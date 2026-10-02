# -*- coding: utf-8 -*-
"""師資資料查核：照片品質 + 師資頁內容完整度 → tools/faculty.json

用法：
    python tools/check-faculty.py inde              # 查核單一系所
    python tools/check-faculty.py inde mcae mse     # 查核多個系所
    python tools/check-faculty.py --all             # 全部（會跑很久）

查核三件事（對應使用者需求）：
  1. 師資照片：缺漏／模糊／頭太貼頂或被裁切／解析度過低
  2. 師資連結內容：個人頁至少要有「專長」與「學歷」
  3. 結果寫入 tools/faculty.json，再用 sync-faculty.py 注入健檢儀表板

照片判讀方式（都會把原始數值一併寫入 json，方便人工覆核）：
  - 模糊：Laplacian 變異數（越小越糊）。<60 判明顯模糊、60–120 判偏糊
  - 頭太貼頂：Haar 正面人臉偵測，算臉框上緣距圖片頂端的比例；
             另掃描頂端列是否已經是人像（非背景）判斷「頭頂觸頂／被裁切」
  - 解析度：短邊 < 200px 視為過低
"""
import base64, io, json, re, sys, time
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse, parse_qs

import numpy as np
import requests
import urllib3
from bs4 import BeautifulSoup
from PIL import Image
import cv2

sys.stdout.reconfigure(encoding='utf-8')
urllib3.disable_warnings()                      # 校內網站憑證鏈缺 SKI，新版 OpenSSL 會擋
HERE = Path(__file__).resolve().parent
OUT = HERE / 'faculty.json'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) FCU-healthcheck'}

"""判讀門檻（2026-10-02 以工工系 21 張照片目視校準）

清晰度一律只量「臉部」而非整張：全身照的大片純色背景會把整張的 Laplacian 變異數
拉到很低，早期版本因此把構圖正常的全身照全部誤判成模糊。
"""
FACE_BLUR_BAD = 10.0                          # 臉部 Laplacian 變異數（縮到 180px 後計算）；低於此判明顯模糊
TOP_GAP_MIN = 0.0                             # 臉框上緣距頂端 = 0% 才算頭太貼頂（2026-10-02 使用者定調）
MIN_SIDE = 200                                # 原圖短邊低於此值視為解析度過低
MIN_FACE_PX = 90                              # 臉在原圖的寬度低於此值，卡片上看不清五官
THUMB_W = 56                                  # 內嵌縮圖寬度（臉部裁切）；放大會讓 health-check.html 暴肥

# 師資職稱排序原則（公共事務組提供，2026-10-02）。名單與選單都該照這個順序排。
# 中文標籤 → job_title 的正確對應（取自全校 68 系選單的多數用法）。
# 某一系的連結與這張表不符，表示那條連結設錯，點進去會看到別類師資或空白。
LABEL_JOBTITLE = {
    '講座教授': 'Chair Professor',
    '特約講座': 'Adjunct Chair Professor',
    '特聘教授': 'Distinguished Professor',
    '專任教授': 'Professor',
    '專任副教授': 'Associate Professor',
    '專任助理教授': 'Assistant Professor',
    '專任講師': 'Lecturer',
    '客座教授': 'Visiting Professor',
    '研究副教授': 'Research Associate Professor',
    '研究助理教授': 'Research Assistant Professor',
    '兼任教授': 'Adjunct Professor',
    '兼任副教授': 'Adjunct Associate Professor',
    '兼任助理教授': 'Adjunct Assistant Professor',
    '兼任講師': 'Adjunct Lecturer',
}

TITLE_ORDER = [
    '何宜武先生學術講座', '高人言先生學術講座', '春雨講座', '生日講座',
    '榮譽特聘講座', '特聘講座', '講座教授', '特約講座',
    '榮譽特聘教授', '特聘教授', '專任教授', '客座教授', '特約客座教授', '榮譽教授',
    '專任副教授', '特約客座副教授', '專任助理教授', '專任講師',
    '研究教授', '研究副教授', '研究助理教授',
    '兼任教授', '兼任副教授', '兼任助理教授', '兼任講師',
]
TITLE_RANK = {t: i + 1 for i, t in enumerate(TITLE_ORDER)}


def rank_of(t):
    """排序原則沒收錄的職稱排在最後，並另外列出來請人工確認。"""
    return TITLE_RANK.get((t or '').strip(), 99)


CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')


def get(url, tries=3, params=None):
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=40, verify=False, params=params)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return None
        except Exception:
            pass
        time.sleep(1.5 * (i + 1))
    return None


# 師資照片不在 HTML 裡，由 teachers.js 向校網 API 取回 base64（見 getThumb()）
THUMB_API = 'https://www.fcu.edu.tw/wp-json/api/v1/get_teacher_thumb/'


def fetch_thumb(tid, unit_id):
    if not tid:
        return None
    txt = get(THUMB_API, params={'id': tid, 'unit_id': unit_id or ''})
    if not txt:
        return None
    try:
        th = json.loads(txt).get('thumb')
    except Exception:
        return None
    img = (th or {}).get('image')
    return 'data:image/jpeg;base64,' + img if img else None


def fetch_image(url):
    """直接抓圖片位元組（部分系網的照片是一般圖檔網址，不走校網 API）。"""
    if not url:
        return None
    try:
        r = requests.get(url, headers=UA, timeout=40, verify=False)
        if r.status_code == 200 and r.content:
            return r.content
    except Exception:
        pass
    return None


def analyse_photo(raw):
    """回傳照片品質判讀 dict；raw 為 None 代表沒有照片。"""
    if not raw:
        return {'has': 0}
    if isinstance(raw, str):                       # data URI
        try:
            raw = base64.b64decode(raw.split(',', 1)[1])
        except Exception as e:
            return {'has': 0, 'err': '照片解碼失敗：%s' % type(e).__name__}
    try:
        im = Image.open(io.BytesIO(raw))
        im.load()
    except Exception as e:
        return {'has': 0, 'err': '照片解碼失敗：%s' % type(e).__name__}

    w, h = im.size
    rgb = im.convert('RGB')
    arr = np.asarray(rgb)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    side = min(w, h)

    faces = CASCADE.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=5,
                                     minSize=(max(24, int(side * .08)),) * 2)
    face = max(faces, key=lambda f: f[2] * f[3]) if len(faces) else None

    face_px, face_blur, top_gap, cut = 0, None, None, 0
    if face is not None:
        fx, fy, fw, fh = (int(v) for v in face)
        face_px, top_gap = fw, round(fy / h, 3)
        crop = gray[max(0, fy):fy + fh, max(0, fx):fx + fw]
        if crop.size:
            face_blur = round(float(cv2.Laplacian(cv2.resize(crop, (180, 180)),
                                                  cv2.CV_64F).var()), 1)
        cut = int(fy <= 1 or fx <= 1 or fx + fw >= w - 1)   # 臉框貼到邊界＝臉被裁掉

    flat = int(float(gray.std()) < 12)                      # 整張幾乎單色＝空白／佔位圖

    # issues＝真的要請系上處理的；notes＝只列供參考，不計入「照片有疑慮」。
    # 2026-10-02 使用者定調：只抓「模糊」與「頭太貼頂」，照片不夠銳利（原本的「偏軟」）不算問題。
    issues, notes = [], []
    if flat:
        issues.append('照片疑似空白或佔位圖（整張幾乎單色）')
    if face is None:
        notes.append('偵測不到正面人臉（可能是側臉、團體照或非人像，需人工確認）')
    else:
        if cut:
            issues.append('臉部被裁切到照片邊緣')
        elif top_gap <= TOP_GAP_MIN:
            issues.append('頭部太貼近上緣（臉部上緣已到照片頂端，距頂端 0%）')
        if face_blur is not None and face_blur < FACE_BLUR_BAD:
            issues.append('臉部明顯模糊／失焦（清晰度 %.0f）' % face_blur)
        if face_px < MIN_FACE_PX:
            notes.append('臉部在原圖僅 %d px 寬' % face_px)
    if side < MIN_SIDE:
        notes.append('照片解析度偏低（%d×%d）' % (w, h))

    return {'has': 1, 'w': w, 'h': h, 'facePx': face_px, 'faceBlur': face_blur,
            'topGap': top_gap, 'cut': cut, 'flat': flat, 'bytes': len(raw),
            'thumb': make_thumb(rgb, face), 'issues': issues, 'notes': notes}


def make_thumb(rgb, face):
    """臉部附近裁一張小縮圖內嵌到儀表板，讓人可以直接目視覆核。"""
    w, h = rgb.size
    if face is not None:
        fx, fy, fw, fh = (int(v) for v in face)
        pad = int(fw * 0.45)
        box = (max(0, fx - pad), max(0, fy - pad), min(w, fx + fw + pad), min(h, fy + fh + pad))
    else:
        s = min(w, h)
        box = ((w - s) // 2, 0, (w - s) // 2 + s, s)
    crop = rgb.crop(box).resize((THUMB_W, THUMB_W), Image.LANCZOS)
    buf = io.BytesIO()
    crop.save(buf, 'JPEG', quality=58, optimize=True)
    return base64.b64encode(buf.getvalue()).decode('ascii')


FIELD_PAT = {
    'spec': re.compile(r'(研究專長|專長|專業領域|研究領域)'),
    'edu':  re.compile(r'(學歷|最高學歷|Education)'),
}

# ⚠ 師資個人頁的「專長／學歷／經歷／著作」全部是 JS 向校網 API 取回後才填進畫面的，
#   直接抓個人頁 HTML 只會拿到「基本資訊」的空殼（2026-10-02 曾因此把全系誤判成缺專長學歷）。
INFO_API = 'https://www.fcu.edu.tw/wp-json/api/v1/teacher/info'


def fetch_detail(tid):
    """師資個人頁實際顯示的內容（與頁面同一支 API）。"""
    empty = {'ok': 0, 'spec': 0, 'edu': 0, 'nSpec': 0, 'nEdu': 0,
             'topEdu': '', 'specs': [], 'rich': {}}
    if not tid:
        return empty
    txt = get(INFO_API, params={'id': tid})
    if not txt:
        return empty
    try:
        d = json.loads(txt).get('data') or {}
    except Exception:
        return empty

    skills = [s.get('ski_desc_c') or s.get('ski_desc') or '' for s in (d.get('skill') or [])]
    skills = [s for s in skills if s.strip()]
    edus = d.get('edu') or []

    def edu_label(e):
        return ' / '.join(x for x in [e.get('edu_xmcname'), e.get('edu_xddname'),
                                      e.get('xdl_name')] if x)
    rank = {'博士': 3, '碩士': 2, '學士': 1}
    top = max(edus, key=lambda e: rank.get(e.get('xdl_name'), 0)) if edus else None

    return {'ok': 1,
            'spec': 1 if skills else 0,
            'edu': 1 if edus else 0,
            'nSpec': len(skills), 'nEdu': len(edus),
            'specs': skills[:8],
            'topEdu': edu_label(top) if top else '',
            'rich': {k: len(d.get(k) or []) for k in
                     ('fcuExp', 'journal', 'conference', 'book', 'patent', 'reward')}}


# ══════════════════════════════════════════════════════════════════
# 選單師資二階 vs 實際師資職稱
#   需求：該系有哪些師資類別（職稱），導覽選單的「師資」底下就該有對應的二階連結。
#   例：工工系有一位特約講座，選單就要有「特約講座」的連結。
#   選單是伺服器端輸出的，直接抓首頁 HTML 即可（不像照片與個人頁要走 API）。
# ══════════════════════════════════════════════════════════════════
# 非教學人員與已離職者不列入師資查核。
#   有些系網把師資頁與成員頁合在一起（資工系就把行政人員、退休／離職教師一起列），
#   算進師資會灌大人數、也會讓職稱比對出現一堆排序原則沒收錄的項目。
#   排除的人會另外記錄下來，儀表板上會寫明排除了誰，不是悄悄丟掉。
DEPARTED_PAT = re.compile(r'離職|退休|卸任|留職停薪')
NON_TEACHING = {'助理', '研究助理', '專案助理', '組員', '技士', '技佐', '技術員',
                '書記', '幹事', '專員', '秘書', '工友', '職員', '行政人員', '約僱人員'}


def is_teaching(job):
    """判斷這個職稱算不算師資。沒寫職稱的保留，交給人工看。"""
    j = (job or '').strip()
    if not j:
        return True
    if DEPARTED_PAT.search(j):
        return False
    return j not in NON_TEACHING


def txt(el):
    """取元素文字。部分系網是 Vue 樣板，內容會被解析成 TemplateString，
    get_text() 會回空字串，要退回 .string（2026-10-02 經管學院踩到）。"""
    if el is None:
        return ''
    t = el.get_text(' ', strip=True)
    if not t and el.string:
        t = str(el.string)
    return t.strip()


def scrape_home(base):
    """抓系網首頁一次，取回：①師資列表頁網址 ②選單「師資」底下的職稱二階項目。

    各系的師資頁路徑不一致（/teachers/ 或 /faculty/ 都有），所以不寫死，
    優先從選單那幾條帶 job_title 的連結反推，再退回總覽連結，最後才逐一試。
    """
    root = base.rstrip('/')
    html = get(root + '/')
    items, listing = [], None
    if html:
        soup = BeautifulSoup(html, 'html.parser')
        # 以「畫面上看到的標籤」去重，不能用 job_title——有的系網兩個不同項目
        # 指到同一個 job_title（材料系的專任/兼任助理教授就是），用 job_title
        # 去重會把其中一項當成重複丟掉，變成誤報「選單缺某類別」。
        by_t = {}
        for a in soup.find_all('a', href=True):
            if 'job_title=' not in a['href']:
                continue
            href = urljoin(root + '/', a['href'])
            q = unquote(re.search(r'job_title=([^&]*)', href).group(1).replace('+', ' ')).strip()
            t = a.get_text(' ', strip=True)
            if t and t not in by_t:
                by_t[t] = {'t': t, 'q': q}
            if listing is None:
                listing = href.split('?')[0]
        items = list(by_t.values())
        if listing is None:
            for a in soup.find_all('a', href=True):
                if re.search(r'/(teachers|faculty)/?$', a['href']):
                    listing = urljoin(root + '/', a['href']).rstrip('/') + '/'
                    break
    if listing is None:
        for path in ('/teachers/', '/faculty/'):
            if get(root + path):
                listing = root + path
                break
    return listing, (items if html is not None else None)


def check_order(seq):
    """seq 是依畫面出現順序的職稱清單；回傳是否符合排序原則，以及第一個逆序的位置。

    排序原則沒收錄的職稱（rank 99）不參與比對——否則它一律被當成最後一級，
    只要它出現在中間，後面每一個正常職稱都會被誤判成逆序。那類職稱改以
    unknown 清單另外列出請人工確認。
    """
    known = [(t, rank_of(t)) for t in seq if rank_of(t) != 99]
    for i in range(1, len(known)):
        if known[i][1] < known[i - 1][1]:
            return 0, {'at': i, 'prev': known[i - 1][0], 'cur': known[i][0]}
    return 1, None


def compare_menu(menu, rows):
    """比對選單二階與師資實際職稱，並檢查兩邊的排序是否符合排序原則。"""
    counts = {}
    for r in rows:
        j = (r.get('job') or '').strip()
        if j:
            counts[j] = counts.get(j, 0) + 1
    cats = sorted(counts, key=lambda k: (rank_of(k), k))          # 依排序原則
    list_seq = [(r.get('job') or '').strip() for r in rows if (r.get('job') or '').strip()]
    list_ok, list_bad = check_order(list_seq)
    unknown = sorted({t for t in list(counts) if rank_of(t) == 99})

    base = {'counts': counts, 'cats': cats, 'unknown': unknown,
            'listOk': list_ok, 'listBad': list_bad}
    if menu is None:
        return dict(base, ok=0, items=[], missing=[], extra=[], clash=[],
                    menuOk=1, menuBad=None, note='抓不到首頁，無法比對選單')
    labels = [m['t'].strip() for m in menu if m['t'].strip()]
    menu_ok, menu_bad = check_order(labels)
    # 連結設錯：標籤對應的 job_title 與全校通用對照不符，
    # 點進去會列出別類師資（或因網址打錯而空白）。
    clash = []
    for m in menu:
        t, q = m['t'].strip(), (m.get('q') or '').strip()
        want = LABEL_JOBTITLE.get(t)
        if t and q and want and q != want:
            clash.append({'t': t, 'q': q, 'want': want,
                          'as': next((k for k, v in LABEL_JOBTITLE.items() if v == q), '')})
    unknown = sorted(set(unknown) | {t for t in labels if rank_of(t) == 99})
    return dict(base, ok=1, items=menu, unknown=unknown, clash=clash,
                missing=[c for c in cats if c not in labels],
                extra=[l for l in labels if l not in counts],
                menuOk=menu_ok, menuBad=menu_bad,
                note='' if labels else '選單沒有師資職稱二階連結')


CARD_RE = re.compile(r'<div[^>]*class="a-flip-personal-card__front"[^>]*>', re.S)


def scrape_dept(listing):
    rows, page, seen = [], 1, set()
    while page <= 12:
        url = listing + ('?post_page=%d' % page if page > 1 else '')
        html = get(url)
        if not html or 'a-flip-personal-card' not in html:
            break
        soup = BeautifulSoup(html, 'html.parser')
        cards = soup.select('.a-flip-personal-card')
        if not cards:
            break
        added = 0
        for c in cards:
            front = c.select_one('.a-flip-personal-card__front')
            a = c.select_one('a[href*="teachers-detail"]')
            tid = (front.get('data-thumb-id') if front else '') or ''
            unit = (front.get('data-unit-id') if front else '') or ''
            if a and not tid:
                # 有些系網沒有 data-thumb-id，工號改從個人頁連結取
                q = parse_qs(urlparse(a['href']).query)
                tid = (q.get('id') or [''])[0]
                unit = unit or (q.get('unit_id') or [''])[0]
            name = txt(c.select_one('.a-flip-personal-card__name'))
            if not tid and not name:
                continue                      # 空殼卡片直接丟掉
            key = (tid, name)
            if key in seen:
                continue                      # 有些系網 ?post_page= 無效，每頁都回同一批
            seen.add(key)
            added += 1
            subs = [txt(x) for x in c.select('.a-flip-personal-card__sub')]
            texts = [txt(x) for x in c.select('.a-flip-personal-card__text')]
            card = dict(zip(subs, texts))
            rows.append({
                'id': tid,
                'unit': unit,
                'name': name,
                'job': txt(c.select_one('.a-flip-personal-card__job')),
                'url': a['href'] if a else '',
                'cardSpec': next((v for k, v in card.items() if FIELD_PAT['spec'].search(k)), ''),
                'cardEdu': next((v for k, v in card.items() if FIELD_PAT['edu'].search(k)), ''),
            })
        if not added:
            break                             # 這一頁沒有新面孔，停止翻頁
        page += 1
    return rows


# ══════════════════════════════════════════════════════════════════
# 其他版型的師資頁
#   全校並非每個系都用同一套版型，除了標準的翻卡（a-flip-personal-card）外，
#   還有另一種卡片（a-personal-card）、純連結清單、以及資工系自建的版面。
#   每種都另外寫一支解析，解析不到的就記成「網站上找不到師資名單」。
# ══════════════════════════════════════════════════════════════════
def scrape_cards_alt(html, listing):
    """a-personal-card 版型：照片是一般圖檔網址，專長直接寫在卡片上。"""
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for c in soup.select('a.a-personal-card, .a-personal-card'):
        name = txt(c.select_one('.a-personal-card__name'))
        if not name:
            continue
        img = c.select_one('.a-personal-card__image')
        pic = ''
        if img:
            for attr in (':style', 'style'):
                v = img.get(attr) or ''
                m = re.search(r"bgStyle\(['\"]([^'\"]+)|url\(['\"]?([^'\")]+)", v)
                if m:
                    pic = m.group(1) or m.group(2); break
        spec = ''
        for li in c.select('.a-personal-card__item'):
            if FIELD_PAT['spec'].search(txt(li.select_one('.a-personal-card__item-title')) or ''):
                spec = ' / '.join(x for x in li.stripped_strings if not FIELD_PAT['spec'].search(x))
        href = c.get('href') or ''
        a2 = c.select_one('a[href]')
        rows.append({'id': '', 'unit': '', 'name': name,
                     'job': txt(c.select_one('.a-personal-card__job')),
                     'url': href or (a2['href'] if a2 else ''),
                     'pic': urljoin(listing, pic) if pic else '',
                     'cardSpec': spec, 'cardEdu': ''})
    return rows


def scrape_links_alt(html):
    """任何版面：只要頁上有 teachers-detail?id= 的連結就能組出名單（連結文字是姓名＋職稱）。"""
    soup = BeautifulSoup(html, 'html.parser')
    rows, seen = [], set()
    for a in soup.select('a[href*="teachers-detail"]'):
        q = parse_qs(urlparse(a['href']).query)
        tid = (q.get('id') or [''])[0]
        if not tid or tid in seen:
            continue
        seen.add(tid)
        parts = [x for x in a.stripped_strings]
        rows.append({'id': tid, 'unit': (q.get('unit_id') or [''])[0],
                     'name': parts[0] if parts else '',
                     'job': parts[1] if len(parts) > 1 else '',
                     'url': a['href'], 'cardSpec': '', 'cardEdu': ''})
    return rows


def scrape_iecs(html, base):
    """資工系自建版型：照片在 .thumb-info-side-image-wrapper，姓名與職稱在相鄰的 caption。"""
    soup = BeautifulSoup(html, 'html.parser')
    rows, seen = [], set()
    for cap in soup.select('.thumb-info-caption-text'):
        h3 = cap.find(['h3', 'h2'])
        name = (h3.find(string=True) or '').strip() if h3 else ''
        if not name or name in seen:
            continue
        seen.add(name)
        strongs = [txt(x) for x in cap.find_all('strong')]
        job = strongs[0] if strongs else ''
        spec = next((re.sub(r'^研究專長[:：]\s*', '', x) for x in strongs
                     if FIELD_PAT['spec'].search(x)), '')
        link = cap.find('a', href=True)
        # 照片在同一個 row 裡的另一欄
        pic, row = '', cap
        for _ in range(6):
            row = row.parent
            if row is None:
                break
            im = row.select_one('img[src*="/media/img/teacher/"]')
            if im:
                pic = urljoin(base, im['src']); break
        rows.append({'id': '', 'unit': '', 'name': name, 'job': job,
                     'url': urljoin(base, link['href']) if link else '',
                     'pic': '' if pic.endswith('default.jpg') else pic,
                     'cardSpec': spec, 'cardEdu': ''})
    return rows


def run(dept):
    base = dept['url'].rstrip('/')
    listing, menu = scrape_home(base)
    rows, how = [], ''
    if listing:
        rows, how = scrape_dept(listing), '標準卡片'
    # 標準版型抓不到時，依序試其他版型
    if not rows:
        for path in ([listing] if listing else []) + [base + '/teacher/', base + '/faculty/',
                                                      base + '/teachers/', base + '/teachers']:
            if not path:
                continue
            html = get(path)
            if not html:
                continue
            for fn, label in ((lambda h: scrape_cards_alt(h, path), '卡片版型B'),
                              (lambda h: scrape_iecs(h, base), '自建版型'),
                              (lambda h: scrape_links_alt(h), '師資連結清單')):
                try:
                    r = fn(html)
                except Exception:
                    r = []
                if r:
                    rows, listing, how = r, path, label
                    break
            if rows:
                break
    if not rows:
        return [], menu, '', '', []
    dropped = [{'name': r['name'], 'job': r['job']} for r in rows if not is_teaching(r['job'])]
    rows = [r for r in rows if is_teaching(r['job'])]
    if not rows:
        return [], menu, '', '', dropped
    out = []
    for r in rows:
        photo = analyse_photo(fetch_image(r['pic']) if r.get('pic')
                              else fetch_thumb(r['id'], r.get('unit')))
        detail = fetch_detail(r['id'])
        issues = list(photo.get('issues', []))
        notes = list(photo.get('notes', []))
        if not photo.get('has'):
            issues.insert(0, '沒有個人照片')
        if detail['ok']:
            if not detail['spec']:
                issues.append('個人頁沒有專長')
            if not detail['edu']:
                issues.append('個人頁沒有學歷')
        else:
            # 這類系網沒有校網格式的師資個人頁（沒有工號可查），
            # 不能當成「缺專長／缺學歷」——那是查不到，不是沒有。
            notes.append('無校網師資個人頁，專長／學歷無法自動查核'
                         + ('；列表卡片上有列專長' if r.get('cardSpec') else ''))
        out.append({
            'tid': r['id'], 'name': r['name'], 'job': r['job'], 'url': r['url'],
            'photo': {k: v for k, v in photo.items() if k not in ('issues', 'notes')},
            'detail': detail,
            'cardSpec': 1 if r['cardSpec'] else 0,
            'cardEdu': 1 if r['cardEdu'] else 0,
            'cardSpecs': [x.strip() for x in re.split(r'[/、,，\s]+', str(r.get('cardSpec') or '')) if x.strip()][:8],
            'issues': issues,
            'notes': notes,
        })
    return out, menu, listing, how, dropped


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit('用法：python tools/check-faculty.py <學系id> [學系id...] | --all')
    depts = json.loads((HERE / 'depts.json').read_text(encoding='utf-8'))
    by_id = {d['id']: d for d in depts}
    targets = [d['id'] for d in depts] if args == ['--all'] else args
    bad = [t for t in targets if t not in by_id]
    if bad:
        sys.exit('查無此學系 id：' + '、'.join(bad))

    data = {}
    if OUT.exists():
        data = json.loads(OUT.read_text(encoding='utf-8')).get('depts', {})

    def save():
        OUT.write_text(json.dumps({'built': time.strftime('%Y-%m-%d %H:%M'), 'depts': data},
                                  ensure_ascii=False, indent=1), encoding='utf-8')

    for n, t in enumerate(targets, 1):
        d = by_id[t]
        print('[%d/%d] 查核 %s %s …' % (n, len(targets), t, d['name']), flush=True)
        try:
            rows, menu, listing, how, dropped = run(d)
        except Exception as e:
            print('   ⚠ 查核失敗（%s: %s），已略過，其餘學系繼續' % (type(e).__name__, e))
            continue
        if not rows:
            data[t] = {'name': d['name'], 'url': '', 'home': d['url'].rstrip('/') + '/',
                       'checked': time.strftime('%Y-%m-%d'), 'rows': [],
                       'noFaculty': 1, 'menu': compare_menu(menu, [])}
            print('   ⚠ 網站上找不到師資名單，已標註為「沒有」')
            save()
            continue
        np_ = sum(1 for r in rows if not r['photo'].get('has'))
        pi = sum(1 for r in rows if r['photo'].get('has')
                 and any('個人頁' not in i for i in r['issues']))
        ns = sum(1 for r in rows if r['detail']['ok'] and not r['detail']['spec'])
        ne = sum(1 for r in rows if r['detail']['ok'] and not r['detail']['edu'])
        nc = sum(1 for r in rows if not r['detail']['ok'])
        menu = compare_menu(menu, rows)
        data[t] = {'name': d['name'], 'url': listing, 'how': how, 'dropped': dropped,
                   'home': d['url'].rstrip('/') + '/',
                   'checked': time.strftime('%Y-%m-%d'), 'rows': rows, 'menu': menu}
        print('   師資 %d 位｜無照片 %d｜照片有疑慮 %d｜個人頁缺專長 %d｜缺學歷 %d%s%s'
              % (len(rows), np_, pi, ns, ne,
                 '｜無個人頁可查 %d' % nc if nc else '',
                 '｜已排除非教學／離職 %d 位（%s）' % (len(dropped),
                     '、'.join(sorted({x['job'] for x in dropped}))) if dropped else ''))
        mn = data[t]['menu']
        print('   師資類別 %d 種｜選單二階 %d 項｜選單缺 %s｜選單多 %s'
              % (len(mn['cats']), len(mn['items']),
                 '、'.join(mn['missing']) or '無', '、'.join(mn['extra']) or '無'))
        for c in mn.get('clash', []):
            print('   ⚠ 選單連結設錯：「%s」指向 %s%s（應為 %s）'
                  % (c['t'], c['q'], '＝' + c['as'] + '的篩選' if c['as'] else '', c['want']))
        print('   名單排序 %s｜選單排序 %s%s'
              % ('✓' if mn['listOk'] else '✗ %s 排在 %s 之後' % (mn['listBad']['cur'], mn['listBad']['prev']),
                 '✓' if mn['menuOk'] else '✗ %s 排在 %s 之後' % (mn['menuBad']['cur'], mn['menuBad']['prev']),
                 '｜排序原則未收錄：' + '、'.join(mn['unknown']) if mn['unknown'] else ''))
        save()          # 每跑完一系就寫檔，中斷時已完成的部分不會白跑

    save()
    print('→ tools/faculty.json（已含 %d 個學系）' % len(data))


if __name__ == '__main__':
    main()

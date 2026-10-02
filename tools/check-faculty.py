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
FACE_BLUR_BAD = 40.0                          # 臉部 Laplacian 變異數（縮到 180px 後計算）；低於此判明顯模糊
TOP_GAP_MIN = 0.10                            # 臉框上緣距頂端 < 10% 視為頭太貼頂
MIN_SIDE = 200                                # 原圖短邊低於此值視為解析度過低
MIN_FACE_PX = 90                              # 臉在原圖的寬度低於此值，卡片上看不清五官
THUMB_W = 84                                  # 內嵌縮圖寬度（臉部裁切）

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


def analyse_photo(data_uri):
    """回傳照片品質判讀 dict；data_uri 為 None 代表沒有照片。"""
    if not data_uri:
        return {'has': 0}
    try:
        b64 = data_uri.split(',', 1)[1]
        raw = base64.b64decode(b64)
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
        elif top_gap < TOP_GAP_MIN:
            issues.append('頭部太貼近上緣（臉部上緣距頂端僅 %.0f%%）' % (top_gap * 100))
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
    crop.save(buf, 'JPEG', quality=62, optimize=True)
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


CARD_RE = re.compile(r'<div[^>]*class="a-flip-personal-card__front"[^>]*>', re.S)


def scrape_dept(dept):
    base = dept['url'].rstrip('/')
    rows, page = [], 1
    while page <= 12:
        url = base + '/teachers/' + ('?post_page=%d' % page if page > 1 else '')
        html = get(url)
        if not html or 'a-flip-personal-card' not in html:
            break
        soup = BeautifulSoup(html, 'html.parser')
        cards = soup.select('.a-flip-personal-card')
        if not cards:
            break
        for c in cards:
            front = c.select_one('.a-flip-personal-card__front')
            name = c.select_one('.a-flip-personal-card__name')
            job = c.select_one('.a-flip-personal-card__job')
            a = c.select_one('a[href*="teachers-detail"]')
            subs = [s.get_text(' ', strip=True) for s in c.select('.a-flip-personal-card__sub')]
            texts = [s.get_text(' ', strip=True) for s in c.select('.a-flip-personal-card__text')]
            card = dict(zip(subs, texts))
            rows.append({
                'id': (front.get('data-thumb-id') if front else '') or '',
                'unit': (front.get('data-unit-id') if front else '') or '',
                'name': name.get_text(strip=True) if name else '',
                'job': job.get_text(strip=True) if job else '',
                'url': a['href'] if a else '',
                'cardSpec': next((v for k, v in card.items() if FIELD_PAT['spec'].search(k)), ''),
                'cardEdu': next((v for k, v in card.items() if FIELD_PAT['edu'].search(k)), ''),
            })
        page += 1
    return rows


def run(dept):
    rows = scrape_dept(dept)
    out = []
    for r in rows:
        photo = analyse_photo(fetch_thumb(r['id'], r.get('unit')))
        detail = fetch_detail(r['id'])
        issues = list(photo.get('issues', []))
        notes = list(photo.get('notes', []))
        if not photo.get('has'):
            issues.insert(0, '沒有個人照片')
        if not detail['spec']:
            issues.append('個人頁沒有專長')
        if not detail['edu']:
            issues.append('個人頁沒有學歷')
        out.append({
            'tid': r['id'], 'name': r['name'], 'job': r['job'], 'url': r['url'],
            'photo': {k: v for k, v in photo.items() if k not in ('issues', 'notes')},
            'detail': detail,
            'cardSpec': 1 if r['cardSpec'] else 0,
            'cardEdu': 1 if r['cardEdu'] else 0,
            'issues': issues,
            'notes': notes,
        })
    return out


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

    for t in targets:
        d = by_id[t]
        print('查核 %s %s …' % (t, d['name']), flush=True)
        rows = run(d)
        if not rows:
            print('   ⚠ 抓不到師資卡片，可能版型不同，已略過')
            continue
        np_ = sum(1 for r in rows if not r['photo'].get('has'))
        pi = sum(1 for r in rows if r['photo'].get('has')
                 and any('個人頁' not in i for i in r['issues']))
        ns = sum(1 for r in rows if not r['detail']['spec'])
        ne = sum(1 for r in rows if not r['detail']['edu'])
        data[t] = {'name': d['name'], 'url': d['url'].rstrip('/') + '/teachers/',
                   'checked': time.strftime('%Y-%m-%d'), 'rows': rows}
        print('   師資 %d 位｜無照片 %d｜照片有疑慮 %d｜個人頁缺專長 %d｜缺學歷 %d'
              % (len(rows), np_, pi, ns, ne))

    OUT.write_text(json.dumps({'built': time.strftime('%Y-%m-%d %H:%M'), 'depts': data},
                              ensure_ascii=False, indent=1), encoding='utf-8')
    print('→ tools/faculty.json（已含 %d 個學系）' % len(data))


if __name__ == '__main__':
    main()

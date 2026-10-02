# -*- coding: utf-8 -*-
"""
review_news_v4.py — 校園新聞審核機制 v4.0（News Gatekeeper）

與 v3.x 的根本差異：**不產生加權分數**。改以四道關卡依序判定，輸出可執行的編輯建議。

用法：
    python review_news_v4.py <article_list.json> [--refresh]

輸入：文章清單 JSON（[{d, t, url}, ...]）
輸出：
    article_review_v4.json   — 每篇的完整審核結果
    article_content_cache.json — 內文/圖片快取（規則調整時免重抓）

關卡順序（不可調換）：
  Gate 1 新聞類型判定  → 非新聞立即 🔴 停止，不再往下審
  Gate 2 新聞完整度    → 列出缺漏要素（不計分）
  Gate 3 新聞照片素材  → 僅客觀項目：張數、圖說、重複圖（不做影像辨識）

最終結果：🟢 可發布 / 🟡 需修改 / 🔴 非新聞

註：原規格的「AI 語感偵測」關卡已於 2026-08-01 依使用者決定移除——
    現有稿件皆為同仁撰寫，該關卡實際偵測到的是「公關腔」而非 AI 生成文，
    與設立目的不符。若日後確有 AI 代寫稿需求，再重新設計。
"""

# ── 路徑已改為相對本專案（2026-10-01 從「工具程式」資料夾搬入）──
# 本檔位置：fcu-news-dashboard/tools/news-pipeline/
from pathlib import Path as _P
PROJ = _P(__file__).resolve().parents[2]   # fcu-news-dashboard/
HERE = _P(__file__).resolve().parent       # tools/news-pipeline/
DASHBOARD = PROJ / 'index.html'            # 新聞監測儀表板

import sys, io, re, json, time, os
import html as html_mod
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_FILE = os.path.join(BASE, 'article_review_v4.json')
CACHE_FILE = os.path.join(BASE, 'article_content_cache.json')

# ══════════════════════════════════════════════════════════════════
# Gate 1：新聞類型判定
# ══════════════════════════════════════════════════════════════════
# 標題若含這些字樣，僅視為「非新聞候選」，仍須內文佐證才判定（見 gate1_news_type）
# —— 因為「校園徵才說明會登場」「連三年分發滿招」這類是**報導徵才/招生活動的新聞**，
#    只看標題會誤殺（2026-08-01 實測 3 篇全為誤判）
NON_NEWS_RE = re.compile(
    r'公告|甄選|甄試|招生|報名|徵件|徵才|招募|截止|注意事項|作業規定|相關事項|'
    r'依規辦理|填報|開放申請|開始申請|通知單|申請說明|課程加退選|時程與注意'
)
# 純行政/系統類：不需內文佐證，直接判非新聞
HARD_NON_NEWS_RE = re.compile(r'系統維護|維護公告|停機|服務中斷|網站維護')
# 內文的「行動呼籲／辦理須知」訊號 → 傾向公告
CTA_RE = re.compile(
    r'報名方式|報名截止|報名網址|報名表|報名期間|報名地點|線上報名|歡迎報名|'
    r'申請期限|申請方式|申請日期|申請時間|資格限制|應具備資格|名額|'
    r'請於|意者|洽詢|聯絡人|收件|檢附|檢具|備妥|繳交|表格下載|請自行下載|'
    r'即日起至|截止日期|逾期不受理|承辦人|報名費|注意事項如下'
)
# 內文的「事件報導」訊號 → 傾向新聞（已發生）
EVENT_RE = re.compile(
    r'舉行|舉辦|登場|圓滿|順利|落幕|揭曉|參與|出席|吸引|蒞臨|表示|指出|強調|'
    r'獲頒|榮獲|勇奪|奪得|頒發|合影|致詞|開幕|閉幕'
)
# iecs（Porto CMS）內文開頭固定為「由 作者 分類 N 瀏覽」，站方自訂的分類是最權威的訊號：
# 課務公告／演講公告／一般活動公告／競爭力活動公告 皆為通知，不是新聞報導。
# 實測 iecs 有 16 篇屬「公告」分類，僅 4 篇被關鍵字規則抓到，其餘 12 篇漏判
# （例如「【專題演講】…」內文是「演講日期／演講地點／值日生」的事前通知）。
# 註：部分文章沒有「由 作者」前綴，直接以「分類 N 瀏覽」開頭，故作者段為選填。
SITE_CAT_RE = re.compile(r'^\s*(?:由\s+\S+\s+)?(\S{2,10}?)\s+[\d,]+\s*瀏覽')

# 未來式事件 → 活動預告，依規格屬非新聞
FUTURE_RE = re.compile(
    # 「將於…舉辦」中間常夾長串日期＋地址（實測達 36 字），範圍需放寬
    r'將於[^。]{0,60}(?:舉行|舉辦|登場|開跑|進行|展開)|即將[^。]{0,15}(?:舉行|舉辦|登場)|'
    r'預計於|敬請期待|敬邀|歡迎踴躍|歡迎參加|自由入場|報名從速|共襄盛舉'
)

# ══════════════════════════════════════════════════════════════════
# Gate 2：新聞完整度要素
# ══════════════════════════════════════════════════════════════════
TIME_RE   = re.compile(r'\d{1,2}月\d{1,2}日|\d{4}年\d{1,2}月|\d{1,2}/\d{1,2}')
PLACE_RE  = re.compile(
    r'(?:於|在|假)[^，。；]{0,24}(?:舉行|舉辦|辦理|登場|進行|展開|召開|揭幕|開幕|盛大)|'
    r'[^，。；]{0,12}(?:國際會議廳|演講廳|活動中心|體育館|大樓|校區|會館|展場|中心)舉'
)
ACTOR_RE  = re.compile(r'校長|副校長|院長|系主任|主任|教授|老師|教師|學生|同學|校友|團隊|學系|學院|中心|公司|協會|基金會|局長|署長|理事長|董事長')
RESULT_RE = re.compile(
    r'榮獲|勇奪|奪得|獲得|獲頒|入選|通過|完成|達成|突破|提升|成立|簽署|落成|'
    r'冠軍|亞軍|季軍|優勝|首獎|金獎|銀獎|銅獎|特優|佳作|成果|影響|效益'
)
NUM_RE    = re.compile(r'\d+\s*(?:人|位|名|組|件|場|次|校|所|項|屆|億|萬|千|%|％|分|年|個月|公尺|公里|篇|冊|門|班)')
RANK_RE   = re.compile(r'全國[冠亞季]軍|全國第[一二三1-3]|全球排名|全球前\d|世界前\d|四強|冠軍|第[一二三]名')
SPEECH_RE = re.compile(r'表示|指出|強調|認為|談到|提到|說明|分享|期許|勉勵|直言|坦言')
QUOTE_SPAN_RE = re.compile(r'[「『]([^」』]{4,})[」』]')

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode('utf-8', errors='replace')


def _balance_div(html, open_m):
    depth, pos = 1, open_m.end()
    while depth > 0:
        nxt = re.search(r'<div\b|</div>', html[pos:])
        if not nxt:
            return html[open_m.end():open_m.end() + 20000]
        pos += nxt.end()
        depth += 1 if nxt.group().startswith('<div') else -1
    return html[open_m.end():pos - 6]


def extract_content_div(html):
    """三種版型：editor（FCU WP）→ post-content（iecs Porto）→ wix rich-text。"""
    m = re.search(r'<div\b[^>]*class="[^"]*\beditor\b[^"]*"[^>]*>', html)
    if m:
        return _balance_div(html, m)
    m = re.search(r'<div\b[^>]*class="[^"]*\bpost-content\b[^"]*"[^>]*>', html)
    if m:
        return _balance_div(html, m)
    rich = re.findall(
        r'<(?:p|h[1-6])\b[^>]*class="[^"]*wixui-rich-text__text[^"]*"[^>]*>(.*?)</(?:p|h[1-6])>',
        html, re.S)
    if rich:
        return '\n'.join(rich)
    return None


def norm_img(src):
    name = src.split('/')[-1].split('?')[0]
    return re.sub(r'-\d+x\d+(?=\.\w+$)', '', name)


def parse_article(html):
    """回傳 (內文純文字, 圖片總數, 不重複圖片數, 圖說數)。"""
    body = extract_content_div(html)
    if body is None:
        return None
    text = html_mod.unescape(re.sub(r'<[^>]+>', '', body))
    text = re.sub(r'\s+', ' ', text).strip()

    raw_imgs = [s for s in re.findall(r'<img[^>]+src="([^"]+)"', body)
                if '/uploads/' in s or 'wixstatic.com' in s]
    names = [norm_img(s) for s in raw_imgs]
    unique = set(names)
    og = re.search(r'property="og:image" content="([^"]+)"', html)
    if og:
        ou = og.group(1)
        if re.search(r'\.(jpe?g|png|webp)', ou, re.I) and 'logo' not in ou.lower():
            unique.add(norm_img(ou))
    captions = len(re.findall(r'<figcaption|wp-caption-text', body))
    dup = len(names) - len(set(names))
    return text, len(names), len(unique), captions, dup


# ══════════════════════════════════════════════════════════════════
def gate1_news_type(t, c):
    """回傳 (is_news, reason)。

    以**內文性質**為主要依據——標題有無公告字樣只是輔助。
    實測（2026-08-01 航太系）：「114學年度長榮航太專業實習」「…成果發表會」
    這類招募公告與活動預告，標題完全沒有公告關鍵字，只看標題會整批漏掉。
    """
    if HARD_NON_NEWS_RE.search(t):
        return False, HARD_NON_NEWS_RE.search(t).group()

    # 內文抽取為空（純海報圖片公告，無任何文字內容）→ 非新聞
    # 實測案例：水利系「115學年碩士班甄試」內文只有一張海報 <img>，無任何段落文字
    if len(c.strip()) == 0:
        return False, '內文為純圖片公告，無文字內容'

    # 站方自訂分類含「公告」→ 直接判非新聞（比任何關鍵字推測都可靠）
    mcat = SITE_CAT_RE.match(c)
    if mcat and '公告' in mcat.group(1):
        return False, f'站方分類：{mcat.group(1)}'

    ev = len(EVENT_RE.findall(c))
    cta = len(CTA_RE.findall(c))
    fut = FUTURE_RE.search(c)
    title_hit = NON_NEWS_RE.search(t)

    # ① 活動預告：內文寫「將於…舉辦」且沒有已發生的事件描述
    if fut and ev <= 1:
        return False, f'活動預告（{fut.group()[:12]}）'
    # ② 辦理須知型：報名/申請訊號明顯多於事件描述
    if cta >= 2 and ev == 0:
        return False, '招募／申請公告'
    # ③ 標題本身即公告字樣，且內文不是事件報導
    if title_hit and ev <= cta:
        return False, title_hit.group()
    return True, None


def gate2_completeness(t, c):
    """回傳缺漏要素清單。"""
    source = t + '\n' + c
    quotes = QUOTE_SPAN_RE.findall(c)
    has_quote = False
    for m in QUOTE_SPAN_RE.finditer(c):
        near = c[max(0, m.start() - 25):m.end() + 25]
        if SPEECH_RE.search(near):
            has_quote = True
            break

    checks = [
        ('時間',       bool(TIME_RE.search(c))),
        ('地點',       bool(PLACE_RE.search(c))),
        ('人物或單位', bool(ACTOR_RE.search(c))),
        ('主要事件',   len(c) >= 80),
        ('成果或影響', bool(RESULT_RE.search(source))),
        ('引述',       has_quote),
        ('可核實數據', bool(NUM_RE.search(source) or RANK_RE.search(source))),
    ]
    return [name for name, ok in checks if not ok]


def gate3_photos(total, unique, captions, dup):
    """回傳建議清單（僅客觀項目，不做影像辨識）。"""
    tips = []
    if unique == 0:
        tips.append('新聞稿原則上應至少附一張照片。')
    elif unique == 1:
        tips.append('僅有 1 張照片，建議增加照片以強化新聞完整度。')
    if unique > 0 and captions == 0:
        tips.append('所有照片皆未附圖說，建議為每張照片加上圖說。')
    elif 0 < captions < unique:
        tips.append(f'{unique} 張照片中僅 {captions} 張有圖說，建議補齊。')
    if dup > 0:
        tips.append(f'偵測到 {dup} 張重複圖片，建議移除。')
    return tips


def verdict(is_news, missing, unique):
    """🟢 可發布 / 🟡 需修改 / 🔴 非新聞。

    判定原則（照片圖說因系網結構性缺少，不單獨列為降級條件）：
      🔴 非新聞
      🟡 缺漏要素 ≥2、或完全沒有照片
      🟢 其餘
    """
    if not is_news:
        return '🔴 非新聞'
    if len(missing) >= 2 or unique == 0:
        return '🟡 需修改'
    return '🟢 可發布'


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    refresh = '--refresh' in sys.argv[2:]
    with open(sys.argv[1], encoding='utf-8') as f:
        articles = json.load(f)

    cache = {}
    if os.path.exists(CACHE_FILE) and not refresh:
        with open(CACHE_FILE, encoding='utf-8') as f:
            cache = json.load(f)

    # 與既有結果合併（單跑某系時不會弄丟其他系的判定）
    reviews = {}
    if os.path.exists(OUT_FILE):
        with open(OUT_FILE, encoding='utf-8') as f:
            reviews = json.load(f)
    this_run = set()
    fetched, cached_n, failed = 0, 0, []
    for art in articles:
        url, t, d = art.get('url'), art['t'], art.get('d', '')
        if not url:
            continue

        if url in cache:
            cd = cache[url]
            cached_n += 1
        else:
            try:
                parsed = parse_article(fetch(url))
            except Exception as e:
                failed.append((d, t, f'抓取失敗 {e}'))
                continue
            if parsed is None:
                failed.append((d, t, '找不到內文容器'))
                continue
            text, total, unique, captions, dup = parsed
            cd = {'c': text, 'imgs': total, 'uniq': unique, 'caps': captions, 'dup': dup}
            cache[url] = cd
            fetched += 1
            time.sleep(0.6)

        c = cd['c']
        this_run.add(url)
        is_news, nn_reason = gate1_news_type(t, c)
        if not is_news:
            reviews[url] = {'d': d, 't': t, 'verdict': '🔴 非新聞',
                            'non_news_keyword': nn_reason}
            continue

        missing = gate2_completeness(t, c)
        photo_tips = gate3_photos(cd['imgs'], cd['uniq'], cd['caps'], cd['dup'])
        reviews[url] = {
            'd': d, 't': t,
            'verdict': verdict(is_news, missing, cd['uniq']),
            'missing': missing,
            'photos': {'unique': cd['uniq'], 'captions': cd['caps'], 'dup': cd['dup'],
                       'tips': photo_tips},
        }

    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(reviews, f, ensure_ascii=False, indent=1)

    # ── 統計（只計本次執行的文章）──
    from collections import Counter
    scope = {u: reviews[u] for u in this_run if u in reviews}
    vc = Counter(r['verdict'] for r in scope.values())
    print(f'\n本次審核 {len(scope)} 篇（新抓 {fetched}、快取 {cached_n}）'
          f'｜結果檔累計 {len(reviews)} 篇')
    if failed:
        print(f'失敗 {len(failed)} 篇：')
        for d, t, why in failed:
            print(f'  {d} {t[:34]} — {why}')
    print('\n═══ 審核結果 ═══')
    for v in ['🟢 可發布', '🟡 需修改', '🔴 非新聞']:
        n = vc.get(v, 0)
        pct = n / len(scope) * 100 if scope else 0
        print(f'  {v}：{n:4d} 篇（{pct:.1f}%）')

    news_only = [r for r in scope.values() if r['verdict'] != '🔴 非新聞']
    if news_only:
        mc = Counter()
        for r in news_only:
            for m in r['missing']:
                mc[m] += 1
        print(f'\n═══ 缺漏要素統計（新聞類 {len(news_only)} 篇）═══')
        for name, n in mc.most_common():
            print(f'  缺「{name}」：{n:4d} 篇（{n/len(news_only)*100:.1f}%）')

        zero = sum(1 for r in news_only if not r['missing'])
        print(f'  七項全備：{zero:4d} 篇（{zero/len(news_only)*100:.1f}%）')

        no_photo = sum(1 for r in news_only if r['photos']['unique'] == 0)
        one_photo = sum(1 for r in news_only if r['photos']['unique'] == 1)
        no_cap = sum(1 for r in news_only if r['photos']['captions'] == 0)
        has_dup = sum(1 for r in news_only if r['photos']['dup'] > 0)
        print(f'\n═══ 照片素材 ═══')
        print(f'  無照片：{no_photo} 篇｜僅 1 張：{one_photo} 篇')
        print(f'  無圖說：{no_cap} 篇｜有重複圖：{has_dup} 篇')

    print(f'\n已寫入 {OUT_FILE}')


if __name__ == '__main__':
    main()

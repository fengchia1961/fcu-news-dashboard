# -*- coding: utf-8 -*-

# ── 路徑已改為相對本專案（2026-10-01 從「工具程式」資料夾搬入）──
# 本檔位置：fcu-news-dashboard/tools/news-pipeline/
from pathlib import Path as _P
PROJ = _P(__file__).resolve().parents[2]   # fcu-news-dashboard/
HERE = _P(__file__).resolve().parent       # tools/news-pipeline/
DASHBOARD = PROJ / 'index.html'            # 新聞監測儀表板

import re, time, difflib, sys
import urllib.request
from urllib.parse import urlparse

HTML_FILE = str(DASHBOARD)
CUT = "2025.08.01"

CARD_RE = re.compile(
    r'<a\s+[^>]*?href="([^"]+)"[^>]*?class="a-image-card"[\s\S]*?</a>'
)
TITLE_RE = re.compile(r'__title">([^<]+)<')
DATE_RE  = re.compile(r'<p>(\d{4}\.\d{2}\.\d{2})</p>')

# 第二種版型：a-news-list（純文字列表，無縮圖）
LIST_BLOCK_RE = re.compile(
    r'<div class="a-news-list__main">[\s\S]*?</div>\s*</div>'
)
LIST_DATE_RE  = re.compile(r'a-news-list__date">\s*(\d{4}\.\d{2}\.\d{2})\s*<')
LIST_TITLE_RE = re.compile(
    r'<a class="a-news-list__title"\s+href="([^"]+)"\s+target="_blank"\s*>([^<]+)</a>'
)

# 第三種版型：a-event-card（活動卡片，無日期欄位）
EVENT_RE = re.compile(
    r'<a\s+href="([^"]+)"[^>]*?class="a-event-card"[\s\S]{0,1500}?__title">([^<]+)<'
)

# 第四種版型：Porto 自建系統（iecs.fcu.edu.tw 等）
# article.post > .post-content > a.post-title + .post-meta > .meta-data(日期 ISO)
PORTO_BLOCK_RE = re.compile(r'<article[^>]*>([\s\S]*?)</article>')
PORTO_TITLE_RE = re.compile(r'<a\s+class="post-title\s*"\s+href="([^"]+)"[^>]*>([^<]+)</a>')
PORTO_DATE_RE  = re.compile(r'class="meta-data">(\d{4}-\d{2}-\d{2})<')

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="ignore")

def parse_page(html, page_url=''):
    """嘗試四種版型解析，回傳 list of (date, title, url)"""
    out = []
    # 版型 1：a-image-card（含縮圖）
    for m in CARD_RE.finditer(html):
        block = m.group(0)
        href = m.group(1)
        tm = TITLE_RE.search(block)
        dm = DATE_RE.search(block)
        if tm and dm:
            out.append((dm.group(1), tm.group(1).strip(), href))
    if out:
        return out
    # 版型 2：a-news-list（純文字列表）
    for m in LIST_BLOCK_RE.finditer(html):
        block = m.group(0)
        dm = LIST_DATE_RE.search(block)
        tm = LIST_TITLE_RE.search(block)
        if tm and dm:
            out.append((dm.group(1), tm.group(2).strip(), tm.group(1)))
    if out:
        return out
    # 版型 3：a-event-card（活動卡片，無日期，用 None 代表）
    for m in EVENT_RE.finditer(html):
        out.append((None, m.group(2).strip(), m.group(1)))
    if out:
        return out
    # 版型 4：Porto 自建系統（article.post + a.post-title + .meta-data ISO 日期）
    # 所有文章一頁全顯示，不需分頁；日期 YYYY-MM-DD 轉為 YYYY.MM.DD 與 D 陣列格式一致
    parsed_base = urlparse(page_url)
    origin = f"{parsed_base.scheme}://{parsed_base.netloc}" if parsed_base.netloc else ''
    for m in PORTO_BLOCK_RE.finditer(html):
        block = m.group(1)
        tm = PORTO_TITLE_RE.search(block)
        dm = PORTO_DATE_RE.search(block)
        if tm and dm:
            iso_date = dm.group(1)                  # e.g. 2026-06-30
            dot_date = iso_date.replace('-', '.')   # e.g. 2026.06.30
            href = tm.group(1)                      # e.g. /news/TITLE%20.../
            if href.startswith('/') and origin:
                href = origin + href
            out.append((dot_date, tm.group(2).strip(), href))
    return out

def scrape_dept(base_url, dept_id):
    """抓取一個系所的所有新聞分頁，直到日期早於 CUT。回傳 list of (date, title, url)"""
    results = []
    page = 1
    while True:
        url = base_url if page == 1 else re.sub(r'/news/?$', f'/news/page/{page}/', base_url)
        try:
            html = fetch(url)
        except Exception as e:
            print(f"  [{dept_id}] page {page} 抓取失敗: {e}")
            break

        page_items = parse_page(html, url)
        if not page_items:
            break

        results.extend(page_items)
        page_dates = [d for d, t, u in page_items if d is not None]
        # 若這一頁全部日期都早於 CUT，停止翻頁（無日期版型則用頁數上限把關）
        if page_dates and all(d < CUT for d in page_dates):
            break
        page += 1
        if page > 8:  # 安全上限（無日期版型較保守，避免無限翻頁）
            break
        time.sleep(0.3)
    return results

def norm_title(t):
    return re.sub(r'[\s「」『』、，。：；！？\-－—,.!?:;"\'　]+', '', t)

def best_match(target_title, candidates):
    """candidates: list of (title, url). 回傳最佳匹配的 url 或 None"""
    nt = norm_title(target_title)
    best_url, best_score = None, 0.0
    for title, url in candidates:
        nc = norm_title(title)
        # 完全包含關係優先
        if nt == nc:
            return url
        score = difflib.SequenceMatcher(None, nt, nc).ratio()
        if nt in nc or nc in nt:
            score = max(score, 0.85)
        if score > best_score:
            best_score, best_url = score, url
    return best_url if best_score >= 0.55 else None

def main():
    with open(HTML_FILE, encoding="utf-8") as f:
        html = f.read()

    # 找出 const D=[ ... ]; 區塊
    d_start = html.index("const D=[")
    d_end = html.index("\n];", d_start) + 3
    d_block = html[d_start:d_end]

    # 解析每個系所的 id 與 url
    dept_re = re.compile(r"\{id:'([^']+)',col:'[^']*',name:'[^']*',url:'([^']+)',news:\[([\s\S]*?)\n  \]\},?")
    depts = dept_re.findall(d_block)
    print(f"找到 {len(depts)} 個系所")

    new_d_block = d_block
    total_matched, total_news = 0, 0

    for dept_id, base_url, news_body in depts:
        print(f"抓取中：{dept_id} ({base_url}) ...")
        scraped = scrape_dept(base_url, dept_id)
        print(f"  抓到 {len(scraped)} 篇")

        # 建立候選 list（不分日期，全部一起比對，標題優先）
        candidates_all = [(t, u) for (_, t, u) in scraped]
        candidates_by_date = {}
        for d, t, u in scraped:
            candidates_by_date.setdefault(d, []).append((t, u))

        # 找出這個系所 news 區塊裡的每一條 {d:'...',t:'...'}（尚無 url 的）
        entry_re = re.compile(r"\{d:'([^']+)',t:'((?:[^'\\]|\\.)*)'\}")
        def repl(m):
            nonlocal total_matched, total_news
            total_news += 1
            date, title = m.group(1), m.group(2)
            title_unescaped = title.replace("\\'", "'")
            cands = candidates_by_date.get(date, candidates_all)
            url = best_match(title_unescaped, cands)
            if not url:
                url = best_match(title_unescaped, candidates_all)
            if url:
                total_matched += 1
                return f"{{d:'{date}',t:'{title}',url:'{url}'}}"
            else:
                print(f"    [未配對] {date} {title_unescaped[:30]}")
                return m.group(0)

        new_news_body = entry_re.sub(repl, news_body)
        new_d_block = new_d_block.replace(
            f"{{id:'{dept_id}',col:", f"{{id:'{dept_id}',col:", 1
        )
        old_full = f"news:[{news_body}\n  ]}}"
        new_full = f"news:[{new_news_body}\n  ]}}"
        new_d_block = new_d_block.replace(old_full, new_full, 1)

    html = html[:d_start] + new_d_block + html[d_end:]
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n完成！共 {total_news} 篇新聞，成功配對 {total_matched} 篇網址。")

if __name__ == "__main__":
    main()

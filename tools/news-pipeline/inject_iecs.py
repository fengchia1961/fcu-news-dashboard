# -*- coding: utf-8 -*-
"""
inject_iecs.py — 抓取資訊工程學系 (iecs.fcu.edu.tw) 新聞並注入到儀表板 D 陣列。
可重複執行：若 iecs 已存在則更新，否則插入於 upiee 之後、civil 之前。
"""

# ── 路徑已改為相對本專案（2026-10-01 從「工具程式」資料夾搬入）──
# 本檔位置：fcu-news-dashboard/tools/news-pipeline/
from pathlib import Path as _P
PROJ = _P(__file__).resolve().parents[2]   # fcu-news-dashboard/
HERE = _P(__file__).resolve().parent       # tools/news-pipeline/
DASHBOARD = PROJ / 'index.html'            # 新聞監測儀表板

import re, sys, io
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HTML_FILE = str(DASHBOARD)
CUT       = "2025.08.01"
CUT_END   = "2026.07.31"   # 114學年度上限（2026-08-10 使用者指示）
IECS_URL  = "https://www.iecs.fcu.edu.tw/news/"
UA        = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

PORTO_BLOCK_RE = re.compile(r'<article[^>]*>([\s\S]*?)</article>')
PORTO_TITLE_RE = re.compile(r'<a\s+class="post-title\s*"\s+href="([^"]+)"[^>]*>([^<]+)</a>')
PORTO_DATE_RE  = re.compile(r'class="meta-data">(\d{4}-\d{2}-\d{2})<')

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="ignore")

def scrape_iecs():
    html = fetch(IECS_URL)
    articles = []
    for m in PORTO_BLOCK_RE.finditer(html):
        block = m.group(1)
        tm = PORTO_TITLE_RE.search(block)
        dm = PORTO_DATE_RE.search(block)
        if tm and dm:
            dot_date = dm.group(1).replace('-', '.')
            href     = tm.group(1)
            if href.startswith('/'):
                href = "https://www.iecs.fcu.edu.tw" + href
            title = tm.group(2).strip()
            if CUT <= dot_date <= CUT_END:
                articles.append((dot_date, title, href))
    return articles

def js_str(s):
    """Escape for single-quoted JS string literal."""
    return s.replace('\\', '\\\\').replace("'", "\\'")

def build_entry(articles):
    lines = [
        "  {id:'iecs',col:'ece',name:'資訊工程學系',"
        "url:'https://www.iecs.fcu.edu.tw/news/',extHost:1,news:["
    ]
    for date, title, url in articles:
        lines.append(f"    {{d:'{date}',t:'{js_str(title)}',url:'{url}'}},")
    lines.append("  ]},")
    return '\n'.join(lines)

def main():
    print(f"抓取 {IECS_URL} ...")
    articles = scrape_iecs()
    print(f"  找到 {len(articles)} 篇 post-CUT 文章")

    with open(HTML_FILE, encoding='utf-8') as f:
        html = f.read()

    entry = build_entry(articles)

    if "id:'iecs'" in html:
        # 更新：替換既有 iecs 區塊
        old_re = re.compile(r"  \{id:'iecs',col:'ece'[\s\S]*?\n  \]},")
        if old_re.search(html):
            html = old_re.sub(entry, html, count=1)
            print("已更新既有 iecs 資料")
        else:
            print("WARNING: 找到 id:'iecs' 但無法定位完整區塊，請手動確認。")
            return
    else:
        # 新增：插入於 upiee 之後、civil 之前
        marker = "\n  ]},\n  {id:'civil',"
        if marker not in html:
            print("ERROR: 找不到插入點（upiee 後、civil 前）。D 陣列結構可能已更動。")
            return
        replacement = "\n  ]},\n" + entry + "\n  {id:'civil',"
        html = html.replace(marker, replacement, 1)
        print("已插入新的 iecs 資料")

    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"完成！共 {len(articles)} 篇文章已寫入。")
    # Show newest/oldest for sanity check
    print(f"  最新：{articles[0][0]}  {articles[0][1][:40]}")
    print(f"  最舊：{articles[-1][0]}  {articles[-1][1][:40]}")

if __name__ == "__main__":
    main()

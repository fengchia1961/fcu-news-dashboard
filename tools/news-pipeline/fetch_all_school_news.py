# -*- coding: utf-8 -*-

# ── 路徑已改為相對本專案（2026-10-01 從「工具程式」資料夾搬入）──
# 本檔位置：fcu-news-dashboard/tools/news-pipeline/
from pathlib import Path as _P
PROJ = _P(__file__).resolve().parents[2]   # fcu-news-dashboard/
HERE = _P(__file__).resolve().parent       # tools/news-pipeline/
DASHBOARD = PROJ / 'index.html'            # 新聞監測儀表板

import json, time, re
import urllib.request

API_BASE = "https://www.fcu.edu.tw/wp-json/api/news"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
CUT = "2025-08-01"

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    all_items = []
    offset = 0
    limit = 100
    while True:
        url = f"{API_BASE}?offset={offset}&limit={limit}"
        data = fetch_json(url)
        items = data.get("list", [])
        if not items:
            break
        all_items.extend(items)
        oldest_date = items[-1]["post_date"][:10]
        print(f"offset={offset}: 取得 {len(items)} 篇，最舊日期 {oldest_date}")
        if oldest_date < CUT:
            break
        offset += limit
        time.sleep(0.3)

    # 篩選 CUT 之後的文章
    in_scope = [it for it in all_items if it["post_date"][:10] >= CUT]
    print(f"\n共抓取 {len(all_items)} 篇，CUT（{CUT}）之後共 {len(in_scope)} 篇")

    with open(str(HERE / 'school_news_full.json'), "w", encoding="utf-8") as f:
        json.dump(in_scope, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

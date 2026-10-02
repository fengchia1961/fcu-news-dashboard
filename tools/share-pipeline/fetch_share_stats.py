# -*- coding: utf-8 -*-
import os
from pathlib import Path
HERE = Path(__file__).resolve().parent
PROJ = HERE.parent.parent          # fcu-news-dashboard/
import json, time
import urllib.request
from datetime import datetime

API_BASE = "https://www.fcu.edu.tw/wp-json/api/share"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
CUT = "2025-08-01"

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_all_share():
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
        if len(items) < limit:
            break
        offset += limit
        time.sleep(0.3)
    return all_items

def main():
    items = fetch_all_share()
    total = len(items)
    since_cut = [it for it in items if it["post_date"][:10] >= CUT]

    print(f"=== /share/ 學生愛分享 篇數統計 ===")
    print(f"全站總篇數：{total} 篇")
    print(f"{CUT} 起共：{len(since_cut)} 篇")

    with open(HERE / "share_full.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    with open(HERE / "share_since_cut.json", "w", encoding="utf-8") as f:
        json.dump(since_cut, f, ensure_ascii=False, indent=2)

    print("\n已儲存 share_full.json 與 share_since_cut.json")

if __name__ == "__main__":
    main()

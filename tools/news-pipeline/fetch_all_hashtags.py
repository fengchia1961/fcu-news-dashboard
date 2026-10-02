# -*- coding: utf-8 -*-

# ── 路徑已改為相對本專案（2026-10-01 從「工具程式」資料夾搬入）──
# 本檔位置：fcu-news-dashboard/tools/news-pipeline/
from pathlib import Path as _P
PROJ = _P(__file__).resolve().parents[2]   # fcu-news-dashboard/
HERE = _P(__file__).resolve().parent       # tools/news-pipeline/
DASHBOARD = PROJ / 'index.html'            # 新聞監測儀表板

import json, time, re, sys, io
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
TAG_RE = re.compile(r'class="m-tags__item">#\s*([^<]+?)\s*</a>')

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="ignore")

def get_hashtags(url):
    try:
        html = fetch(url)
    except Exception as e:
        print(f"  失敗 {url}: {e}")
        return []
    return TAG_RE.findall(html)

def main():
    with open(str(HERE / 'school_news_full.json'), encoding="utf-8") as f:
        items = json.load(f)

    print(f"共 {len(items)} 篇，開始抓取 hashtag...")
    result = []
    for i, it in enumerate(items, 1):
        url = it["link"]
        tags = get_hashtags(url)
        date = it["post_date"][:10].replace("-", ".")
        result.append({"d": date, "t": it["title"], "url": url, "cats": tags})
        print(f"[{i}/{len(items)}] {date} {it['title'][:30]} -> {len(tags)} tags")
        time.sleep(0.25)

    with open(str(HERE / 'school_raw_full.json'), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    no_tags = sum(1 for r in result if not r["cats"])
    print(f"\n完成！共 {len(result)} 篇，{no_tags} 篇沒有 hashtag。")

if __name__ == "__main__":
    main()

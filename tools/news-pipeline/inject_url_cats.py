
# ── 路徑已改為相對本專案（2026-10-01 從「工具程式」資料夾搬入）──
# 本檔位置：fcu-news-dashboard/tools/news-pipeline/
from pathlib import Path as _P
PROJ = _P(__file__).resolve().parents[2]   # fcu-news-dashboard/
HERE = _P(__file__).resolve().parent       # tools/news-pipeline/
DASHBOARD = PROJ / 'index.html'            # 新聞監測儀表板

import json, re

HTML_FILE = str(DASHBOARD)

with open(str(HERE / 'url_cats.json'), encoding="utf-8") as f:
    url_cats = json.load(f)

with open(HTML_FILE, encoding="utf-8") as f:
    html = f.read()

js_const = "const URL_CATS=" + json.dumps(url_cats, ensure_ascii=False) + ";\n"

marker = "const SCH_TITLES=new Set(SCHOOL_RAW.map(x=>x.t));"
assert marker in html, "找不到插入點"
html = html.replace(marker, js_const + marker, 1)

with open(HTML_FILE, "w", encoding="utf-8") as f:
    f.write(html)

print("已插入 URL_CATS，共", len(url_cats), "筆")

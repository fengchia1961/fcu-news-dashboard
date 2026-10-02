# -*- coding: utf-8 -*-
"""
repair_dept_urls.py — 把 const D=[...] 中遺失的 url 欄位從快取補回（不連網）。

背景：update_fcu_news.py 的 build_dept_js() 原本沒有輸出 url 欄位，而 update_html()
      是整塊覆蓋 const D=[...]，導致 2026-08-01 執行後全部系所的 url 被洗掉。
      抓取端其實有存 url，只是沒寫回——所以直接從 fcu_news_cache.json 補即可。

用法：python repair_dept_urls.py [--dry-run]

只針對「目前缺 url」的項目補寫，已有 url 者不動；逐筆以 (日期, 標題) 配對。
"""

# ── 路徑已改為相對本專案（2026-10-01 從「工具程式」資料夾搬入）──
# 本檔位置：fcu-news-dashboard/tools/news-pipeline/
from pathlib import Path as _P
PROJ = _P(__file__).resolve().parents[2]   # fcu-news-dashboard/
HERE = _P(__file__).resolve().parent       # tools/news-pipeline/
DASHBOARD = PROJ / 'index.html'            # 新聞監測儀表板

import sys, io, re, json, shutil, datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HTML_FILE = Path(str(DASHBOARD))
CACHE_FILE = Path(str(HERE / 'fcu_news_cache.json'))
BACKUP_DIR = Path(str(HERE / 'backup'))
DRY = '--dry-run' in sys.argv

cache = json.loads(CACHE_FILE.read_text(encoding='utf-8'))
depts_cache = cache.get('depts', {})

raw = HTML_FILE.read_bytes()
has_bom = raw[:3] == b'\xef\xbb\xbf'
html = raw.decode('utf-8-sig')

d_start = html.find('const D=[')
d_end = html.find('\r\n];', d_start)
if d_start < 0 or d_end < 0:
    print('找不到 const D=[...] 區塊'); sys.exit(1)
d_block = html[d_start:d_end]

ENTRY_RE = re.compile(r"\{d:'([^']+)',t:'((?:[^'\\]|\\.)*)'\}")   # 只抓沒有 url 的項目

total_filled = total_missing = 0
report = []
new_block = d_block

for chunk in re.split(r"(?=\{id:')", d_block)[1:]:
    m_id = re.match(r"\{id:'([^']+)'", chunk)
    if not m_id:
        continue
    did = m_id.group(1)
    lookup = {}
    for a in depts_cache.get(did, []):
        if a.get('url'):
            lookup[(a['d'], a['t'])] = a['url']

    filled = missing = 0
    for m in ENTRY_RE.finditer(chunk):
        d, t_esc = m.group(1), m.group(2)
        t = t_esc.replace("\\'", "'")
        url = lookup.get((d, t))
        if url:
            u_esc = url.replace("'", "\\'")
            old = m.group(0)
            new = f"{{d:'{d}',t:'{t_esc}',url:'{u_esc}'}}"
            new_block = new_block.replace(old, new, 1)
            filled += 1
        else:
            missing += 1
    if filled or missing:
        report.append((did, filled, missing))
    total_filled += filled
    total_missing += missing

print(f'{"系所":10s}{"補回":>6s}{"仍缺":>6s}')
print('-' * 24)
for did, f, m in report:
    print(f'{did:10s}{f:6d}{m:6d}')
print('-' * 24)
print(f'{"合計":10s}{total_filled:6d}{total_missing:6d}')

if DRY:
    print('\n[dry-run] 未寫入檔案')
    sys.exit(0)

if total_filled == 0:
    print('\n無需修改')
    sys.exit(0)

stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bak = BACKUP_DIR / f'FCU新聞監測儀表板_backup_{stamp}.html'
shutil.copy2(HTML_FILE, bak)
print(f'\n備份 → {bak}')

html_new = html[:d_start] + new_block + html[d_end:]
out = (b'\xef\xbb\xbf' if has_bom else b'') + html_new.encode('utf-8')
HTML_FILE.write_bytes(out)
print(f'已寫回：補上 {total_filled} 筆 url')

# -*- coding: utf-8 -*-
"""
dedupe_school_raw.py — 清掉校網新聞（SCHOOL_RAW）裡同一篇文章的重複紀錄。

成因（2026-08-07 由使用者在工工系頁面發現）
────────────────────────────────────────
update_fcu_news.py 的 update_school_news() 是用**標題字串**判斷一則校網新聞是否
已經抓過（`known = {s["t"] for s in cache["school"]}`）。校網編輯若事後在標題
尾端多打／刪掉一個全形空白 U+3000，同一個網址就會被當成新文章再存一次：

  https://www.fcu.edu.tw/news/2025123001/
    '逢甲工工系丘紀堇老師榮獲英國FADA冬季賽雙白金'
    '逢甲工工系丘紀堇老師榮獲英國FADA冬季賽雙白金　'   ← 尾端 U+3000

儀表板 D.forEach 的 schOnly 分支只拿 SCHOOL_RAW 去和「該系自有文章」比對去重，
並沒有拿 SCHOOL_RAW 自己去重，所以兩筆都會掛到工工系底下，變成同一則出現兩次，
也讓該系與校級的則數各多算一則。

本腳本做三件事，並同步三個檔案（缺一就會在下次更新被還原回去）：
  ① 去掉標題頭尾的空白（含全形空白 U+3000）
  ② 同一個 url 只保留一筆（保留最早出現的那筆）
  ③ 日期統一成 YYYY-MM-DD（HTML／快取）或維持 YYYY.MM.DD（school_raw_full.json）

治本的部分已改在 update_fcu_news.py：改以 url 去重、寫入前 strip 標題。

用法：
  python dedupe_school_raw.py --dry-run
  python dedupe_school_raw.py
"""

# ── 路徑已改為相對本專案（2026-10-01 從「工具程式」資料夾搬入）──
# 本檔位置：fcu-news-dashboard/tools/news-pipeline/
from pathlib import Path as _P
PROJ = _P(__file__).resolve().parents[2]   # fcu-news-dashboard/
HERE = _P(__file__).resolve().parent       # tools/news-pipeline/
DASHBOARD = PROJ / 'index.html'            # 新聞監測儀表板

import re, io, sys, os, json, shutil, datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HTML = str(DASHBOARD)
CACHE = str(HERE / 'fcu_news_cache.json')
FULL = str(HERE / 'school_raw_full.json')
BAK_DIR = str(HERE / 'backup')
DRY = '--dry-run' in sys.argv

WS = ' \t\r\n\u3000\u00a0'


def clean_title(t):
    return t.strip(WS)


def dedupe(items, keyf=lambda x: x['url']):
    """保留每個 url 第一次出現的那筆，回傳 (結果, 被刪掉的清單)。

    重複兩筆的 cats 若不一致，取聯集併到保留的那筆——否則刪掉的那筆若獨有某個
    hashtag，該系所就會少掉這則校網介接的新聞。
    """
    first, out, dropped = {}, [], []
    for it in items:
        k = keyf(it)
        if k and k in first:
            keep = first[k]
            a, b = keep.get('cats'), it.get('cats')
            if a is not None and b is not None and a != b:
                merged = a + [c for c in b if c not in a]
                print(f'   ⚠ cats 不一致，取聯集：{keep["t"][:24]}')
                print(f'      保留 {a}\n      刪除 {b}\n      合併 {merged}')
                keep['cats'] = merged
            dropped.append(it)
            continue
        if k:
            first[k] = it
        out.append(it)
    return out, dropped


def esc(s):
    return s.replace('\\', '\\\\').replace("'", "\\'")


changed = []

# ── ① 儀表板 HTML 的 const SCHOOL_RAW=[...] ──────────────
raw = open(HTML, 'rb').read()
bom = raw[:3] == b'\xef\xbb\xbf'
src = raw.decode('utf-8-sig').replace('\r\n', '\n')
i = src.find('const SCHOOL_RAW=[')
j = src.find('\n];', i)
if i < 0 or j < 0:
    sys.exit('找不到 const SCHOOL_RAW=[...] 區塊')

rows = []
for m in re.finditer(r"\{d:'([^']+)',t:'((?:[^'\\]|\\.)*)',url:'([^']*)',cats:\[([^\]]*)\]\}", src[i:j]):
    rows.append({'d': m.group(1).replace('.', '-'),
                 't': clean_title(m.group(2)),
                 'url': m.group(3),
                 'cats': re.findall(r"'((?:[^'\\]|\\.)*)'", m.group(4))})
kept, dropped = dedupe(rows)
print(f'HTML SCHOOL_RAW：{len(rows)} → {len(kept)} 筆（刪除 {len(dropped)} 筆重複）')
for d in dropped:
    print(f"   － {d['d']}  {d['t'][:44]}")
    print(f"      {d['url']}")

lines = ['const SCHOOL_RAW=[']
for s in sorted(kept, key=lambda x: x['d'], reverse=True):
    cats = ','.join("'" + esc(c) + "'" for c in s['cats'])
    lines.append(f"  {{d:'{s['d']}',t:'{esc(s['t'])}',url:'{esc(s['url'])}',cats:[{cats}]}},")
lines.append('];')
new_block = '\n'.join(lines)
out_html = src[:i] + new_block + src[j + len('\n];'):]
changed.append(('HTML', len(rows) - len(kept)))

# ── ② fcu_news_cache.json 的 school ─────────────────────
cache = json.load(open(CACHE, encoding='utf-8')) if os.path.exists(CACHE) else None
if cache is not None:
    sc = cache.get('school', [])
    for x in sc:
        x['t'] = clean_title(x['t'])
        x['d'] = x['d'].replace('.', '-')
    sc2, drop2 = dedupe(sc)
    cache['school'] = sorted(sc2, key=lambda x: x['d'], reverse=True)
    print(f'fcu_news_cache.json / school：{len(sc)} → {len(sc2)} 筆（刪除 {len(drop2)}）')
    changed.append(('cache', len(sc) - len(sc2)))

# ── ③ school_raw_full.json（GA4 用，日期維持 YYYY.MM.DD）──
full = json.load(open(FULL, encoding='utf-8')) if os.path.exists(FULL) else None
if isinstance(full, list):
    for x in full:
        x['t'] = clean_title(x['t'])
    full2, drop3 = dedupe(full)
    print(f'school_raw_full.json：{len(full)} → {len(full2)} 筆（刪除 {len(drop3)}）')
    changed.append(('full', len(full) - len(full2)))
else:
    full2 = None

if DRY:
    print('\n[dry-run] 未寫入任何檔案')
    sys.exit(0)

stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
shutil.copy2(HTML, os.path.join(BAK_DIR, f'FCU新聞監測儀表板_backup_{stamp}.html'))
open(HTML, 'wb').write((b'\xef\xbb\xbf' if bom else b'') + out_html.replace('\n', '\r\n').encode('utf-8'))
print(f'\n備份 → FCU新聞監測儀表板_backup_{stamp}.html')
if cache is not None:
    json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
if full2 is not None:
    json.dump(full2, open(FULL, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('三個檔案已同步寫回')

# ── 寫回後自我檢查 ──────────────────────────────────────
chk = open(HTML, 'rb').read().decode('utf-8-sig')
m = re.search(r'const SCHOOL_RAW=\[.*?\n\];', chk, re.S)
urls = re.findall(r"url:'([^']*)',cats:", m.group(0))
print('\n── 寫回後自我檢查 ──')
print(f'   SCHOOL_RAW {len(urls)} 筆，相異網址 {len(set(urls))} 個'
      f'{"（無重複）" if len(urls) == len(set(urls)) else " ⚠ 仍有重複"}')
dblock = re.search(r'const D=\[.*?\n\];', chk, re.S).group(0)
print(f'   D 陣列未受影響：單位 {len(re.findall(chr(123)+"id:", dblock))} 個｜'
      f'文章 {len(re.findall(chr(123)+"d:", dblock))} 篇')
print(f'   彎引號 U+2018/2019：{chk.count(chr(0x2018)) + chk.count(chr(0x2019))} 個（應為 0）')

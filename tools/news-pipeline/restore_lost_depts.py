# -*- coding: utf-8 -*-
"""
restore_lost_depts.py — 還原被 update_fcu_news.py 刪除的系所。

背景：update_fcu_news.py 的 update_html() 整塊重建 const D=[...]，且只依 DEPT_LIST
      產生內容，因此由 inject_new_depts.py / inject_iecs.py 另外加入、不在 DEPT_LIST
      裡的系所，每跑一次就會被刪掉。2026-08-01 該次執行刪掉了 15 個系所、97 篇文章。

本腳本從備份取回那些系所的完整區塊（含已抓到的文章），依原順序插回目前的 D 陣列，
並同步寫進 fcu_news_cache.json，讓日後的更新有基準可比對。

用法：python restore_lost_depts.py [備份HTML] [--dry-run]
"""

# ── 路徑已改為相對本專案（2026-10-01 從「工具程式」資料夾搬入）──
# 本檔位置：fcu-news-dashboard/tools/news-pipeline/
from pathlib import Path as _P
PROJ = _P(__file__).resolve().parents[2]   # fcu-news-dashboard/
HERE = _P(__file__).resolve().parent       # tools/news-pipeline/
DASHBOARD = PROJ / 'index.html'            # 新聞監測儀表板

import sys, io, re, json, shutil, datetime, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HTML = str(DASHBOARD)
CACHE = str(HERE / 'fcu_news_cache.json')
BAK_DIR = str(HERE / 'backup')
SRC = next((a for a in sys.argv[1:] if not a.startswith('--')),
           os.path.join(BAK_DIR, 'FCU新聞監測儀表板_backup_20260713_162221.html'))
DRY = '--dry-run' in sys.argv


def split_depts(html):
    """回傳 [(id, 完整區塊文字), …]，區塊含結尾的 ']},'。"""
    ds = html.find('const D=[')
    de = html.find('\n];', ds)
    body = html[ds + len('const D=['):de]
    out = []
    for part in re.split(r'(?=\n  \{id:\')', body):
        m = re.search(r"\{id:'([^']+)'", part)
        if m:
            out.append((m.group(1), part))
    return out, ds, de


cur_raw = open(HTML, 'rb').read()
has_bom = cur_raw[:3] == b'\xef\xbb\xbf'
cur = cur_raw.decode('utf-8-sig').replace('\r\n', '\n')
old = open(SRC, 'rb').read().decode('utf-8-sig', errors='replace').replace('\r\n', '\n')

cur_list, ds, de = split_depts(cur)
old_list, _, _ = split_depts(old)
cur_ids = [i for i, _ in cur_list]
old_ids = [i for i, _ in old_list]
old_map = dict(old_list)

lost = [i for i in old_ids if i not in cur_ids]
print(f'目前 {len(cur_ids)} 系所；備份 {len(old_ids)} 系所；待還原 {len(lost)} 個')
if not lost:
    print('無需還原'); sys.exit(0)

# 依備份的順序插回：找出每個遺失系所在備份中的前一個「目前也存在」的系所
new_list = list(cur_list)
for did in lost:
    idx = old_ids.index(did)
    anchor = None
    for j in range(idx - 1, -1, -1):
        if old_ids[j] in [i for i, _ in new_list]:
            anchor = old_ids[j]
            break
    block = old_map[did]
    n_art = len(re.findall(r"\{d:'", block))
    if anchor is None:
        new_list.insert(0, (did, block))
        print(f'  + {did:9s}（{n_art} 篇）→ 置於最前')
    else:
        pos = [i for i, _ in new_list].index(anchor) + 1
        new_list.insert(pos, (did, block))
        print(f'  + {did:9s}（{n_art} 篇）→ 接在 {anchor} 之後')

new_D = 'const D=[' + ''.join(b for _, b in new_list) + '\n];'
out = cur[:ds] + new_D + cur[de + len('\n];'):]

# ── 同步 cache ──
cache = json.load(open(CACHE, encoding='utf-8')) if os.path.exists(CACHE) else {'depts': {}}
added_cache = 0
for did in lost:
    arts = []
    for m in re.finditer(r"\{d:'([^']+)',t:'((?:[^'\\]|\\.)*)'(?:,url:'([^']*)')?\}", old_map[did]):
        a = {'d': m.group(1), 't': m.group(2).replace("\\'", "'")}
        if m.group(3):
            a['url'] = m.group(3)
        arts.append(a)
    if arts or did not in cache['depts']:
        cache['depts'][did] = arts
        added_cache += 1

print(f'\ncache 更新 {added_cache} 個系所')
print(f'D 陣列：{len(cur_ids)} → {len(new_list)} 系所')

if DRY:
    print('\n[dry-run] 未寫入'); sys.exit(0)

stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
shutil.copy2(HTML, os.path.join(BAK_DIR, f'FCU新聞監測儀表板_backup_{stamp}.html'))
open(HTML, 'wb').write((b'\xef\xbb\xbf' if has_bom else b'') + out.replace('\n', '\r\n').encode('utf-8'))
json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
print(f'\n備份 → FCU新聞監測儀表板_backup_{stamp}.html')
print('已寫回儀表板與快取')

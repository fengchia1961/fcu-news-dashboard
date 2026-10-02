# -*- coding: utf-8 -*-
"""把 tools/news.json 的統計結果同步進 health-check.html 的 NW／NW_META 常數。

用法：
    node tools/extract-news.js          # 先從 index.html 重算 → tools/news.json
    python tools/sync-news-to-healthcheck.py

冪等：可重複執行；每次會先備份 health-check.html。
對應方式以**網址主機名**比對（兩邊的 id 不完全一致，例如 marketing↔mkt、msc↔imsc）。
"""
import io, json, re, shutil, sys, os, datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
HC = PROJ / 'health-check.html'
NEWS = HERE / 'news.json'
DEPTS = HERE / 'depts.json'

if not NEWS.exists():
    sys.exit('找不到 tools/news.json，請先執行：node tools/extract-news.js')

nj = json.loads(NEWS.read_text(encoding='utf-8'))
dep = json.loads(DEPTS.read_text(encoding='utf-8'))

host = lambda u: re.sub(r'^https?://', '', u or '').split('/')[0].lower()
by_host, by_name = {}, {}
for k, v in nj['depts'].items():
    by_host.setdefault(host(v['url']), v)
    by_name.setdefault(v['name'], v)

data, missing = {}, []
for d in dep:
    v = by_host.get(host(d['url'])) or by_name.get(d['name'])
    if not v:
        missing.append(d['name']); continue
    data[d['id']] = {'cnt': v['cnt'], 'total': v['total'], 'nn': v['nn'], 'fromSch': v['fromSch'],
                     'self': v['self'], 'last': v['last'], 'mavg': v['mavg'],
                     'url': v['url'], 'months': v['months'], 'items': v['items']}
if missing:
    sys.exit('以下學系對應不到新聞資料，請檢查網址：' + '、'.join(missing))

meta = {'cut': nj['cut'], 'cutEnd': nj['cutEnd'], 'tgt': nj['tgt'],
        'months': nj['months'], 'mkeys': nj['mkeys']}

html = HC.read_text(encoding='utf-8')
if '==NEWS_JS_START==' not in html:
    sys.exit('health-check.html 裡找不到新聞成效區塊（==NEWS_JS_START==）')

new_meta = 'const NW_META = ' + json.dumps(meta, ensure_ascii=False, separators=(',', ':')) + ';'
new_data = 'const NW = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';'

html2, n1 = re.subn(r'const NW_META = .*?;\n', lambda _m: new_meta + '\n', html, count=1, flags=re.S)
html2, n2 = re.subn(r'const NW = \{.*?\};\n', lambda _m: new_data + '\n', html2, count=1, flags=re.S)
if not (n1 and n2):
    sys.exit(f'取代失敗（NW_META={n1}, NW={n2}），請檢查 health-check.html 是否被手改過')

bak = HC.with_suffix('.html.bak-news-' + datetime.datetime.now().strftime('%Y%m%d%H%M'))
shutil.copyfile(HC, bak)
HC.write_text(html2, encoding='utf-8', newline='')

tot = sum(v['cnt'] for v in data.values())
print(f'已同步 {len(data)} 個學系｜有效新聞合計 {tot} 則｜統計期間 {meta["cut"]}–{meta["cutEnd"]}')
print('備份：', bak.name)
print('檔案大小：', round(HC.stat().st_size / 1024), 'KB')

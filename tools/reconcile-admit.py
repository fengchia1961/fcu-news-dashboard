# -*- coding: utf-8 -*-
"""讓健檢 DEPTS 與 115 招生系所一覽表（ADMIT_115）完全對得上。

處理三件事（皆冪等）：
 1. 補進一覽表漏列的招生單位（全校國際生大一不分系學士班）
 2. 一個一覽表單位可掛多個健檢網站（did2），例如行銷學系含全球行銷碩士班
 3. 其餘未列入者標註原因（停招／學院網站／當年未招生），不再是來路不明的落差

用法： python tools/reconcile-admit.py
"""
import io, json, re, shutil, sys, datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
HC = Path(__file__).resolve().parent.parent / 'health-check.html'
html = HC.read_text(encoding='utf-8')

m = re.search(r'const ADMIT_115 = (\{.*?\});\n', html, re.S)
if not m:
    sys.exit('找不到 ADMIT_115')
A = json.loads(m.group(1))

# ── 1. 補進漏列的招生單位 ──
NEW_UNITS = [
    ('通識教育中心', {'n': '全校國際生大一不分系學士班', 'did': 'pmp', 'p': ['b'],
                      'note': '只收境外生'}),   # 名額表未列數字，不另掛 q 以免與 note 重複
]
added = []
for col_name, unit in NEW_UNITS:
    col = next((c for c in A['colleges'] if c['name'] == col_name), None)
    if col is None:
        col = {'name': col_name, 'units': []}
        A['colleges'].append(col)
        added.append(f'新增學院區塊：{col_name}')
    cur = next((u for u in col['units'] if u['n'] == unit['n']), None)
    if cur is None:
        col['units'].append(dict(unit))
        added.append(f'{col_name}／{unit["n"]}')
    else:                       # 已存在則同步欄位（移除不該有的殘留）
        cur.clear(); cur.update(unit)
        added.append(f'{col_name}／{unit["n"]}（更新）')

# ── 2. 一個單位對應多個健檢網站 ──
MULTI = {'行銷學系(含全球行銷碩士班)': 'globalmarketing'}
linked = []
for c in A['colleges']:
    for u in c['units']:
        d2 = MULTI.get(u['n'])
        if d2 and u.get('did2') != d2:
            u['did2'] = d2
            linked.append(f'{u["n"]} → {d2}')

# ── 3. 未列入一覽表者標註原因 ──
A['unlisted'] = {
    'nze':  '網站已停用，115 學年度未招生',
    'bmie': '115 學年度未列於招生系所一覽表',
    'msc':  '115 學年度未列於招生系所一覽表',
}

# 學院層級網站：本身不是招生單位，不納入「未列於一覽表」清單
A['nonAdmit'] = ['cocd']

new_const = 'const ADMIT_115 = ' + json.dumps(A, ensure_ascii=False, separators=(',', ':')) + ';\n'
html = html[:m.start()] + new_const + html[m.end():]

# ── 版面：未列入清單改為帶原因，並把 did2 納入已對應判定 ──
OLD = """  const admDids = {};
  ADMIT_115.colleges.forEach(c=>c.units.forEach(u=>{ if(u.did) admDids[u.did]=1; }));
  const missing = DEPTS.filter(d=>!admDids[d.id]);
  if(missing.length){
    html += '<div class="card">' +
      '<div class="card-title"><i class="ti ti-info-circle"></i> 未列於 ' + esc(ADMIT_115.year) + ' 學年度招生一覽表的單位（' + missing.length + '）</div>' +
      '<div class="adm-miss">' + missing.map(d=>'<span>' + esc(d.name) + '</span>').join('') + '</div>' +
      '<div class="adm-src" style="margin-top:6px;">這些單位設有網站並列入健檢，但未出現在 ' + esc(ADMIT_115.year) + ' 學年度招生系所一覽表中。</div>' +
    '</div>';
  }"""

NEW = """  const admDids = {};
  ADMIT_115.colleges.forEach(c=>c.units.forEach(u=>{
    if(u.did) admDids[u.did]=1;
    if(u.did2) admDids[u.did2]=1;
  }));
  const nonAdmit = ADMIT_115.nonAdmit || [];
  const missing = DEPTS.filter(d=>!admDids[d.id] && nonAdmit.indexOf(d.id)<0);
  if(missing.length){
    const un = ADMIT_115.unlisted || {};
    html += '<div class="card">' +
      '<div class="card-title"><i class="ti ti-info-circle"></i> 未列於 ' + esc(ADMIT_115.year) + ' 學年度招生一覽表的單位（' + missing.length + '）</div>' +
      '<div class="adm-miss">' + missing.map(d=>
        '<span>' + esc(d.name) + (un[d.id] ? '<i class="adm-why">' + esc(un[d.id]) + '</i>' : '') + '</span>'
      ).join('') + '</div>' +
      '<div class="adm-src" style="margin-top:6px;">這些單位設有網站並列入健檢，但未出現在 ' + esc(ADMIT_115.year) + ' 學年度招生系所一覽表中；原因如各項後方標註。</div>' +
    '</div>';
  }"""

if OLD in html:
    html = html.replace(OLD, NEW)
    patched = True
else:
    patched = 'adm-why' in html

CSS_MARK = '/* ==ADMIT_WHY_CSS== */'
if CSS_MARK not in html:
    html = html.replace('/* ==ADMIT_CSS_END== */', CSS_MARK + """
.adm-miss span{display:inline-flex;align-items:center;gap:6px;}
.adm-why{font-style:normal;font-size:11px;color:#888780;background:#fff;border:1px solid #e5e4dc;border-radius:7px;padding:0 6px;}
""" + '/* ==ADMIT_CSS_END== */')

bak = HC.with_suffix('.html.bak-reconcile-' + datetime.datetime.now().strftime('%Y%m%d%H%M'))
shutil.copyfile(HC, bak)
HC.write_text(html, encoding='utf-8', newline='')

print('新增招生單位：', added or '（已存在）')
print('多站對應：', linked or '（已存在）')
print('標註原因：', len(A['unlisted']), '個')
print('版面修補：', '已套用' if patched else '⚠ 找不到插入點')
print('備份：', bak.name)

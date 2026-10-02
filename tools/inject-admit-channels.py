# -*- coding: utf-8 -*-
"""把招生管道別（tools/admit-channels.json）併入 health-check.html 的
115 學年度招生系所一覽表（ADMIT_115），並在表格中呈現。

用法：
    python tools/extract-admit-channels.py "<xlsx>"   # 先抽資料
    python tools/inject-admit-channels.py             # 再注入

冪等：可重複執行（資料常數整段取代；版面程式碼有 marker 保護）。
注意：教育部【表7-2】僅涵蓋**日間學制學士班**，故管道別只掛在 p 含 'b' 的單位上。
"""
import io, json, re, shutil, sys, datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
HC = PROJ / 'health-check.html'
CH = HERE / 'admit-channels.json'

# 長名稱 → 表格用短名稱；x=1 代表外加名額
SHORT = {
    ('大學多元入學', '分發入學'): ('分發入學', 0),
    ('大學多元入學', '繁星推薦'): ('繁星推薦', 0),
    ('大學多元入學', '申請入學'): ('申請入學', 0),
    ('四技二專', '甄選入學'): ('四技甄選', 0),
    ('四技二專', '登記分發入學'): ('四技登記分發', 0),
    ('四技二專', '技優入學'): ('四技技優', 0),
    ('運動績優', '甄試'): ('運動績優甄試', 0),
    ('運動績優', '單獨招生'): ('運動績優單招', 0),
    ('單獨招生', '全校單招'): ('全校單招', 0),
    ('單獨招生', '學系單招'): ('學系單招', 0),
    ('單獨招生', '特殊選才'): ('特殊選才', 0),
    ('單獨招生', '其他'): ('單招其他', 0),
    ('原住民考生', '分發入學'): ('原民分發', 1),
    ('原住民考生', '繁星推薦'): ('原民繁星', 1),
    ('原住民考生', '申請入學'): ('原民申請', 1),
    ('原住民考生', '單獨招生'): ('原民單招', 1),
    ('資安學研人才培育計畫', '申請入學'): ('資安學研申請', 1),
    ('資安學研人才培育計畫', '特殊選才'): ('資安學研特殊選才', 1),
    ('青年儲蓄帳戶組', '申請入學'): ('青年儲蓄申請', 1),
    ('青年儲蓄帳戶組', '四技二專'): ('青年儲蓄四技', 1),
    ('四技二專技優入學', '四技二專技優入學'): ('四技技優外加', 1),
}

ch = json.loads(CH.read_text(encoding='utf-8'))
html = HC.read_text(encoding='utf-8')

m = re.search(r'const ADMIT_115 = (\{.*?\});\n', html, re.S)
if not m:
    sys.exit('找不到 ADMIT_115 常數')
A = json.loads(m.group(1))

norm = lambda n: re.sub(r'[（(].*?[)）]', '', n).replace('大學', '').replace('學位學程', '學程').strip()
xl = {norm(u['name']): u for u in ch['units']}

hit, miss, used = 0, [], set()
for c in A['colleges']:
    for u in c['units']:
        u.pop('q', None); u.pop('exp', None); u.pop('ch', None)
        if 'b' not in u['p']:
            continue
        src = xl.get(norm(u['n']))
        if not src:
            miss.append(f"{c['name']}／{u['n']}")
            continue
        used.add(src['name'])
        chans = []
        for x in src['channels']:
            key = (x['g'], x['n'])
            short, ext = SHORT.get(key, (x['n'], 0))
            chans.append({'n': short, 'q': x['q'], 'x': ext})
        chans.sort(key=lambda z: (z['x'], -z['q']))
        u['q'] = src['total']
        if src['expand'] and str(src['expand']).strip('0') not in ('', '.'):
            u['exp'] = src['expand']
        u['ch'] = chans
        hit += 1

A['chScope'] = ch['scope']
A['chSource'] = ch['source']

print(f'學士班單位對應成功 {hit} 個')
for x in miss:
    print('  未對應（一覽表有、名額表無）：', x)
for n in [u['name'] for u in ch['units'] if u['name'] not in used]:
    print('  未使用（名額表有、一覽表無）：', n)

new_const = 'const ADMIT_115 = ' + json.dumps(A, ensure_ascii=False, separators=(',', ':')) + ';\n'
html = html[:m.start()] + new_const + html[m.end():]

# ── 版面：在單位名稱下方加一行管道別 chips（只做一次）──
CSS_MARK = '/* ==ADMIT_CH_CSS== */'
if CSS_MARK not in html:
    css = CSS_MARK + '''
.adm-ch{margin-top:5px;display:flex;flex-wrap:wrap;gap:3px 5px;align-items:center;}
.adm-ch-q{font-size:10.5px;font-weight:800;color:#534AB7;background:#EEEDFE;border:1px solid #d5d2f5;border-radius:8px;padding:1px 7px;white-space:nowrap;}
.adm-ch-i{font-size:10.5px;color:#5F5E5A;background:#f7f6f1;border:1px solid #e5e4dc;border-radius:8px;padding:1px 7px;white-space:nowrap;}
.adm-ch-i.ext{background:#fffbeb;border-color:#fde68a;color:#92400e;}
.adm-ch-i b{color:#1a1a18;font-weight:800;margin-left:1px;}
.adm-ch-lg{font-size:11px;color:#888780;line-height:1.9;}
'''
    html = html.replace('/* ==ADMIT_CSS_END== */', css + '/* ==ADMIT_CSS_END== */')

JS_MARK = '/* ==ADMIT_CH_JS== */'
if JS_MARK not in html:
    js = JS_MARK + '''
/* 115 學士班招生管道別（資料來源：教育部【表7-2】日間學制學士班名額分配表） */
function admChannels(u){
  if(u.q==null && (!u.ch || !u.ch.length)) return '';
  const q = (u.q==null) ? '' :
    '<span class="adm-ch-q">學士班名額 ' + esc(String(u.q)) + (u.exp?'（含擴充 ' + esc(String(u.exp)) + '）':'') + '</span>';
  const chips = (u.ch||[]).map(c=>
    '<span class="adm-ch-i' + (c.x?' ext':'') + '">' + esc(c.n) + '<b>' + c.q + '</b></span>'
  ).join('');
  return '<div class="adm-ch">' + q + chips + '</div>';
}
'''
    html = html.replace('function renderAdmitBody(){', js + 'function renderAdmitBody(){')

OLD_ROW = "      return '<tr><td class=\"n\">' + nameHtml + note + '</td>' + cells + '</tr>';"
NEW_ROW = "      return '<tr><td class=\"n\">' + nameHtml + note + admChannels(u) + '</td>' + cells + '</tr>';"
if OLD_ROW in html:
    html = html.replace(OLD_ROW, NEW_ROW)
elif 'admChannels(u)' not in html:
    sys.exit('找不到表格列的插入點')

# 說明文字（圖例）
LEG_MARK = 'adm-ch-lg'
if 'id="adm-ch-legend"' not in html:
    old = "'<div id=\"adm-body\"></div>'"
    new = ("'<div class=\"card\"><div class=\"card-title\"><i class=\"ti ti-ticket\"></i> 招生管道別說明</div>'"
           " + '<div class=\"adm-ch-lg\" id=\"adm-ch-legend\">各學士班單位名稱下方列出 115 學年度的招生管道與名額："
           "<span class=\"adm-ch-i\">灰底<b>　</b></span> 為內含名額、"
           "<span class=\"adm-ch-i ext\">黃底<b>　</b></span> 為外加名額（原住民、資安學研、青年儲蓄帳戶組等）；"
           "<span class=\"adm-ch-q\">紫底</span> 為該系學士班總名額。<br>"
           "資料來源：' + esc(ADMIT_115.chSource||'') + '（僅涵蓋' + esc(ADMIT_115.chScope||'') + "
           "'，碩博士班與進修學制不在此表範圍）。</div></div>'"
           " + '<div id=\"adm-body\"></div>'")
    if old in html:
        html = html.replace(old, new, 1)
    else:
        print('⚠ 找不到圖例插入點，略過圖例')

bak = HC.with_suffix('.html.bak-admitch-' + datetime.datetime.now().strftime('%Y%m%d%H%M'))
shutil.copyfile(HC, bak)
HC.write_text(html, encoding='utf-8', newline='')
print('已寫入 health-check.html｜備份：', bak.name)
print('檔案大小：', round(HC.stat().st_size / 1024), 'KB')

# -*- coding: utf-8 -*-
"""把招生管道逐條查核結果（tools/channel-check.json）注入 health-check.html
的「招生連結查核」分頁。

用法：
    python tools/check-admission-channels.py      # 先產生查核結果
    python tools/inject-channel-check.py          # 再注入

冪等：可重複執行（資料常數整段取代、版面程式碼有 marker 保護），自動備份。
"""
import io, json, re, shutil, sys, datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
HC = HERE.parent / 'health-check.html'
SRC = HERE / 'channel-check.json'

if not SRC.exists():
    sys.exit('找不到 tools/channel-check.json，請先執行 check-admission-channels.py')

j = json.loads(SRC.read_text(encoding='utf-8'))
data = {}
for did, rows in j['results'].items():
    data[did] = [{
        'n': r['name'],
        'clicks': r['clicks'],
        'path': r['path'],
        'pages': r.get('pages', []),
        'subPages': r.get('subPages', []),
        'ch': [{k: v for k, v in c.items() if k in ('n', 'q', 's', 'why', 'url', 't', 'src')}
               for c in r['channels']],
    } for r in rows]

html = HC.read_text(encoding='utf-8')

CONST = ('const CHK_DATE = ' + json.dumps(j['checked'], ensure_ascii=False) + ';\n'
         + 'const CHK = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n')

if 'const CHK = ' in html:
    html = re.sub(r'const CHK_DATE = .*?;\nconst CHK = \{.*?\};\n', CONST, html, count=1, flags=re.S)
else:
    html = html.replace('function renderAdmission(d){', CONST + '\nfunction renderAdmission(d){', 1)

# ── CSS ──
CSS_MARK = '/* ==CHK_CSS== */'
if CSS_MARK not in html:
    html = html.replace('/* ==ADMISSION_CSS_END== */', CSS_MARK + '''
.chk-tbl{width:100%;border-collapse:collapse;font-size:15px;}
.chk-tbl th{background:#f7f6f1;font-size:13.5px;color:#5F5E5A;font-weight:700;padding:9px 11px;border-bottom:1px solid #e5e4dc;text-align:left;}
.chk-tbl td{padding:9px 11px;border-bottom:1px solid #f0efe9;vertical-align:top;line-height:1.6;}
.chk-tbl tr:last-child td{border-bottom:none;}
.chk-tbl tr:hover td{background:#fcfcfa;}
.chk-ch{font-weight:700;white-space:nowrap;}
.chk-q{text-align:right;width:64px;color:#5F5E5A;white-space:nowrap;font-weight:700;}
.chk-s{width:122px;white-space:nowrap;}
.chk-to{font-size:13.5px;color:#5F5E5A;line-height:1.7;word-break:break-all;}
.chk-to a{color:#185FA5;text-decoration:none;}
.chk-to a:hover{text-decoration:underline;}
.chk-lv{display:inline-block;font-size:13.5px;font-weight:800;border-radius:10px;padding:3px 10px;white-space:nowrap;}
.chk-lv.ok{background:#dcfce7;color:#15803d;}
.chk-lv.wk{background:#fef3c7;color:#b45309;}
.chk-lv.bad{background:#fee2e2;color:#b91c1c;}
.chk-lv.nil{background:#fee2e2;color:#b91c1c;}
.chk-lv.ext{background:#EEEDFE;color:#534AB7;}
.chk-sum{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;}
.chk-pill{font-size:13.5px;font-weight:700;border-radius:9px;padding:4px 12px;background:#f7f6f1;border:1px solid #e5e4dc;color:#5F5E5A;}
.chk-pages{font-size:13px;color:#5F5E5A;line-height:1.8;margin-top:8px;}
.chk-pages a{color:#185FA5;text-decoration:none;}
@media(max-width:620px){.chk-tbl .chk-q{display:none;}}
''' + '/* ==ADMISSION_CSS_END== */')

# ── 版面：在招生連結查核分頁最後加一張卡 ──
JS_MARK = '/* ==CHK_JS== */'
if True:
    js = JS_MARK + '''
/* 115 學年度招生管道逐條查核 */
function chkCard(d){
  const rows = CHK[d.id];
  if(!rows || !rows.length) return '';
  const LV = {ok:'✓ 連結正確', wk:'△ 連結待修正', bad:'✗ 連結失效', nil:'— 無對應連結', ext:'＋ 外加名額'};
  return rows.map(r=>{
    const n = {ok:0,wk:0,bad:0,nil:0,ext:0};
    r.ch.forEach(c=>{ n[c.s] = (n[c.s]||0)+1; });
    const pills = [
      n.ok ? `<span class="chk-pill" style="color:#15803d;">✓ 連結正確 ${n.ok}</span>`:'',
      n.wk ? `<span class="chk-pill" style="color:#b45309;">△ 連結待修正 ${n.wk}</span>`:'',
      n.bad? `<span class="chk-pill" style="color:#b91c1c;">✗ 連結失效 ${n.bad}</span>`:'',
      n.nil? `<span class="chk-pill" style="color:#b91c1c;">— 無對應連結 ${n.nil}</span>`:'',
      n.ext? `<span class="chk-pill" style="color:#534AB7;">＋ 外加名額 ${n.ext}</span>`:'',
      `<span class="chk-pill">${r.clicks ? r.clicks + ' 次點擊可達招生頁' : '找不到招生頁入口'}</span>`,
    ].filter(Boolean).join('');
    const body = r.ch.map(c=>`<tr>
      <td class="chk-ch">${esc(c.n)}</td>
      <td class="chk-q">${c.q} 名</td>
      <td class="chk-s"><span class="chk-lv ${esc(c.s)}">${esc(LV[c.s]||c.s)}</span></td>
      <td class="chk-to">${c.url
          ? `<a href="${esc(safeUrl(c.url))}" target="_blank" rel="noopener noreferrer">${esc(c.t||c.url)}</a><br><span style="color:#888780;">${esc(c.url)}</span>${
              c.why ? `<br><span style="color:#b45309;">${esc(c.why)}</span>` : ''}`
          : esc(c.why||'')}</td>
      <td class="chk-to">${c.src
          ? `<a href="${esc(safeUrl(c.src))}" target="_blank" rel="noopener noreferrer">${esc(c.src.replace(/^https?:\/\//,''))}</a>`
          : (c.s === 'nil' && r.pages && r.pages.length
             ? `<span style="color:#888780;">建議補於</span><br><a href="${esc(safeUrl(r.pages[0]))}" target="_blank" rel="noopener noreferrer">${esc(r.pages[0].replace(/^https?:\/\//,''))}</a>`
             : '<span style="color:#B4B2A9;">—</span>')}</td>
    </tr>`).join('');
    return `<div class="card">
      <div class="sec-lbl"><i class="ti ti-list-check"></i> 115 學年度招生管道逐條查核${rows.length>1?'：'+esc(r.n):''}
        <span style="margin-left:auto;font-size:11px;font-weight:600;color:#888780;text-transform:none;letter-spacing:0;">查核日期 ${esc(CHK_DATE)}</span></div>
      <div class="chk-sum">${pills}</div>
      <table class="chk-tbl"><thead><tr>
        <th>招生管道</th><th class="chk-q">名額</th><th class="chk-s">查核結果</th><th>對應連結</th><th>連結所在頁面</th>
      </tr></thead><tbody>${body}</tbody></table>
      <div class="chk-pages">招生頁入口路徑：${esc(r.path||'—')}
        <br>本次查核的招生頁（${(r.pages||[]).length}）：${
        (r.pages||[]).map(p=>`<a href="${esc(safeUrl(p))}" target="_blank" rel="noopener noreferrer">${esc(p.replace(/^https?:\/\//,''))}</a>`).join('、') || '—'}${
        (r.subPages||[]).length ? `<br>一併查核的子頁（${r.subPages.length}）：${
          r.subPages.map(p=>`<a href="${esc(safeUrl(p))}" target="_blank" rel="noopener noreferrer">${esc(p.replace(/^https?:\/\//,''))}</a>`).join('、')}` : ''}
        <br>「＋ 外加名額」指原住民、資安學研人才培育計畫、青年儲蓄帳戶組等名額，隨主管道一併報名，系網無須另設連結，不列入缺漏計算。</div>
    </div>`;
  }).join('');
}
'''
    if JS_MARK in html:      # 已存在則整段取代，確保版面改版會生效
        html = re.sub(r'/\* ==CHK_JS== \*/.*?(?=function renderAdmission\(d\)\{)',
                      js, html, count=1, flags=re.S)
    else:
        html = html.replace('function renderAdmission(d){', js + 'function renderAdmission(d){', 1)

# 先清掉既有的呼叫（避免重複注入），再補回唯一一處
html = html.replace('  h += chkCard(d);\n\n', '')
OLD = "  el.innerHTML = h;\n}\n/* ==ADMISSION_JS_END== */"
NEW = "  h += chkCard(d);\n\n  el.innerHTML = h;\n}\n/* ==ADMISSION_JS_END== */"
if OLD not in html:
    sys.exit('找不到 renderAdmission 的插入點')
html = html.replace(OLD, NEW)

bak = HC.with_suffix('.html.bak-chk-' + datetime.datetime.now().strftime('%Y%m%d%H%M'))
shutil.copyfile(HC, bak)
HC.write_text(html, encoding='utf-8', newline='')

tot = {}
for rows in data.values():
    for r in rows:
        for c in r['ch']:
            tot[c['s']] = tot.get(c['s'], 0) + 1
print(f'已注入 {len(data)} 個學系的管道查核結果')
print('管道別統計：', tot)
print('備份：', bak.name, '｜檔案', round(HC.stat().st_size/1024), 'KB')

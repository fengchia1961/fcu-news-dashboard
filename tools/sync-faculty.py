# -*- coding: utf-8 -*-
"""把 tools/faculty.json（師資照片與個人頁查核）注入 health-check.html 的
「📷 師資查核」分頁（排在招生連結查核之後）。

用法：
    python tools/check-faculty.py inde            # 1. 查核
    python tools/sync-faculty.py                  # 2. 注入

冪等：資料常數與版面程式碼每次整段取代（marker 保護），分頁按鈕／面板／render
呼叫只在不存在時插入。每次執行前自動備份 health-check.html。
"""
import json, re, shutil, sys, datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
HC = HERE.parent / 'health-check.html'
SRC = HERE / 'faculty.json'

if not SRC.exists():
    sys.exit('找不到 tools/faculty.json，請先執行：python tools/check-faculty.py <學系id>')

j = json.loads(SRC.read_text(encoding='utf-8'))
depts = j['depts']
html = HC.read_text(encoding='utf-8')

# ══════════════════════════════════════════════════════════════════
# 1. CSS
# ══════════════════════════════════════════════════════════════════
CSS = '''/* ==FACULTY_CSS_START== */
/* ── 師資查核分頁 ── */
.fa-stats{display:flex;gap:8px;flex-wrap:wrap;}
.fa-stat{flex:1;min-width:104px;background:#f7f6f1;border:1px solid #e5e4dc;border-radius:9px;padding:9px 11px;text-align:center;}
.fa-stat-n{font-size:23px;font-weight:800;line-height:1.1;}
.fa-stat-l{font-size:11px;color:#888780;margin-top:3px;line-height:1.5;}
.fa-note{background:#F4F7FB;border:1px solid #CFE0F0;border-radius:9px;padding:10px 13px;margin-top:11px;font-size:12px;color:#5F5E5A;line-height:1.85;}
.fa-note b{color:#185FA5;}
.fa-tools{display:flex;gap:6px;flex-wrap:wrap;margin-left:auto;}
.fa-tools button{font-size:11px;font-weight:700;padding:3px 10px;border-radius:7px;border:1px solid #d3d1c7;background:#fff;color:#5F5E5A;cursor:pointer;text-transform:none;letter-spacing:0;font-family:inherit;}
.fa-tools button.on{background:#185FA5;border-color:#185FA5;color:#fff;}
.fa-tbl{width:100%;border-collapse:collapse;font-size:13px;}
.fa-tbl th{background:#f7f6f1;font-size:11.5px;color:#5F5E5A;font-weight:700;padding:7px 8px;border-bottom:1px solid #e5e4dc;text-align:left;white-space:nowrap;}
.fa-tbl td{padding:7px 8px;border-bottom:1px solid #f0efe9;vertical-align:middle;line-height:1.6;}
.fa-tbl tr:last-child td{border-bottom:none;}
.fa-tbl tr:hover td{background:#fcfcfa;}
.fa-tbl tr.bad td{background:#FDF6F6;}
.fa-tbl tr.bad:hover td{background:#FBEFEF;}
.fa-th{width:52px;}
.fa-img{width:44px;height:44px;border-radius:7px;object-fit:cover;border:1px solid #e5e4dc;display:block;background:#f0efe8;}
.fa-noimg{width:44px;height:44px;border-radius:7px;border:1px dashed #E1B4B4;display:flex;align-items:center;justify-content:center;font-size:10px;color:#b91c1c;background:#FDECEC;text-align:center;line-height:1.2;}
.fa-nm{font-weight:700;color:#1a1a18;white-space:nowrap;}
.fa-nm a{color:#185FA5;text-decoration:none;}
.fa-nm a:hover{text-decoration:underline;}
.fa-job{font-size:11px;color:#888780;white-space:nowrap;}
.fa-num{width:78px;font-size:11.5px;color:#5F5E5A;white-space:nowrap;text-align:right;font-variant-numeric:tabular-nums;}
.fa-ok{display:inline-block;width:17px;height:17px;border-radius:50%;background:#EDF8F1;color:#15803d;font-size:11px;font-weight:800;text-align:center;line-height:17px;}
.fa-no{display:inline-block;width:17px;height:17px;border-radius:50%;background:#FDECEC;color:#b91c1c;font-size:11px;font-weight:800;text-align:center;line-height:17px;}
.fa-fl{width:38px;text-align:center;}
.fa-sp{width:140px;font-size:11.5px;color:#5F5E5A;}
.fa-cnt{display:inline-block;min-width:17px;height:17px;border-radius:9px;background:#EAF1FA;color:#185FA5;font-size:11px;font-weight:800;text-align:center;line-height:17px;padding:0 5px;}
.fa-sp-t{margin-top:2px;line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
.fa-iss{font-size:12px;color:#b45309;line-height:1.7;min-width:160px;}
.fa-iss .sev{color:#b91c1c;font-weight:700;}
.fa-iss .dim{color:#888780;}
.fa-sub{font-size:11.5px;color:#888780;line-height:1.7;}
.fa-pend{background:#FDF8EC;border:1px solid #F2DCA8;border-radius:9px;padding:12px 14px;font-size:13px;color:#5F5E5A;line-height:1.85;}
@media(max-width:700px){
  /* 窄螢幕只留照片、姓名與判讀；尺寸、清晰度、專長、學歷在桌機上看 */
  .fa-tbl .fa-num,.fa-tbl .fa-sp{display:none;}
  .fa-tbl th,.fa-tbl td{padding:6px 5px;}
  .fa-iss{min-width:0;}
}
/* ==FACULTY_CSS_END== */
'''
if '==FACULTY_CSS_START==' in html:
    html = re.sub(r'/\* ==FACULTY_CSS_START==.*?/\* ==FACULTY_CSS_END== \*/\n', CSS, html,
                  count=1, flags=re.S)
else:
    anchor = '/* ==NEWS_CSS_START== */'
    assert anchor in html, '找不到 CSS 插入位置（==NEWS_CSS_START==）'
    html = html.replace(anchor, CSS + anchor, 1)

# ══════════════════════════════════════════════════════════════════
# 2. 資料常數 + 版面
# ══════════════════════════════════════════════════════════════════
CONST = ('const FA_BUILT = ' + json.dumps(j.get('built', ''), ensure_ascii=False) + ';\n'
         + 'const FA = ' + json.dumps(depts, ensure_ascii=False, separators=(',', ':')) + ';\n')

JS = '''/* ═══════════════════════════════════════════════════════
   師資查核分頁  ==FACULTY_JS_START==
   資料由 tools/check-faculty.py 實際抓各系 /teachers/ 與師資個人頁產生：
   照片取自校網 API（wp-json/api/v1/get_teacher_thumb），逐張做人臉偵測、
   臉部清晰度（Laplacian 變異數）與頭頂留白計算；個人頁則檢查有無專長與學歷。
   更新：python tools/check-faculty.py <學系id> && python tools/sync-faculty.py
═══════════════════════════════════════════════════════ */
__CONST__function FA_ON(d){ return !!FA[d.id]; }

let FA_CUR = null, FA_FILTER = 'all';   // all | photo | detail
function faSetFilter(mode){
  FA_FILTER = mode;
  const d = DEPTS.find(x=>x.id===FA_CUR);
  if(d) renderFaculty(d);
}

function faPhotoIssues(r){ return (r.issues||[]).filter(i=>i.indexOf('個人頁')<0); }

function faRow(r){
  const p = r.photo || {};
  const pi = faPhotoIssues(r);
  const bad = pi.length || !r.detail.spec || !r.detail.edu;
  const img = p.has && p.thumb
    ? `<img class="fa-img" alt="${esc(r.name)}" src="data:image/jpeg;base64,${p.thumb}">`
    : `<div class="fa-noimg">無<br>照片</div>`;
  const nums = p.has
    ? `${p.w}×${p.h}<br><span style="color:#B4B2A9;">臉寬 ${p.facePx||0}px</span>`
    : '<span style="color:#B4B2A9;">—</span>';
  const qual = p.has
    ? `${p.faceBlur != null ? p.faceBlur : '—'}<br><span style="color:#B4B2A9;">頭頂 ${p.topGap != null ? Math.round(p.topGap*100)+'%' : '—'}</span>`
    : '<span style="color:#B4B2A9;">—</span>';
  const nt = (r.notes||[]).map(i=>`<span class="dim">${esc(i)}</span>`).join('<br>');
  const iss = (pi.length ? pi.map(i=>`<span class="sev">${esc(i)}</span>`).join('<br>')
                         : '<span class="dim">✓ 未發現異常</span>')
            + (nt ? '<br>' + nt : '');
  return `<tr class="${bad?'bad':''}">
    <td class="fa-th">${img}</td>
    <td><div class="fa-nm">${r.url ? `<a href="${esc(safeUrl(r.url))}" target="_blank" rel="noopener noreferrer">${esc(r.name)} ↗</a>` : esc(r.name)}</div>
        <div class="fa-job">${esc(r.job||'')}</div></td>
    <td class="fa-num">${nums}</td>
    <td class="fa-num">${qual}</td>
    <td class="fa-sp">${r.detail.spec
        ? `<span class="fa-cnt">${r.detail.nSpec}</span><div class="fa-sp-t" title="${esc((r.detail.specs||[]).join('、'))}">${esc((r.detail.specs||[]).join('、'))}</div>`
        : '<span class="fa-no">✕</span>'}</td>
    <td class="fa-sp">${r.detail.edu
        ? `<span class="fa-cnt">${r.detail.nEdu}</span><div class="fa-sp-t" title="${esc(r.detail.topEdu)}">${esc(r.detail.topEdu)}</div>`
        : '<span class="fa-no">✕</span>'}</td>
    <td class="fa-iss">${iss}</td>
  </tr>`;
}

function renderFaculty(d){
  const el = document.getElementById('tpfac');
  if(!el) return;
  FA_CUR = d.id;
  const f = FA[d.id];
  if(!f){
    el.innerHTML = `<div class="card"><div class="fa-pend">
      <strong><i class="ti ti-clock" style="color:#BA7517;"></i> 本系尚未進行師資查核。</strong><br>
      師資查核逐系進行中，完成後會在此顯示。查核內容：師資照片是否缺漏／模糊／頭部太貼近上緣，
      以及師資個人頁是否至少具備「專長」與「學歷」。
    </div></div>`;
    return;
  }
  const rows = f.rows || [];
  const noPhoto = rows.filter(r=>!r.photo.has).length;
  const badPhoto = rows.filter(r=>r.photo.has && faPhotoIssues(r).length).length;
  const noSpec = rows.filter(r=>!r.detail.spec).length;
  const noEdu = rows.filter(r=>!r.detail.edu).length;
  const shown = FA_FILTER === 'photo' ? rows.filter(r=>faPhotoIssues(r).length)
              : FA_FILTER === 'detail' ? rows.filter(r=>!r.detail.spec || !r.detail.edu)
              : rows;

  let h = `<div class="card">
    <div class="sec-lbl"><i class="ti ti-users-group"></i> 師資資料查核
      <span style="margin-left:auto;font-size:11px;font-weight:600;color:#888780;text-transform:none;letter-spacing:0;">查核日期 ${esc(f.checked||'')}</span>
    </div>
    <div class="fa-stats">
      <div class="fa-stat"><div class="fa-stat-n" style="color:#185FA5;">${rows.length}</div><div class="fa-stat-l">師資人數</div></div>
      <div class="fa-stat"><div class="fa-stat-n" style="color:${noPhoto?'#E24B4A':'#1D9E75'};">${noPhoto}</div><div class="fa-stat-l">缺照片</div></div>
      <div class="fa-stat"><div class="fa-stat-n" style="color:${badPhoto?'#BA7517':'#1D9E75'};">${badPhoto}</div><div class="fa-stat-l">照片有疑慮</div></div>
      <div class="fa-stat"><div class="fa-stat-n" style="color:${noSpec?'#E24B4A':'#1D9E75'};">${noSpec}</div><div class="fa-stat-l">個人頁缺專長</div></div>
      <div class="fa-stat"><div class="fa-stat-n" style="color:${noEdu?'#E24B4A':'#1D9E75'};">${noEdu}</div><div class="fa-stat-l">個人頁缺學歷</div></div>
    </div>
    <div class="fa-note">
      <b>判讀方式</b>：照片取自校網師資照片 API（與系網顯示的同一張），逐張做人臉偵測。
      <b>只標示兩種照片問題：明顯模糊與頭太貼近上緣</b>（不夠銳利但看得清楚的不算問題）。
      <b>清晰度</b>只量臉部區域的 Laplacian 變異數（整張算會被大片純色背景拉低，全身照會被誤判成模糊），
      低於 40 判「明顯模糊／失焦」；<b>頭頂</b>是臉框上緣距照片頂端的比例，低於 10% 判「太貼近上緣」。
      灰字是參考資訊，不計入問題數。
      <b>專長／學歷</b>查的是「More」點進去的師資個人頁實際顯示的內容（個人頁的專長、學歷、經歷、著作
      都是由校網師資 API 即時帶入，直接抓網頁原始碼只會看到「基本資訊」的空殼）；數字是筆數。
      數值一併列出供人工覆核，<b>判讀僅供排序參考，最終仍請目視確認</b>。
    </div>
  </div>`;

  h += `<div class="card">
    <div class="sec-lbl"><i class="ti ti-list-check"></i> 師資逐位查核（${shown.length}／${rows.length} 位）
      <span class="fa-tools">
        <button class="${FA_FILTER==='all'?'on':''}" onclick="faSetFilter('all')">全部 ${rows.length}</button>
        <button class="${FA_FILTER==='photo'?'on':''}" onclick="faSetFilter('photo')">照片有疑慮 ${noPhoto+badPhoto}</button>
        <button class="${FA_FILTER==='detail'?'on':''}" onclick="faSetFilter('detail')">個人頁不全 ${rows.filter(r=>!r.detail.spec||!r.detail.edu).length}</button>
      </span>
    </div>
    <table class="fa-tbl"><thead><tr>
      <th class="fa-th">照片</th><th>姓名／職稱</th>
      <th class="fa-num">尺寸</th><th class="fa-num">臉部清晰度</th>
      <th class="fa-sp" title="師資個人頁顯示的專長">專長</th>
      <th class="fa-sp" title="師資個人頁顯示的學歷（取最高學歷）">學歷</th>
      <th>照片判讀</th>
    </tr></thead><tbody>${shown.map(faRow).join('')}</tbody></table>
    <div class="fa-sub" style="margin-top:10px;">
      資料來源：<a href="${esc(safeUrl(f.url))}" target="_blank" rel="noopener noreferrer">${esc(f.url)} ↗</a>
      ｜縮圖為臉部裁切後的縮圖，點姓名可開啟該師資的個人頁。
      ｜紅底列代表照片或個人頁內容有待處理事項。
    </div>
  </div>`;
  el.innerHTML = h;
}
/* ==FACULTY_JS_END== */
'''.replace('__CONST__', CONST)

JS_ANCHOR = ('/* ═══════════════════════════════════════════════════════\n'
             '   學生愛分享分頁  ==SHARE_JS_START==')
if '==FACULTY_JS_START==' in html:
    html, n = re.subn(r'/\* ═+\n   師資查核分頁  ==FACULTY_JS_START==.*?/\* ==FACULTY_JS_END== \*/\n',
                      JS, html, count=1, flags=re.S)
    if not n:
        sys.exit('取代 FACULTY_JS 區塊失敗，請檢查 health-check.html 是否被手改過')
else:
    assert JS_ANCHOR in html, '找不到 JS 插入位置（==SHARE_JS_START==）'
    html = html.replace(JS_ANCHOR, JS + '\n' + JS_ANCHOR, 1)

# ══════════════════════════════════════════════════════════════════
# 3. 分頁按鈕、面板、render 呼叫（排在招生連結查核之後）
#    ⚠ switchTab 靠 DOM 索引對位，按鈕與面板順序必須一致
# ══════════════════════════════════════════════════════════════════
BTN_OLD = """    ${ADM_ON(d)?`<button class="tab" onclick="switchTab('tpadm')">🔗 招生連結查核</button>`:''}"""
BTN_NEW = BTN_OLD + """
    <button class="tab" onclick="switchTab('tpfac')">📷 師資查核</button>"""
if "switchTab('tpfac')" not in html:
    assert BTN_OLD in html, '找不到分頁按鈕插入位置'
    html = html.replace(BTN_OLD, BTN_NEW, 1)

PANEL_OLD = '''  ${ADM_ON(d)?`<div class="tab-panel" id="tpadm"></div>`:``}'''
PANEL_NEW = PANEL_OLD + '''
  <div class="tab-panel" id="tpfac"></div>'''
if 'id="tpfac"' not in html:
    assert PANEL_OLD in html, '找不到分頁面板插入位置'
    html = html.replace(PANEL_OLD, PANEL_NEW, 1)

CALL_OLD = '  // 招生連結查核分頁\n  renderAdmission(d);\n'
CALL_NEW = CALL_OLD + '\n  // 師資查核分頁\n  renderFaculty(d);\n'
# 注意：不能用 'renderFaculty(d);' 當判斷依據——上面注入的 JS 區塊裡也有一個
# （faSetFilter 內的 if(d) renderFaculty(d);），會讓這段永遠不被插入。
if '  // 師資查核分頁\n' not in html:
    assert CALL_OLD in html, '找不到 renderFaculty 呼叫插入位置'
    html = html.replace(CALL_OLD, CALL_NEW, 1)

bak = HC.with_suffix('.html.bak-fac-' + datetime.datetime.now().strftime('%Y%m%d%H%M'))
shutil.copyfile(HC, bak)
HC.write_text(html, encoding='utf-8', newline='')

tot = sum(len(v['rows']) for v in depts.values())
print('已注入 %d 個學系、%d 位師資的查核結果' % (len(depts), tot))
for k, v in depts.items():
    rows = v['rows']
    npho = sum(1 for r in rows if not r['photo']['has'])
    bad = sum(1 for r in rows if r['photo']['has'] and any('個人頁' not in i for i in r['issues']))
    ns = sum(1 for r in rows if not r['detail']['spec'])
    ne = sum(1 for r in rows if not r['detail']['edu'])
    print('   %-10s %-24s 師資 %d｜缺照片 %d｜照片有疑慮 %d｜缺專長 %d｜缺學歷 %d'
          % (k, v['name'], len(rows), npho, bad, ns, ne))
print('備份：', bak.name)
print('檔案大小：', round(HC.stat().st_size / 1024), 'KB')

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
.fa-stat{flex:1;min-width:112px;background:#f7f6f1;border:1px solid #e5e4dc;border-radius:9px;padding:9px 11px;text-align:center;}
.fa-stat-n{font-size:23px;font-weight:800;line-height:1.1;}
.fa-stat-l{font-size:12.5px;color:#888780;margin-top:3px;line-height:1.5;}
.fa-note{background:#F4F7FB;border:1px solid #CFE0F0;border-radius:9px;padding:12px 15px;margin-top:11px;font-size:13.5px;color:#5F5E5A;line-height:1.85;}
.fa-note b{color:#185FA5;}
.fa-tools{display:flex;gap:6px;flex-wrap:wrap;margin-left:auto;}
.fa-tools button{font-size:13px;font-weight:700;padding:5px 13px;border-radius:7px;border:1px solid #d3d1c7;background:#fff;color:#5F5E5A;cursor:pointer;text-transform:none;letter-spacing:0;font-family:inherit;}
.fa-tools button.on{background:#185FA5;border-color:#185FA5;color:#fff;}
.fa-tbl{width:100%;border-collapse:collapse;font-size:15px;}
.fa-tbl th{background:#f7f6f1;font-size:13.5px;color:#5F5E5A;font-weight:700;padding:9px 11px;border-bottom:1px solid #e5e4dc;text-align:left;white-space:nowrap;}
.fa-tbl td{padding:9px 11px;border-bottom:1px solid #f0efe9;vertical-align:middle;line-height:1.6;}
.fa-tbl tr:last-child td{border-bottom:none;}
.fa-tbl tr:hover td{background:#fcfcfa;}
.fa-tbl tr.bad td{background:#FDF6F6;}
.fa-tbl tr.bad:hover td{background:#FBEFEF;}
.fa-th{width:62px;}
.fa-img{width:54px;height:54px;border-radius:7px;object-fit:cover;border:1px solid #e5e4dc;display:block;background:#f0efe8;}
.fa-noimg{width:54px;height:54px;border-radius:7px;border:1px dashed #E1B4B4;display:flex;align-items:center;justify-content:center;font-size:11.5px;color:#b91c1c;background:#FDECEC;text-align:center;line-height:1.2;}
.fa-nm{font-weight:700;color:#1a1a18;white-space:nowrap;}
.fa-nm a{color:#185FA5;text-decoration:none;}
.fa-nm a:hover{text-decoration:underline;}
.fa-job{font-size:12.5px;color:#888780;white-space:nowrap;}
.fa-num{width:96px;font-size:13px;color:#5F5E5A;white-space:nowrap;text-align:right;font-variant-numeric:tabular-nums;}
.fa-ok{display:inline-block;width:20px;height:20px;border-radius:50%;background:#EDF8F1;color:#15803d;font-size:12.5px;font-weight:800;text-align:center;line-height:20px;}
.fa-no{display:inline-block;width:20px;height:20px;border-radius:50%;background:#FDECEC;color:#b91c1c;font-size:12.5px;font-weight:800;text-align:center;line-height:20px;}
.fa-fl{width:44px;text-align:center;}
.fa-sp{width:172px;font-size:13px;color:#5F5E5A;}
.fa-na{display:inline-block;font-size:11.5px;font-weight:700;color:#888780;background:#f0efe8;border-radius:9px;padding:2px 9px;white-space:nowrap;}
.fa-cnt{display:inline-block;min-width:20px;height:20px;border-radius:10px;background:#EAF1FA;color:#185FA5;font-size:12.5px;font-weight:800;text-align:center;line-height:20px;padding:0 6px;}
.fa-sp-t{margin-top:2px;line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
.fa-iss{font-size:13.5px;color:#b45309;line-height:1.7;min-width:180px;}
.fa-iss .sev{color:#b91c1c;font-weight:700;}
.fa-iss .dim{color:#888780;}
.fa-sub{font-size:13px;color:#888780;line-height:1.7;}
.fa-pend{background:#FDF8EC;border:1px solid #F2DCA8;border-radius:9px;padding:14px 16px;font-size:15.5px;color:#5F5E5A;line-height:1.85;}
/* 師資類別 vs 選單結構 */
.fa-mn{display:flex;gap:7px;flex-wrap:wrap;margin-top:4px;}
.fa-cat{display:inline-flex;align-items:center;gap:6px;border-radius:9px;padding:5px 13px;font-size:13.5px;font-weight:700;border:1px solid #e5e4dc;background:#f7f6f1;color:#5F5E5A;white-space:nowrap;}
.fa-cat.ok{background:#EDF8F1;border-color:#BFE3CD;color:#15803d;}
.fa-cat.miss{background:#FDECEC;border-color:#F0C2C2;color:#b91c1c;}
.fa-cat.ext{background:#FDF8EC;border-color:#F2DCA8;color:#b45309;}
.fa-cat b{font-weight:800;}
.fa-cat .n{font-weight:400;color:#888780;font-size:12.5px;}
.fa-mn-h{font-size:13px;font-weight:700;color:#888780;margin:12px 0 2px;}
.fa-mn-ok{background:#EDF8F1;border:1px solid #BFE3CD;border-radius:9px;padding:11px 14px;margin-top:11px;font-size:15.5px;color:#15803d;line-height:1.75;}
.fa-mn-bad{background:#FDECEC;border:1px solid #F0C2C2;border-radius:9px;padding:11px 14px;margin-top:11px;font-size:15.5px;color:#b91c1c;line-height:1.75;}
@media(max-width:860px){
  /* 窄螢幕只留照片、姓名與判讀；尺寸、清晰度、專長、學歷在桌機上看 */
  .fa-tbl .fa-num,.fa-tbl .fa-sp{display:none;}
  .fa-tbl th,.fa-tbl td{padding:6px 5px;}
  .fa-iss{min-width:0;}
}
/* ==FACULTY_CSS_END== */
'''
if '==FACULTY_CSS_START==' in html:
    html = re.sub(r'/\* ==FACULTY_CSS_START==.*?/\* ==FACULTY_CSS_END== \*/\n', lambda _m: CSS, html,
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
    <td class="fa-sp">${!r.detail.ok
        ? ((r.cardSpecs||[]).length
            ? `<span class="fa-na">列表卡片</span><div class="fa-sp-t" title="${esc(r.cardSpecs.join('、'))}">${esc(r.cardSpecs.join('、'))}</div>`
            : '<span class="fa-na">無法查核</span>')
        : r.detail.spec
        ? `<span class="fa-cnt">${r.detail.nSpec}</span><div class="fa-sp-t" title="${esc((r.detail.specs||[]).join('、'))}">${esc((r.detail.specs||[]).join('、'))}</div>`
        : '<span class="fa-no">✕</span>'}</td>
    <td class="fa-sp">${!r.detail.ok ? '<span class="fa-na">無法查核</span>'
        : r.detail.edu
        ? `<span class="fa-cnt">${r.detail.nEdu}</span><div class="fa-sp-t" title="${esc(r.detail.topEdu)}">${esc(r.detail.topEdu)}</div>`
        : '<span class="fa-no">✕</span>'}</td>
    <td class="fa-iss">${iss}</td>
  </tr>`;
}

/* 師資類別（職稱）與導覽選單「師資」二階連結是否一致 */
function faMenuCard(f){
  const m = f.menu;
  if(!m) return '';
  const labels = (m.items||[]).map(x=>x.t);
  const cats = m.cats||[], miss = m.missing||[], ext = m.extra||[];
  const catPills = cats.map(c=>{
    const has = labels.indexOf(c) >= 0;
    return `<span class="fa-cat ${has?'ok':'miss'}">${has?'✓':'✕'} <b>${esc(c)}</b><span class="n">${m.counts[c]} 位</span></span>`;
  }).join('');
  const extPills = ext.map(t=>`<span class="fa-cat ext">⚠ <b>${esc(t)}</b><span class="n">0 位</span></span>`).join('');
  let verdict;
  if(!m.ok){
    verdict = `<div class="fa-mn-bad">${esc(m.note||'抓不到首頁，無法比對選單')}</div>`;
  } else if(!labels.length){
    verdict = `<div class="fa-mn-bad"><b>導覽選單的「師資」底下沒有任何職稱二階連結</b>，
      訪客只能看到師資總覽，無法依講座教授、專任教授等類別快速瀏覽。本系共有 ${cats.length} 種師資類別。</div>`;
  } else if(miss.length || ext.length){
    verdict = `<div class="fa-mn-bad">
      ${miss.length ? `<b>選單缺 ${miss.length} 項</b>：${esc(miss.join('、'))}——本系有這些師資，但選單上沒有對應連結。<br>` : ''}
      ${ext.length ? `<b>選單多 ${ext.length} 項</b>：${esc(ext.join('、'))}——選單有連結，但本系目前沒有這類師資，點進去會是空的。` : ''}
    </div>`;
  } else {
    verdict = `<div class="fa-mn-ok">✓ 本系 ${cats.length} 種師資類別與選單的 ${labels.length} 項二階連結完全一致。</div>`;
  }
  const ord = (ok, bad, what) => ok
    ? `<span class="fa-cat ok">✓ <b>${what}</b>符合排序原則</span>`
    : `<span class="fa-cat miss">✕ <b>${what}</b>未依排序原則：${esc(bad.cur)} 排在 ${esc(bad.prev)} 之後</span>`;
  const unk = (m.unknown||[]).length
    ? `<div class="fa-mn-h">排序原則未收錄的職稱（請人工確認擺放位置）</div>
       <div class="fa-mn">${m.unknown.map(t=>`<span class="fa-cat ext">？ <b>${esc(t)}</b></span>`).join('')}</div>`
    : '';

  return `<div class="card">
    <div class="sec-lbl"><i class="ti ti-sitemap"></i> 師資類別與選單結構是否一致
      <span style="margin-left:auto;font-size:11px;font-weight:600;color:#888780;text-transform:none;letter-spacing:0;">師資類別 ${cats.length} 種／選單二階 ${labels.length} 項</span>
    </div>
    <div class="fa-mn-h">本系實際有的師資類別（依排序原則排列；綠＝選單有對應連結，紅＝選單缺）</div>
    <div class="fa-mn">${catPills || '<span class="fa-cat">（查無師資）</span>'}</div>
    ${extPills ? `<div class="fa-mn-h">選單有、但本系沒有這類師資</div><div class="fa-mn">${extPills}</div>` : ''}
    ${verdict}
    <div class="fa-mn-h">排序是否符合排序原則</div>
    <div class="fa-mn">${ord(m.listOk, m.listBad, '師資名單')}${labels.length ? ord(m.menuOk, m.menuBad, '選單二階') : ''}</div>
    ${unk}
    <div class="fa-sub" style="margin-top:10px;">
      比對方式：抓取${f.home ? `<a href="${esc(safeUrl(f.home))}" target="_blank" rel="noopener noreferrer">系網首頁 ↗</a>` : '系網首頁'}導覽選單中「師資」底下帶
      <code>job_title</code> 參數的二階連結，與師資名單上實際出現的職稱逐一對照；
      排序依公共事務組的師資職稱排序原則（何宜武先生學術講座 → … → 兼任講師，共 25 級）檢查名單與選單的先後順序。
    </div>
  </div>`;
}

function renderFaculty(d){
  const el = document.getElementById('tpfac');
  if(!el) return;
  FA_CUR = d.id;
  const f = FA[d.id];
  if(!f){
    el.innerHTML = `<div class="card"><div class="fa-pend">
      <strong><i class="ti ti-clock" style="color:#BA7517;"></i> 本系尚未進行師資查核。</strong><br>
      師資查核逐系進行中，完成後會在此顯示。查核內容：師資照片是否缺漏／模糊／頭部太貼近上緣、
      師資個人頁是否至少具備「專長」與「學歷」，以及導覽選單的師資二階連結是否涵蓋本系所有師資類別。
    </div></div>`;
    return;
  }
  if(f.noFaculty){
    el.innerHTML = `<div class="card"><div class="sec-lbl"><i class="ti ti-user-off"></i> 師資資料查核
        <span style="margin-left:auto;font-size:11px;font-weight:600;color:#888780;text-transform:none;letter-spacing:0;">查核日期 ${esc(f.checked||'')}</span></div>
      <div class="fa-mn-bad"><b>網站上找不到師資名單。</b></div>
      <div class="fa-sub" style="margin-top:10px;">
        已逐一嘗試 <code>/teachers/</code>、<code>/teacher/</code>、<code>/faculty/</code> 以及導覽選單中的師資連結，
        均未找到可辨識的師資名單頁。對高中生與家長而言，看不到授課師資是相當關鍵的缺漏，
        建議至少列出本單位專兼任師資，或明確連往母系的師資頁。
        <br>系網首頁：<a href="${esc(safeUrl(f.home||''))}" target="_blank" rel="noopener noreferrer">${esc(f.home||'')} ↗</a>
      </div></div>`;
    return;
  }
  const rows = f.rows || [];
  const noPhoto = rows.filter(r=>!r.photo.has).length;
  const badPhoto = rows.filter(r=>r.photo.has && faPhotoIssues(r).length).length;
  const noSpec = rows.filter(r=>r.detail.ok && !r.detail.spec).length;
  const noEdu = rows.filter(r=>r.detail.ok && !r.detail.edu).length;
  const noPage = rows.filter(r=>!r.detail.ok).length;
  const shown = FA_FILTER === 'photo' ? rows.filter(r=>faPhotoIssues(r).length)
              : FA_FILTER === 'detail' ? rows.filter(r=>r.detail.ok && (!r.detail.spec || !r.detail.edu))
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
      ${noPage?`<div class="fa-stat"><div class="fa-stat-n" style="color:#888780;">${noPage}</div><div class="fa-stat-l">無個人頁可查<br><span style="font-size:10px;color:#B4B2A9;">非校網版型</span></div></div>`:''}
    </div>
    <div class="fa-note">
      <b>判讀方式</b>：照片取自校網師資照片 API（與系網顯示的同一張），逐張做人臉偵測。
      <b>只標示兩種照片問題：明顯模糊與頭太貼近上緣</b>（不夠銳利但看得清楚的不算問題）。
      <b>清晰度</b>只量臉部區域的 Laplacian 變異數（整張算會被大片純色背景拉低，全身照會被誤判成模糊），
      <b>低於 10</b> 判「明顯模糊／失焦」；<b>頭頂</b>是臉框上緣距照片頂端的比例，<b>到 0%</b>（臉已貼到頂端或被裁掉）才判「太貼近上緣」。
      灰字是參考資訊，不計入問題數。
      <b>專長／學歷</b>查的是「More」點進去的師資個人頁實際顯示的內容（個人頁的專長、學歷、經歷、著作
      都是由校網師資 API 即時帶入，直接抓網頁原始碼只會看到「基本資訊」的空殼）；數字是筆數。
      部分系網不是校網版型、沒有師資個人頁，該欄會標「無法查核」而非當成缺漏。
      數值一併列出供人工覆核，<b>判讀僅供排序參考，最終仍請目視確認</b>。
    </div>
  </div>`;

  h += faMenuCard(f);

  h += `<div class="card">
    <div class="sec-lbl"><i class="ti ti-list-check"></i> 師資逐位查核（${shown.length}／${rows.length} 位）
      <span class="fa-tools">
        <button class="${FA_FILTER==='all'?'on':''}" onclick="faSetFilter('all')">全部 ${rows.length}</button>
        <button class="${FA_FILTER==='photo'?'on':''}" onclick="faSetFilter('photo')">照片有疑慮 ${noPhoto+badPhoto}</button>
        <button class="${FA_FILTER==='detail'?'on':''}" onclick="faSetFilter('detail')">個人頁不全 ${rows.filter(r=>r.detail.ok&&(!r.detail.spec||!r.detail.edu)).length}</button>
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
                      lambda _m: JS, html, count=1, flags=re.S)
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

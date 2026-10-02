# -*- coding: utf-8 -*-
"""把 tools/share.json（學生愛分享篇數與流量）同步進 health-check.html 的
「🎓 學生愛分享」分頁。

用法：
    node tools/extract-share.js                   # 1. 從 student-share.html 重算 → tools/share.json
    python tools/sync-share-to-healthcheck.py     # 2. 注入 health-check.html

冪等：可重複執行。資料常數（SH_META／SH）與版面程式碼每次整段取代（marker 保護），
分頁按鈕／面板／render 呼叫只在不存在時插入。每次執行前自動備份 health-check.html。
"""
import json, re, shutil, sys, datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
HC = HERE.parent / 'health-check.html'
SRC = HERE / 'share.json'

if not SRC.exists():
    sys.exit('找不到 tools/share.json，請先執行：node tools/extract-share.js')

j = json.loads(SRC.read_text(encoding='utf-8'))
meta, depts = j['meta'], j['depts']
html = HC.read_text(encoding='utf-8')

# ══════════════════════════════════════════════════════════════════
# 1. CSS
# ══════════════════════════════════════════════════════════════════
CSS = '''/* ==SHARE_CSS_START== */
/* ── 學生愛分享分頁 ── */
.sh-stats{display:flex;gap:8px;flex-wrap:wrap;}
.sh-stat{flex:1;min-width:108px;background:#f7f6f1;border:1px solid #e5e4dc;border-radius:9px;padding:9px 11px;text-align:center;}
.sh-stat-n{font-size:23px;font-weight:800;line-height:1.1;}
.sh-stat-l{font-size:11px;color:#888780;margin-top:3px;line-height:1.5;}
.sh-cmp{margin-top:12px;}
.sh-cmp-r{display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap;font-size:12.5px;color:#5F5E5A;margin-bottom:6px;}
.sh-cmp-bg{height:11px;background:#ebe9e0;border-radius:6px;overflow:hidden;position:relative;}
.sh-cmp-f{height:100%;background:linear-gradient(90deg,#AFA9EC,#534AB7);border-radius:6px;transition:width .5s ease;}
.sh-cmp-avg{position:absolute;top:0;bottom:0;width:2px;background:#BA7517;}
.sh-cmp-n{font-size:12px;color:#888780;margin-top:6px;}
.sh-rk{display:inline-block;font-size:11.5px;font-weight:800;border-radius:10px;padding:2px 9px;background:#EEEDFE;color:#534AB7;white-space:nowrap;}
.sh-chart{display:flex;align-items:flex-end;gap:10px;height:128px;padding-top:6px;}
.sh-col{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;min-width:0;}
.sh-bn{font-size:14px;font-weight:800;color:#1a1a18;line-height:1.3;margin-bottom:3px;}
.sh-bar{width:100%;max-width:52px;border-radius:4px 4px 0 0;background:#ebe9e0;min-height:4px;}
.sh-bar.lo{background:#AFA9EC;} .sh-bar.hi{background:#534AB7;}
.sh-bm{font-size:12.5px;color:#5F5E5A;margin-top:6px;white-space:nowrap;}
.sh-tbl{width:100%;border-collapse:collapse;font-size:13px;}
.sh-tbl th{background:#f7f6f1;font-size:11.5px;color:#5F5E5A;font-weight:700;padding:7px 8px;border-bottom:1px solid #e5e4dc;text-align:left;}
.sh-tbl td{padding:7px 8px;border-bottom:1px solid #f0efe9;vertical-align:top;line-height:1.6;}
.sh-tbl tr:last-child td{border-bottom:none;}
.sh-tbl tr:hover td{background:#fcfcfa;}
.sh-tbl a{color:#185FA5;text-decoration:none;}
.sh-tbl a:hover{text-decoration:underline;}
.sh-rank{width:30px;text-align:center;color:#B4B2A9;font-size:11px;}
.sh-dt{width:84px;font-size:11.5px;color:#888780;white-space:nowrap;}
.sh-pv{width:84px;text-align:right;font-weight:700;white-space:nowrap;}
.sh-sort{display:flex;gap:5px;margin-left:auto;}
.sh-sort button{font-size:11px;font-weight:700;padding:3px 10px;border-radius:7px;border:1px solid #d3d1c7;background:#fff;color:#5F5E5A;cursor:pointer;text-transform:none;letter-spacing:0;}
.sh-sort button.on{background:#534AB7;border-color:#534AB7;color:#fff;}
.sh-sub{font-size:11.5px;color:#888780;line-height:1.7;}
.sh-zero{background:#FDF8EC;border:1px solid #F2DCA8;border-radius:9px;padding:12px 14px;font-size:13px;color:#5F5E5A;line-height:1.85;}
@media(max-width:620px){
  .sh-tbl .sh-rank{display:none;}
  .sh-chart{height:104px;gap:4px;}
  .sh-bm{font-size:10px;}
  .sh-bn{font-size:12px;}
}
/* ==SHARE_CSS_END== */
'''
CSS_ANCHOR = '/* ==ADMISSION_CSS_START== */'
if '==SHARE_CSS_START==' in html:
    html = re.sub(r'/\* ==SHARE_CSS_START==.*?/\* ==SHARE_CSS_END== \*/\n', lambda _m: CSS, html,
                  count=1, flags=re.S)
else:
    assert CSS_ANCHOR in html, '找不到 CSS 插入位置（==ADMISSION_CSS_START==）'
    html = html.replace(CSS_ANCHOR, CSS + CSS_ANCHOR, 1)

# ══════════════════════════════════════════════════════════════════
# 2. 資料常數 + 版面程式碼（整個 SHARE_JS 區塊每次重寫）
# ══════════════════════════════════════════════════════════════════
CONST = ('const SH_META = ' + json.dumps(meta, ensure_ascii=False, separators=(',', ':')) + ';\n'
         + 'const SH = ' + json.dumps(depts, ensure_ascii=False, separators=(',', ':')) + ';\n')

JS = '''/* ═══════════════════════════════════════════════════════
   學生愛分享分頁  ==SHARE_JS_START==
   資料由 tools/extract-share.js 從 student-share.html（學生愛分享儀表板）抽出，
   篇數與瀏覽次數一律以該儀表板為唯一來源，請勿在此另行統計。
   更新：node tools/extract-share.js && python tools/sync-share-to-healthcheck.py
═══════════════════════════════════════════════════════ */
/* 先行開放的學系 id；全面開放時把整個陣列改成字串 'all' */
const SH_DEPTS = 'all';
__CONST__function SH_ON(d){ return (SH_DEPTS === 'all' || SH_DEPTS.indexOf(d.id) >= 0) && !!SH[d.id]; }

function shNum(n){ return (n||0).toLocaleString(); }
function shDate(s){ return (s||'').replace(/-/g,'.'); }
let SH_CUR = null, SH_SORT = 'date';

function shRows(s){
  const list = s.items.slice();
  if(SH_SORT === 'pv') list.sort((a,b)=> b.pv - a.pv || b.d.localeCompare(a.d));
  else list.sort((a,b)=> b.d.localeCompare(a.d));
  return list.map((it,i)=>`<tr>
    <td class="sh-rank">${i+1}</td>
    <td>${it.u ? `<a href="${esc(safeUrl(it.u))}" target="_blank" rel="noopener noreferrer">${esc(it.t)}</a>` : esc(it.t)}</td>
    <td class="sh-dt">${esc(shDate(it.d))}</td>
    <td class="sh-pv" style="color:${it.pv ? '#185FA5' : '#B4B2A9'};">${it.pv ? shNum(it.pv) : '—'}</td>
  </tr>`).join('');
}

function shSort(mode){
  const s = SH[SH_CUR];
  if(!s) return;
  SH_SORT = mode;
  const tb = document.getElementById('sh-tbody');
  if(tb) tb.innerHTML = shRows(s);
  document.querySelectorAll('.sh-sort button').forEach(b=>b.classList.toggle('on', b.dataset.m === mode));
}

function renderShare(d){
  const el = document.getElementById('tpshare');
  if(!el) return;
  const s = SH[d.id];
  if(!s){ el.innerHTML = '<div class="pending-note">本站未納入學生愛分享統計。</div>'; return; }
  SH_CUR = d.id;
  SH_SORT = 'date';
  const M = SH_META;
  const maxY = Math.max.apply(null, s.years.concat([1]));
  const cmpMax = Math.max(s.cnt, M.avgCnt, 1);

  let h = '';
  h += `<div class="card">
    <div class="sec-lbl"><i class="ti ti-users"></i> 學生愛分享篇數與流量
      <span style="margin-left:auto;font-size:11px;font-weight:600;color:#888780;text-transform:none;letter-spacing:0;">資料更新：${esc(M.builtAt||'')}</span>
    </div>
    <div class="sh-stats">
      <div class="sh-stat"><div class="sh-stat-n" style="color:#534AB7;">${s.cnt}</div><div class="sh-stat-l">累計篇數</div></div>
      <div class="sh-stat"><div class="sh-stat-n" style="color:${s.ay ? '#1D9E75' : '#E24B4A'};">${s.ay}</div><div class="sh-stat-l">${esc(M.ay)}新增<br><span style="font-size:10px;color:#B4B2A9;">${esc(shDate(M.cut))} 起</span></div></div>
      <div class="sh-stat"><div class="sh-stat-n" style="color:#185FA5;">${shNum(s.pv)}</div><div class="sh-stat-l">瀏覽次數合計</div></div>
      <div class="sh-stat"><div class="sh-stat-n" style="color:#BA7517;">${shNum(s.avgPv)}</div><div class="sh-stat-l">平均每篇瀏覽</div></div>
      <div class="sh-stat"><div class="sh-stat-n" style="color:#5F5E5A;font-size:18px;">${esc(s.last ? shDate(s.last) : '—')}</div><div class="sh-stat-l">最近發佈日期</div></div>
    </div>
    <div class="sh-cmp">
      <div class="sh-cmp-r">
        <span><i class="ti ti-chart-bar" style="font-size:12px;"></i> 本系 <strong>${s.cnt}</strong> 篇　<span style="color:#BA7517;">全校平均 ${M.avgCnt} 篇</span></span>
        <span>${s.cnt ? `<span class="sh-rk">篇數第 ${s.rkCnt} 名／${M.liveN} 系</span>　<span class="sh-rk">瀏覽第 ${s.rkPv} 名</span>` : `<span class="sh-rk" style="background:#FDECEC;color:#B91C1C;">尚未產出</span>`}</span>
      </div>
      <div class="sh-cmp-bg">
        <div class="sh-cmp-f" style="width:${Math.round(s.cnt/cmpMax*100)}%"></div>
        <div class="sh-cmp-avg" style="left:${Math.min(99.5, M.avgCnt/cmpMax*100)}%" title="全校平均 ${M.avgCnt} 篇"></div>
      </div>
      <div class="sh-cmp-n">全校 ${M.total} 篇，其中 ${M.matched} 篇已對應到 ${M.liveN} 個學系（平均 ${M.avgCnt} 篇、平均瀏覽 ${shNum(M.avgPv)} 次）</div>
    </div>
  </div>`;

  if(!s.cnt){
    h += `<div class="card"><div class="sh-zero">
      <strong><i class="ti ti-alert-triangle" style="color:#BA7517;"></i> 本系在校級「學生愛分享」尚無文章。</strong><br>
      學生愛分享（<a href="https://www.fcu.edu.tw/share/" target="_blank" rel="noopener noreferrer" style="color:#185FA5;text-decoration:none;">www.fcu.edu.tw/share/ ↗</a>）
      是校級的在校生與系友故事專區，長期可瀏覽、不具時效性，是高中生與家長了解「讀這個系的人後來怎麼了」最直接的素材。
      建議由系上推薦 1–2 位在校生或系友，交公共事務組採訪撰稿。
    </div></div>`;
  }

  if(s.cnt){
  h += `<div class="card">
    <div class="sec-lbl"><i class="ti ti-chart-bar"></i> 年度發佈趨勢</div>
    <div class="sh-chart">${s.years.map((v,i)=>{
      const hp = Math.max(4, Math.round(v / maxY * 86));
      const cls = v >= 5 ? 'hi' : (v > 0 ? 'lo' : '');
      return `<div class="sh-col" title="${M.years[i]} 年　${v} 篇">
        <span class="sh-bn">${v || ''}</span>
        <span class="sh-bar ${cls}" style="height:${hp}px;"></span>
        <span class="sh-bm">${M.years[i]}</span>
      </div>`;
    }).join('')}</div>
  </div>`;
  }

  if(s.items.length){
    h += `<div class="card">
      <div class="sec-lbl"><i class="ti ti-list"></i> 文章列表（${s.cnt} 篇）
        <span class="sh-sort">
          <button class="on" data-m="date" onclick="shSort('date')">依發佈日期</button>
          <button data-m="pv" onclick="shSort('pv')">依瀏覽次數</button>
        </span>
      </div>
      <table class="sh-tbl"><thead><tr>
        <th class="sh-rank">#</th><th>標題</th><th class="sh-dt">發佈日期</th><th class="sh-pv">瀏覽次數</th>
      </tr></thead><tbody id="sh-tbody">${shRows(s)}</tbody></table>
      <div class="sh-sub" style="margin-top:10px;">
        篇數與瀏覽次數以<a href="student-share.html" target="_blank" rel="noopener" style="color:#185FA5;text-decoration:none;">學生愛分享儀表板 ↗</a>為唯一來源。
        瀏覽次數為 GA4 ${esc(shDate(M.gaSince))} ~ ${esc(shDate(M.gaUntil))} 區間的頁面瀏覽數（非全站歷史累計）；
        /share/ 全區段同期合計 ${shNum(M.gaPv)} 次、使用者 ${shNum(M.gaUsers)} 人、平均停留 ${M.gaAvgDur} 秒。
      </div>
    </div>`;
  }
  el.innerHTML = h;
}
/* ==SHARE_JS_END== */
'''.replace('__CONST__', CONST)

JS_ANCHOR = ('/* ═══════════════════════════════════════════════════════\n'
             '   招生連結查核分頁  ==ADMISSION_JS_START==')
if '==SHARE_JS_START==' in html:
    html, n = re.subn(r'/\* ═+\n   學生愛分享分頁  ==SHARE_JS_START==.*?/\* ==SHARE_JS_END== \*/\n',
                      lambda _m: JS, html, count=1, flags=re.S)
    if not n:
        sys.exit('取代 SHARE_JS 區塊失敗，請檢查 health-check.html 是否被手改過')
else:
    assert JS_ANCHOR in html, '找不到 JS 插入位置（==ADMISSION_JS_START==）'
    html = html.replace(JS_ANCHOR, JS + '\n' + JS_ANCHOR, 1)

# ══════════════════════════════════════════════════════════════════
# 3. 分頁按鈕、面板、render 呼叫
#    ⚠ switchTab 靠 DOM 索引對位，按鈕與面板的順序必須一致
# ══════════════════════════════════════════════════════════════════
BTN_OLD = """    ${NW_ON(d)?`<button class="tab" onclick="switchTab('tpnews')">📰 新聞成效</button>`:''}"""
BTN_NEW = BTN_OLD + """
    ${SH_ON(d)?`<button class="tab" onclick="switchTab('tpshare')">🎓 學生愛分享</button>`:''}"""
if "switchTab('tpshare')" not in html:
    assert BTN_OLD in html, '找不到分頁按鈕插入位置'
    html = html.replace(BTN_OLD, BTN_NEW, 1)

PANEL_OLD = '''  ${NW_ON(d)?`<div class="tab-panel" id="tpnews"></div>`:``}'''
PANEL_NEW = PANEL_OLD + '''
  ${SH_ON(d)?`<div class="tab-panel" id="tpshare"></div>`:``}'''
if 'id="tpshare"' not in html:
    assert PANEL_OLD in html, '找不到分頁面板插入位置'
    html = html.replace(PANEL_OLD, PANEL_NEW, 1)

CALL_OLD = '  // 新聞成效分頁\n  renderNews(d);\n'
CALL_NEW = CALL_OLD + '\n  // 學生愛分享分頁\n  renderShare(d);\n'
if 'renderShare(d);' not in html:
    assert CALL_OLD in html, '找不到 renderShare 呼叫插入位置'
    html = html.replace(CALL_OLD, CALL_NEW, 1)

# ── 寫回（先備份） ──
bak = HC.with_suffix('.html.bak-share-' + datetime.datetime.now().strftime('%Y%m%d%H%M'))
shutil.copyfile(HC, bak)
HC.write_text(html, encoding='utf-8', newline='')

live = [v for v in depts.values() if v['cnt']]
print('已同步 {} 個學系｜有產出 {} 系共 {} 篇｜瀏覽合計 {:,}'.format(
    len(depts), len(live), meta['matched'], sum(v['pv'] for v in depts.values())))
print('統計期間：' + meta['gaSince'] + ' ~ ' + meta['gaUntil'] + '（GA4）')
print('備份：', bak.name)
print('檔案大小：', round(HC.stat().st_size / 1024), 'KB')

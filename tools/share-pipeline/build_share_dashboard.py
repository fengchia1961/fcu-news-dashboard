# -*- coding: utf-8 -*-
import os
from pathlib import Path
HERE = Path(__file__).resolve().parent
PROJ = HERE.parent.parent          # fcu-news-dashboard/
import json
from datetime import datetime
from urllib.parse import urlparse

SHARE_FULL_FILE = HERE / "share_full.json"
GA4_FILE        = HERE / "share_ga4.json"
DEPT_MAP_FILE   = HERE / "share_dept_map.json"
HTML_FILE       = PROJ / "student-share.html"
# 學年度切換時只要改這兩行（CUT＝本學年度起算日，AY＝顯示用學年度名稱）
CUT = "2026-08-01"
AY  = "115學年度"

TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline' https://cdn.jsdelivr.net; font-src https://cdn.jsdelivr.net; img-src 'self' https: data:; base-uri 'none'; form-action 'none'; object-src 'none'">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>學生愛分享儀表板</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.19.0/dist/tabler-icons.min.css" integrity="sha384-hs5SINUk7GPohxRis+rS7grpSWEbtOIJ3sRoseBKg3CDPIKpG55RfSenbvA6ALOt" crossorigin="anonymous">
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans TC',sans-serif;background:#f0efe9;color:#1a1a18;font-size:17px;line-height:1.5;}
.layout{display:flex;height:100vh;}

/* Sidebar */
.sb{width:256px;flex-shrink:0;overflow-y:auto;border-right:1px solid #dddcd4;background:#f7f6f1;display:flex;flex-direction:column;}
.sb-hdr{padding:1rem 1.1rem .75rem;border-bottom:1px solid #dddcd4;flex-shrink:0;}
.sb-logo{display:flex;align-items:center;gap:9px;margin-bottom:.5rem;}
.sb-logo i{font-size:22px;color:#534AB7;}
.sb-t{font-size:16px;font-weight:700;color:#1a1a18;line-height:1.3;}
.sb-m{font-size:12.5px;color:#888780;margin-top:4px;line-height:1.65;}
.sb-btns{display:flex;flex-direction:column;gap:5px;margin-top:8px;}
.sb-btn{display:flex;align-items:center;gap:6px;width:100%;padding:6px 10px;font-size:12px;background:#fff;border:1px solid #d3d1c7;border-radius:7px;cursor:pointer;color:#534AB7;font-weight:600;text-decoration:none;transition:background .12s;}
.sb-btn:hover{background:#EEEDFE;border-color:#AFA9EC;}
.sb-btn.red{color:#185FA5;}
.sb-btn.red:hover{background:#EAF1FA;border-color:#8FB8DD;}
.sb-body{flex:1;overflow-y:auto;padding-bottom:.75rem;}
.col-h{padding:.6rem 1.1rem .2rem;font-size:12px;font-weight:700;color:#888780;text-transform:uppercase;letter-spacing:.08em;margin-top:4px;}
.di{display:flex;align-items:center;gap:8px;padding:.4rem 1.1rem;cursor:pointer;color:#5F5E5A;border-left:3px solid transparent;transition:background .12s;}
.di:hover{background:rgba(0,0,0,.05);color:#1a1a18;}
.di.act{background:#fff;color:#185FA5;border-left-color:#185FA5;font-weight:700;}
.di-n{font-size:15px;line-height:1.35;}
.dot{width:9px;height:9px;border-radius:50%;flex-shrink:0;}

/* Main area */
.mn{flex:1;overflow-y:auto;padding:1.25rem 1.6rem;background:#f0efe9;}
.card{background:#fff;border-radius:12px;padding:1.1rem 1.4rem;margin-bottom:.9rem;border:1px solid #e5e4dc;}
.dn{font-size:22px;font-weight:700;color:#1a1a18;}
.ds{font-size:13px;color:#888780;margin-top:4px;}

/* Stat grid */
.sg{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:.9rem;}
.sc{background:#fff;border-radius:10px;padding:.8rem .6rem;text-align:center;border:1px solid #e5e4dc;}
.sv{font-size:28px;font-weight:700;line-height:1.1;}
.sl{font-size:12.5px;color:#888780;margin-top:5px;line-height:1.4;}

/* Table */
.tbl-wrap{background:#fff;border-radius:12px;overflow:clip;border:1px solid #e5e4dc;}
.tbl-hdr{padding:.7rem 1.2rem;background:#f7f6f1;border-bottom:1px solid #e5e4dc;font-size:14px;font-weight:700;color:#1a1a18;display:flex;align-items:center;gap:8px;}
table{width:100%;border-collapse:collapse;font-size:14.5px;}
th{padding:.55rem 1rem;font-size:13px;font-weight:700;color:#888780;text-align:left;border-bottom:1px solid #e5e4dc;background:#f7f6f1;position:sticky;top:0;z-index:2;}
td{padding:.6rem 1rem;border-bottom:1px solid #eceae0;vertical-align:middle;}
tr:last-child td{border-bottom:none;}
tr:hover td{background:#faf9f6;}
.ttl{color:#1a1a18;cursor:pointer;line-height:1.45;font-size:14.5px;}
.ttl:hover{color:#185FA5;text-decoration:underline;}
.gb{display:inline-block;font-size:12.5px;padding:3px 10px;border-radius:6px;font-weight:700;white-space:nowrap;}

/* Misc */
.empty{text-align:center;padding:4rem;color:#B4B2A9;font-size:15px;}
.topbar{display:flex;align-items:center;gap:10px;background:#fff;border-bottom:1px solid #dddcd4;padding:.7rem 1.6rem;flex-shrink:0;font-size:13px;color:#888780;}
.topbar strong{color:#1a1a18;font-size:15px;}
/* ── 手機版 ── */
.mob-btn{display:none;align-items:center;justify-content:center;width:44px;height:44px;border:1px solid #d3d1c7;border-radius:8px;background:#fff;cursor:pointer;color:#1a1a18;font-size:18px;flex-shrink:0;}
.mob-btn:hover{background:rgba(0,0,0,.08);}
.sb-overlay{position:fixed;inset:0;background:rgba(0,0,0,.42);z-index:98;display:none;}
.sb-overlay.sb-open{display:block;}
.sg-wrap{position:relative;margin-bottom:.9rem;}
.sg-wrap>.sg{margin-bottom:0;}
.sg-arrow{display:none;align-items:center;gap:2px;position:absolute;top:2px;right:0;font-size:10.5px;color:#B4B2A9;pointer-events:none;z-index:1;}
.mob-meta{display:none;}
@media(max-width:767px){
  .mob-btn{display:flex;}
  .mob-hide{display:none!important;}
  .sb{position:fixed;top:0;left:0;height:100%;width:80%;max-width:290px;z-index:99;transform:translateX(-100%);transition:transform .22s ease;box-shadow:4px 0 20px rgba(0,0,0,.22);}
  .sb.sb-open{transform:translateX(0);}
  .di{padding:.7rem 1rem;}
  .sb-btn{padding:11px 10px;min-height:44px;}
  .mn{padding:.85rem .9rem;}
  .sv{font-size:22px;}
  .sc{padding:.65rem .5rem;}
  .topbar{padding:.5rem .9rem;font-size:12px;gap:4px 6px;}
  .card{padding:.85rem 1rem;}
  .dn{font-size:18px;}
  .tbl-wrap{overflow-x:auto;}
  .tbl-hdr{flex-direction:column;align-items:stretch;}
  .tbl-hdr input[type="text"]{width:100%!important;box-sizing:border-box;margin-top:4px;}
  .sg-wrap{padding-top:18px;}
  .sg-arrow{display:flex;}
  .sg-wrap>.sg{display:flex!important;overflow-x:auto;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;scrollbar-width:none;gap:8px;padding-bottom:2px;}
  .sg-wrap>.sg::-webkit-scrollbar{display:none;}
  .sg-wrap>.sg>.sc{flex:0 0 calc(47% - 4px);scroll-snap-align:start;min-width:130px;flex-shrink:0;}
  .mob-meta{display:flex!important;flex-wrap:wrap;gap:5px 8px;margin-top:6px;align-items:center;}
  /* 卡片式表格排版 */
  .art-tbl,.hc-tbl{display:block;}
  .art-tbl tbody,.hc-tbl tbody{display:block;}
  .art-tbl thead,.hc-tbl thead{display:none;}
  .art-tbl tr,.hc-tbl tr{display:flex!important;align-items:flex-start;gap:8px;padding:.7rem .9rem;border-bottom:1px solid #eceae0;}
  .art-tbl tr:last-child,.hc-tbl tr:last-child{border-bottom:none;}
  .art-tbl td,.hc-tbl td{padding:0;border:none;}
  .art-tbl td.td-col,.art-tbl td.td-dept,.art-tbl td.td-date,.art-tbl td.td-pv{display:none;}
  .hc-tbl td.td-col,.hc-tbl td.td-date,.hc-tbl td.td-pv{display:none;}
  .td-rank{flex-shrink:0;min-width:20px;text-align:center;padding-top:2px;}
  .td-title{flex:1;min-width:0;}
  .td-title .ttl{display:block;font-size:14px;line-height:1.5;}
}
</style>
</head>
<body>
<div class="layout">

<!-- Sidebar -->
<div class="sb">
  <div class="sb-hdr">
    <div class="sb-logo">
      <i class="ti ti-heart"></i>
      <div class="sb-t">學生愛分享<br>篇數與流量儀表板</div>
    </div>
    <div class="sb-m">秘書處公共事務組<br>資料建置：<span id="builtVal"></span></div>
    <div class="sb-btns">
      <a class="sb-btn red" href="https://fengchia1961.github.io/ai-pitch/" target="_blank" rel="noopener noreferrer">
        <i class="ti ti-arrow-back-up"></i> 返回AI成果首頁
      </a>
      <a class="sb-btn" href="https://fengchia1961.github.io/fcu-news-dashboard/health-check.html" target="_blank" rel="noopener noreferrer">
        <i class="ti ti-stethoscope"></i> 網站健檢儀表板
      </a>
      <a class="sb-btn" href="https://fengchia1961.github.io/fcu-news-dashboard/" target="_blank" rel="noopener noreferrer">
        <i class="ti ti-news"></i> FCU新聞監測儀表版
      </a>
    </div>
  </div>
  <div class="sb-body" id="sb-body"></div>
</div>

<!-- Main -->
<div style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
  <div class="topbar">
    <button class="mob-btn" onclick="openSB()" title="開啟選單"><i class="ti ti-menu-2"></i></button>
    <i class="ti ti-calendar-stats mob-hide" style="font-size:14px;color:#1D9E75;"></i>
    <span class="mob-hide"><span id="ayVal"></span>統計起迄：<strong id="cutVal"></strong> 起</span>
    <span class="mob-hide">｜</span>
    <span>全站累計：<strong id="totVal"></strong> 篇</span>
    <span class="mob-hide">｜</span>
    <span>GA4區間(<strong id="gaRangeVal"></strong>)：<strong id="pvAllVal"></strong> 次瀏覽</span>
    <span style="margin-left:auto;" class="mob-hide">資料來源：fcu.edu.tw/share/</span>
  </div>
  <div class="mn" id="mn">
    <div class="empty">載入中…</div>
  </div>
</div>

</div>
<div class="sb-overlay" id="sb-overlay" onclick="closeSB()"></div>

<script>
/*__SHARE_DATA__*/

const COLLEGE_PALETTE = [
  {bg:'#EAF0FB', fg:'#185FA5', dot:'#185FA5'},
  {bg:'#EAF3DE', fg:'#3B6D11', dot:'#1D9E75'},
  {bg:'#EEEDFE', fg:'#534AB7', dot:'#534AB7'},
  {bg:'#FAEEDA', fg:'#854F0B', dot:'#BA7517'},
  {bg:'#E3F3EE', fg:'#0F6E56', dot:'#0F6E56'},
  {bg:'#FCEBEB', fg:'#A32D2D', dot:'#A32D2D'},
  {bg:'#FAECE7', fg:'#993C1D', dot:'#993C1D'},
  {bg:'#F1EBFB', fg:'#7C3AED', dot:'#7C3AED'},
  {bg:'#FBE7EF', fg:'#B91C63', dot:'#B91C63'},
  {bg:'#E9E8FB', fg:'#4338CA', dot:'#4338CA'},
  {bg:'#E5F4EA', fg:'#15803D', dot:'#15803D'},
];
const OTHER_COLOR = {bg:'#f0efe8', fg:'#888780', dot:'#B4B2A9'};
const COLLEGE_ORDER = COLLEGES.map(function(c){ return c.col; });

function collegeColor(name){
  const i = COLLEGE_ORDER.indexOf(name);
  if(i===-1 || name==='其他') return OTHER_COLOR;
  return COLLEGE_PALETTE[i % COLLEGE_PALETTE.length];
}
function esc(s){
  return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function safeUrl(u){ u=String(u==null?'':u); const l=u.toLowerCase(); return (l.indexOf('http://')===0||l.indexOf('https://')===0)?u:'#'; }
function jd(s){ return (s||'').replace(/-/g,'.'); }
function fmtNum(n){ return (n||0).toLocaleString(); }
function todayStr(){
  const d=new Date();
  return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
}
function monthsBetween(a,b){
  const ap=a.split('-'), bp=b.split('-');
  const ay=Number(ap[0]), am=Number(ap[1]);
  const by=Number(bp[0]), bm=Number(bp[1]);
  return (by-ay)*12+(bm-am)+1;
}

SHARE_RAW.forEach(function(n){
  n.pv = GA4_SHARE.pageViews[n.path] || 0;
});

function deptCount(dept){
  return SHARE_RAW.filter(function(n){ return n.dept===dept; }).length;
}

let cur = null;

function yearChart(items){
  if(!items.length) return '<div class="empty" style="padding:2rem;">無資料</div>';
  const years = items.map(function(n){ return parseInt(n.d.slice(0,4),10); });
  const minY = Math.min.apply(null, years), maxY = new Date().getFullYear();
  const labels = [];
  for(let y=minY;y<=maxY;y++) labels.push(y);
  const cnt = {};
  labels.forEach(function(y){ cnt[y]=0; });
  items.forEach(function(n){ const y=parseInt(n.d.slice(0,4),10); if(cnt[y]!==undefined) cnt[y]++; });
  const counts = labels.map(function(y){ return cnt[y]; });
  const max = Math.max.apply(null, counts.concat([1]));
  const BW=32, GAP=10, BH=46;
  const TW = labels.length*(BW+GAP)-GAP;
  const bars = labels.map(function(y,i){
    const c = cnt[y];
    const h = c ? Math.max(4, Math.round(c/max*BH)) : 0;
    const x = i*(BW+GAP);
    const fill = c>=20 ? '#1D9E75' : c>=5 ? '#5DCAA5' : c>=1 ? '#EF9F27' : '#ebe9e0';
    return '<g>'
      + '<rect x="'+x+'" y="'+(BH-h)+'" width="'+BW+'" height="'+Math.max(h,0)+'" fill="'+fill+'" rx="3"/>'
      + '<text x="'+(x+BW/2)+'" y="'+(BH-h-5)+'" font-size="9" text-anchor="middle" fill="#5F5E5A" font-weight="600">'+(c||'')+'</text>'
      + '<text x="'+(x+BW/2)+'" y="'+(BH+14)+'" font-size="9" text-anchor="middle" fill="#888780">'+y+'</text>'
      + '</g>';
  }).join('');
  return '<svg viewBox="0 0 '+TW+' '+(BH+22)+'" xmlns="http://www.w3.org/2000/svg" style="display:block;width:100%;max-width:'+(TW*2.2)+'px;">'+bars+'</svg>';
}

function rowHTML(n,i,pvColor,showCollege,showDept,showPv){
  const col = collegeColor(n.college);
  const showPv2 = showPv!==false;
  const pvColor2 = pvColor||(n.pv?'#185FA5':'#B4B2A9');
  const mmp = [];
  if(showCollege!==false) mmp.push('<span class="gb" style="font-size:11.5px;padding:2px 7px;background:'+col.bg+';color:'+col.fg+';">'+esc(n.college)+'</span>');
  if(showDept!==false) mmp.push('<span style="font-size:11.5px;color:#5F5E5A;">'+esc(n.dept)+'</span>');
  mmp.push('<span style="font-size:11.5px;color:#888780;"><span style="font-size:10.5px;color:#B4B2A9;margin-right:2px;">發布</span>'+jd(n.d)+'</span>');
  if(showPv2) mmp.push('<span style="font-size:11.5px;font-weight:700;color:'+pvColor2+';"><span style="font-size:10.5px;color:#B4B2A9;font-weight:400;margin-right:2px;">瀏覽</span>'+(n.pv?fmtNum(n.pv):'—')+'</span>');
  const mobMeta = '<div class="mob-meta">'+mmp.join('')+'</div>';
  const collegeCell = showCollege===false ? '' :
    '<td class="td-col"><span class="gb" style="background:'+col.bg+';color:'+col.fg+';">'+esc(n.college)+'</span></td>';
  const deptCell = showDept===false ? '' :
    '<td class="td-dept" style="font-size:12.5px;color:#5F5E5A;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="'+esc(n.dept)+'">'+esc(n.dept)+'</td>';
  const pvCell = showPv2 ?
    '<td class="td-pv" style="text-align:right;font-weight:700;color:'+pvColor2+';">'+(n.pv?fmtNum(n.pv):'—')+'</td>' : '';
  return '<tr>'
    + '<td class="td-rank" style="text-align:center;color:#B4B2A9;font-size:11px;">'+(i+1)+'</td>'
    + '<td class="td-title"><a href="'+esc(safeUrl(n.url))+'" target="_blank" rel="noopener noreferrer" class="ttl" style="text-decoration:none;color:#1a1a18;">'+esc(n.t)+'</a>'+mobMeta+'</td>'
    + collegeCell
    + deptCell
    + '<td class="td-date" style="font-size:11.5px;color:#888780;white-space:nowrap;">'+jd(n.d)+'</td>'
    + pvCell
    + '</tr>';
}

function articleTable(containerId, items, showCollegeDept){
  const showCD = showCollegeDept!==false;
  const sorted = items.slice().sort(function(a,b){ return b.d.localeCompare(a.d); });
  function renderRows(rows){
    return rows.length
      ? rows.map(function(n,i){ return rowHTML(n,i,null,false,showCD,false); }).join('')
      : '<tr><td colspan="'+(showCD?4:3)+'" class="empty">查無符合的文章</td></tr>';
  }
  const extraCols = showCD
    ? '<th class="th-dept" style="width:220px;">學系</th>'
    : '';
  document.getElementById(containerId).innerHTML =
    '<div class="tbl-wrap">'
    + '<div class="tbl-hdr" style="justify-content:space-between;flex-wrap:wrap;gap:8px;">'
    + '<span><i class="ti ti-list-details"></i> 文章列表（共 <span id="'+containerId+'-count">'+sorted.length+'</span> 篇）</span>'
    + '<input id="'+containerId+'-search" type="text" placeholder="搜尋標題…" style="padding:5px 10px;border:1px solid #d3d1c7;border-radius:6px;font-size:13px;width:200px;">'
    + '</div>'
    + '<table class="art-tbl"><thead><tr>'
    + '<th class="th-rank" style="width:30px;text-align:center;">#</th>'
    + '<th class="th-title">標題</th>'
    + extraCols
    + '<th class="th-date" style="width:85px;">發佈日期</th>'
    + '</tr></thead><tbody id="'+containerId+'-tbody">'+renderRows(sorted)+'</tbody></table>'
    + '</div>';

  document.getElementById(containerId+'-search').addEventListener('input', function(e){
    const q = e.target.value.trim().toLowerCase();
    const filtered = q ? sorted.filter(function(n){ return n.t.toLowerCase().indexOf(q)!==-1; }) : sorted;
    document.getElementById(containerId+'-tbody').innerHTML = renderRows(filtered);
    document.getElementById(containerId+'-count').textContent = filtered.length;
  });
}

function hotColdHTML(){
  const withViews = SHARE_RAW.filter(function(n){ return n.pv>0; });
  const hot = withViews.slice().sort(function(a,b){ return b.pv-a.pv; }).slice(0,10);
  const rangeLabel = jd(GA4_SHARE.since)+' ~ '+jd(GA4_SHARE.until);
  const hcHead = '<thead><tr><th class="th-rank" style="width:28px;"></th><th class="th-title">標題</th><th class="th-col" style="width:110px;">學院</th><th class="th-date" style="width:85px;">發佈日期</th><th class="th-pv" style="width:90px;text-align:right;">瀏覽次數</th></tr></thead>';
  return '<div class="tbl-wrap" style="margin-bottom:.9rem;">'
    + '<div class="tbl-hdr"><i class="ti ti-trending-up"></i><span>熱門分享 Top '+hot.length+'（'+rangeLabel+' 瀏覽次數）</span></div>'
    + '<table class="hc-tbl">'+hcHead
    + '<tbody>'+hot.map(function(n,i){ return rowHTML(n,i,'#185FA5',true,false); }).join('')+'</tbody></table>'
    + '</div>';
}

function buildSB(){
  let h = '<div class="di" id="di-overview" onclick="sel(\\'overview\\')" style="border-bottom:1px solid #dddcd4;margin-bottom:4px;padding-bottom:.55rem;">'
    + '<span class="dot" style="background:#185FA5;"></span><span class="di-n" style="font-weight:700;color:#185FA5;"><i class="ti ti-layout-dashboard" style="font-size:13px;"></i> 總覽</span>'
    + '</div>';
  COLLEGES.forEach(function(c){
    const depts = c.depts.filter(function(d){ return deptCount(d)>0; });
    if(!depts.length) return;
    const col = collegeColor(c.col);
    h += '<div class="col-h">'+esc(c.col)+'</div>';
    depts.forEach(function(d){
      const n = deptCount(d);
      h += '<div class="di" id="di-dept-'+d+'" onclick="sel(\\'dept-'+d+'\\')">'
        + '<span class="dot" style="background:'+col.dot+'"></span>'
        + '<span class="di-n">'+esc(d)+'<span style="color:#B4B2A9;font-size:12px;margin-left:5px;">'+n+'</span></span>'
        + '</div>';
    });
  });
  document.getElementById('sb-body').innerHTML = h;
}

function renderOverview(){
  const total = SHARE_RAW.length;
  const sinceCut = SHARE_RAW.filter(function(n){ return n.d>=CUT; });
  const dates = SHARE_RAW.map(function(n){ return n.d; }).slice().sort();
  const firstDate = dates[0], lastDate = dates[dates.length-1];
  const monthsSpan = monthsBetween(firstDate, todayStr());
  const avgPerMonth = (total/Math.max(monthsSpan,1)).toFixed(1);

  const deptsWithPosts = Array.from(new Set(SHARE_RAW.map(function(n){ return n.dept; })));

  let insightHTML = '';
  if(sinceCut.length===0){
    insightHTML = '<div class="card" style="border-left:4px solid #E24B4A;">'
      + '<div style="font-size:13.5px;color:#5F5E5A;"><i class="ti ti-alert-triangle" style="color:#E24B4A;"></i> '+AY+'（'
      + jd(CUT) + ' 起）尚無新增分享文章。</div>'
      + '</div>';
  }

  const g = GA4_SHARE;
  let h = ''
    + '<div class="sg-wrap"><span class="sg-arrow"><i class="ti ti-chevrons-right" style="font-size:12px;"></i>左右滑動</span><div class="sg">'
    + '<div class="sc"><div class="sv" style="color:#185FA5;">'+total+'</div><div class="sl"><i class="ti ti-news" style="font-size:13px;"></i><br>全站總篇數</div></div>'
    + '<div class="sc"><div class="sv" style="color:'+(sinceCut.length?'#1D9E75':'#E24B4A')+';">'+sinceCut.length+'</div><div class="sl"><i class="ti ti-calendar-plus" style="font-size:13px;"></i><br>'+AY+'新增</div></div>'
    + '<div class="sc"><div class="sv" style="color:#534AB7;">'+deptsWithPosts.length+'</div><div class="sl"><i class="ti ti-school" style="font-size:13px;"></i><br>已產出系所數</div></div>'
    + '<div class="sc"><div class="sv" style="color:#BA7517;font-size:18px;">'+jd(lastDate)+'</div><div class="sl"><i class="ti ti-calendar" style="font-size:13px;"></i><br>最近發佈日期</div></div>'
    + '<div class="sc"><div class="sv" style="color:#185FA5;">'+avgPerMonth+'</div><div class="sl"><i class="ti ti-chart-bar" style="font-size:13px;"></i><br>全站平均則/月</div></div>'
    + '</div></div>'
    + insightHTML
    + '<div class="card" style="padding:.85rem 1.2rem .7rem;">'
    + '<div style="font-size:13px;font-weight:700;color:#5F5E5A;margin-bottom:10px;">'
    + '<i class="ti ti-chart-line" style="font-size:11px;color:#185FA5;margin-right:4px;"></i>GA4 網站流量（'+jd(g.since)+' ~ '+jd(g.until)+'，/share/ 區段）'
    + '<span style="float:right;font-size:10px;font-weight:400;color:#B4B2A9;">更新：'+g.fetchedAt+'</span>'
    + '</div>'
    + '<div class="sg-wrap"><span class="sg-arrow"><i class="ti ti-chevrons-right" style="font-size:12px;"></i>左右滑動</span><div class="sg" style="grid-template-columns:repeat(3,1fr);">'
    + '<div class="sc"><div class="sv" style="color:#185FA5;font-size:22px;">'+fmtNum(g.pv)+'</div><div class="sl"><i class="ti ti-eye" style="font-size:12px;"></i><br>瀏覽次數</div></div>'
    + '<div class="sc"><div class="sv" style="color:#534AB7;font-size:15px;">'+esc(g.topChannel)+'</div><div class="sl"><i class="ti ti-route" style="font-size:12px;"></i><br>最大流量來源/媒介</div></div>'
    + '<div class="sc"><div class="sv" style="color:#BA7517;font-size:22px;">'+g.avgDur+'<span style="font-size:13px;">秒</span></div><div class="sl"><i class="ti ti-clock" style="font-size:12px;"></i><br>平均停留時間</div></div>'
    + '</div></div>'
    + '<div style="font-size:11.5px;color:#888780;text-align:right;">瀏覽數統計期間：'+jd(g.since)+' ~ '+jd(g.until)+'（GA4資料，非全站歷史累計）</div>'
    + '</div>'
    + '<div class="card" style="padding:.85rem 1.2rem .7rem;">'
    + '<div style="font-size:13px;font-weight:700;color:#5F5E5A;margin-bottom:7px;"><i class="ti ti-chart-bar" style="font-size:11px;color:#1D9E75;margin-right:3px;"></i>年度發佈趨勢（'+firstDate.slice(0,4)+'年起）</div>'
    + yearChart(SHARE_RAW)
    + '</div>'
    + hotColdHTML()
    + '<div style="display:flex;align-items:center;gap:10px;margin:1.4rem 0 .6rem;">'
    + '<div style="flex:1;height:1px;background:#dddcd4;"></div>'
    + '<span style="font-size:11.5px;color:#B4B2A9;font-weight:600;letter-spacing:.05em;white-space:nowrap;"><i class="ti ti-list-details" style="font-size:11px;margin-right:3px;"></i>文章列表</span>'
    + '<div style="flex:1;height:1px;background:#dddcd4;"></div>'
    + '</div>'
    + '<div id="ov-table"></div>';

  document.getElementById('mn').innerHTML = h;
  document.getElementById('mn').scrollTop = 0;
  articleTable('ov-table', SHARE_RAW);
}

function renderDept(deptName){
  const items = SHARE_RAW.filter(function(n){ return n.dept===deptName; });
  const sinceCut = items.filter(function(n){ return n.d>=CUT; });
  const collegeName = items.length ? items[0].college : null;
  const col = collegeColor(collegeName);
  const pvSum = items.reduce(function(s,n){ return s+n.pv; }, 0);

  let h = ''
    + '<div class="card" style="padding:.8rem 1.4rem;border-left:4px solid '+col.dot+';">'
    + '<div class="dn" style="color:'+col.fg+';">'+esc(deptName)+'</div>'
    + '<div class="ds">'+esc(collegeName||'')+' / 學系頁面</div>'
    + '</div>'
    + '<div class="sg-wrap"><span class="sg-arrow"><i class="ti ti-chevrons-right" style="font-size:12px;"></i>左右滑動</span><div class="sg" style="grid-template-columns:repeat(3,1fr);">'
    + '<div class="sc"><div class="sv" style="color:'+col.fg+';">'+items.length+'</div><div class="sl"><i class="ti ti-news" style="font-size:13px;"></i><br>累計篇數</div></div>'
    + '<div class="sc"><div class="sv" style="color:'+(sinceCut.length?'#1D9E75':'#E24B4A')+';">'+sinceCut.length+'</div><div class="sl"><i class="ti ti-calendar-plus" style="font-size:13px;"></i><br>'+AY+'新增</div></div>'
    + '<div class="sc"><div class="sv" style="color:#185FA5;">'+fmtNum(pvSum)+'</div><div class="sl"><i class="ti ti-eye" style="font-size:13px;"></i><br>瀏覽次數合計</div></div>'
    + '</div></div>'
    + '<div class="card" style="padding:.85rem 1.2rem .7rem;">'
    + '<div style="font-size:13px;font-weight:700;color:#5F5E5A;margin-bottom:7px;"><i class="ti ti-chart-bar" style="font-size:11px;color:'+col.dot+';margin-right:3px;"></i>年度發佈趨勢</div>'
    + yearChart(items)
    + '</div>'
    + '<div id="dept-table"></div>';

  document.getElementById('mn').innerHTML = h;
  document.getElementById('mn').scrollTop = 0;
  articleTable('dept-table', items, false);
}

function openSB(){
  document.querySelector('.sb').classList.add('sb-open');
  document.getElementById('sb-overlay').classList.add('sb-open');
}
function closeSB(){
  document.querySelector('.sb').classList.remove('sb-open');
  document.getElementById('sb-overlay').classList.remove('sb-open');
}

function sel(id){
  closeSB();
  if(cur) { const prev=document.getElementById('di-'+cur); if(prev) prev.classList.remove('act'); }
  cur = id;
  const next = document.getElementById('di-'+id);
  if(next) next.classList.add('act');

  if(id==='overview'){ renderOverview(); return; }
  if(id.indexOf('dept-')===0){ renderDept(id.slice(5)); return; }
}

document.getElementById('ayVal').textContent = AY;
document.getElementById('cutVal').textContent = jd(CUT);
document.getElementById('totVal').textContent = SHARE_RAW.length;
document.getElementById('gaRangeVal').textContent = jd(GA4_SHARE.since)+' ~ '+jd(GA4_SHARE.until);
document.getElementById('pvAllVal').textContent = fmtNum(GA4_SHARE.pv);
document.getElementById('builtVal').textContent = BUILT_AT;
buildSB();
sel('overview');
</script>
</body>
</html>
'''

def build():
    items = json.load(open(SHARE_FULL_FILE, encoding="utf-8"))
    ga4 = json.load(open(GA4_FILE, encoding="utf-8"))
    dept_map = json.load(open(DEPT_MAP_FILE, encoding="utf-8"))

    article_dept = dept_map["articleDept"]
    # 「其他」是給查無對應系所的文章（雙聯學位、無法確認簡稱）一個可瀏覽的歸宿，
    # 不屬於 學院系列表.xlsx 的正式結構，所以不放進 map_share_depts.py 的輸出，在這裡才補上。
    colleges = dept_map["colleges"] + [{"col": "其他", "depts": ["未對應系所"]}]

    share_raw = []
    for it in items:
        info = article_dept.get(str(it["id"]), {})
        share_raw.append({
            "id": it["id"],
            "t": it["title"].strip(),
            "url": it["link"],
            "path": urlparse(it["link"]).path,
            "thumb": it.get("thumb") or "",
            "college": info.get("college") or "其他",
            "dept": info.get("dept") or "未對應系所",
            "d": it["post_date"][:10],
        })

    built_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    data_js = (
        "const SHARE_RAW = " + json.dumps(share_raw, ensure_ascii=False) + ";\n"
        "const GA4_SHARE = " + json.dumps(ga4, ensure_ascii=False) + ";\n"
        "const COLLEGES = " + json.dumps(colleges, ensure_ascii=False) + ";\n"
        "const CUT = " + json.dumps(CUT) + ";\n"
        "const AY = " + json.dumps(AY, ensure_ascii=False) + ";\n"
        "const BUILT_AT = " + json.dumps(built_at) + ";"
    )

    html = TEMPLATE.replace("/*__SHARE_DATA__*/", data_js)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print("已產生：", HTML_FILE)
    print(f"   文章總數：{len(share_raw)} 篇")
    print(f"   GA4資料更新：{ga4.get('fetchedAt')}")
    print(f"   頁面建置時間：{built_at}")

if __name__ == "__main__":
    build()

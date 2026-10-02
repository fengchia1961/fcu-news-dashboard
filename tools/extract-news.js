/* 從 index.html（新聞監測儀表板）抽出各系新聞統計 → tools/news.json
   重現 index.html 內 D.forEach 的前置計算邏輯（校網介接判定、非新聞扣除、月分布）
   用法： node tools/extract-news.js                                            */
const fs = require('fs');
const path = require('path');
const BS = String.fromCharCode(92);
const src = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

/* 取出某個 const 宣告的資料字面值（以括號配對切出，再 eval） */
function pick(name) {
  const at = src.indexOf('const ' + name + '=');
  if (at < 0) throw new Error('找不到 const ' + name);
  const open = src.search.call(src, /[\[{]/) && (() => {
    let i = at;
    while (i < src.length && src[i] !== '[' && src[i] !== '{') i++;
    return i;
  })();
  let depth = 0, i = open, end = -1, inStr = null, esc = false;
  for (; i < src.length; i++) {
    const c = src[i];
    if (inStr) {
      if (esc) { esc = false; continue; }
      if (c === BS) { esc = true; continue; }
      if (c === inStr) inStr = null;
      continue;
    }
    if (c === "'" || c === '"' || c === '`') { inStr = c; continue; }
    if (c === '[' || c === '{') depth++;
    else if (c === ']' || c === '}') { depth--; if (depth === 0) { end = i; break; } }
  }
  if (end < 0) throw new Error('括號配對失敗 ' + name);
  return eval('(' + src.slice(open, end + 1) + ')');
}

const CUT = '2025.08.01', CUT_END = '2026.07.31', TGT = 20, MONTHS = 10.5;
const NEWS_REVIEW = pick('NEWS_REVIEW');
const SCHOOL_RAW = pick('SCHOOL_RAW');
const URL_CATS = pick('URL_CATS');
const cols = pick('cols');
const D = pick('D');

const jd = s => s.replace(/-/g, '.');
const SCH_BY_TITLE = new Map(SCHOOL_RAW.map(x => [x.t, x]));
const SCH_BY_URL = new Map(SCHOOL_RAW.filter(x => x.url).map(x => [x.url, x]));
const isNN = n => !!(n.url && (NEWS_REVIEW[n.url] || {}).nn);
const colName = k => (cols.find(c => c.k === k) || {}).name || '';

/* 月份清單（與 buildMonthChart 一致：CUT 當月起，至 CUT_END 或本月，取較早者） */
function monthKeys() {
  const out = [];
  const [cy, cm] = CUT.split('.').map(Number);
  const [ey, em] = CUT_END.split('.').map(Number);
  const endMonth = new Date(ey, em - 1, 1), now = new Date();
  const stop = endMonth < now ? endMonth : now;
  let p = new Date(cy, cm - 1, 1);
  while (p <= stop) {
    out.push(p.getFullYear() + '.' + String(p.getMonth() + 1).padStart(2, '0'));
    p = new Date(p.getFullYear(), p.getMonth() + 1, 1);
  }
  return out;
}
const MKEYS = monthKeys();

const out = {};
D.forEach(d => {
  // 1. 學系自有新聞，判定是否為校網介接
  const deptAf = d.news.filter(n => n.d >= CUT && n.d <= CUT_END).sort((a, b) => b.d.localeCompare(a.d));
  const deptTitles = new Set(deptAf.map(n => n.t));
  const deptUrls = new Set(deptAf.map(n => n.url).filter(Boolean));
  deptAf.forEach(n => {
    const liveCats = n.url ? URL_CATS[n.url] : null;
    const sr = (n.url && SCH_BY_URL.get(n.url)) || (!d.extHost && SCH_BY_TITLE.get(n.t));
    const cats = liveCats || (sr && sr.cats) || [];
    const isFcuUrl = !d.extHost && n.url && n.url.startsWith('https://www.fcu.edu.tw/');
    n.fromSch = !!isFcuUrl || cats.includes(d.name);
    if (n.fromSch) n.schUrl = n.url || (sr && sr.url);
  });

  // 2. 校網有標記此系但學系未轉貼者
  const schOnly = SCHOOL_RAW
    .filter(s => jd(s.d) >= CUT && jd(s.d) <= CUT_END && (s.cats || []).includes(d.name)
                 && !deptTitles.has(s.t) && !deptUrls.has(s.url))
    .map(s => ({ d: jd(s.d), t: s.t, url: s.url, fromSch: true, schUrl: s.url }));

  const af = [...deptAf, ...schOnly].sort((a, b) => b.d.localeCompare(a.d));
  const dNews = af.filter(n => !isNN(n));

  const months = {};
  MKEYS.forEach(k => months[k] = 0);
  af.forEach(n => {
    const k = n.d.slice(0, 7);
    if (k in months) months[k]++;
  });

  out[d.id] = {
    name: d.name,
    college: colName(d.col),
    url: d.url,
    cnt: dNews.length,                                   // 有效新聞則數（達標基準）
    total: af.length,
    nn: af.length - dNews.length,                        // 非新聞（已扣除）
    fromSch: dNews.filter(n => n.fromSch).length,
    self: dNews.filter(n => !n.fromSch).length,
    last: (af[0] && af[0].d) || '—',
    mavg: dNews.length ? (dNews.length / MONTHS).toFixed(1) : '0.0',
    months: MKEYS.map(k => months[k]),
    items: af.map(n => {
      const r = NEWS_REVIEW[n.url] || {};
      const o = { d: n.d, t: n.t, u: (n.fromSch && n.schUrl) || n.url || '', s: n.fromSch ? 1 : 0 };
      if (r.nn) { o.nn = 1; o.why = r.why || ''; }
      return o;
    })
  };
});

fs.writeFileSync(path.join(__dirname, 'news.json'),
  JSON.stringify({ cut: CUT, cutEnd: CUT_END, tgt: TGT, months: MONTHS, mkeys: MKEYS, depts: out }, null, 1), 'utf8');

const ids = Object.keys(out);
console.log('學系', ids.length, '｜新聞總則數', ids.reduce((s, i) => s + out[i].total, 0),
  '｜有效新聞', ids.reduce((s, i) => s + out[i].cnt, 0),
  '｜非新聞', ids.reduce((s, i) => s + out[i].nn, 0));
console.log('月份', MKEYS.length, MKEYS[0], '→', MKEYS[MKEYS.length - 1]);

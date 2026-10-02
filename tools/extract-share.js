/* 從 student-share.html（學生愛分享儀表板）抽出各系篇數與流量 → tools/share.json
   學生愛分享的篇數與瀏覽數一律以該儀表板為唯一來源，請勿在此另行統計。
   用法： node tools/extract-share.js                                            */
const fs = require('fs');
const path = require('path');
const BS = String.fromCharCode(92);

const PROJ = path.join(__dirname, '..');
const src = fs.readFileSync(path.join(PROJ, 'student-share.html'), 'utf8');
const depts = JSON.parse(fs.readFileSync(path.join(__dirname, 'depts.json'), 'utf8'));

/* 取出某個 const 宣告的資料字面值（以括號配對切出，再 JSON.parse） */
function pick(name) {
  const at = src.indexOf('const ' + name + ' =');
  if (at < 0) throw new Error('找不到 const ' + name);
  let open = at;
  while (open < src.length && src[open] !== '[' && src[open] !== '{') open++;
  let depth = 0, inStr = null, esc = false, end = -1;
  for (let i = open; i < src.length; i++) {
    const c = src[i];
    if (inStr) {
      if (esc) { esc = false; continue; }
      if (c === BS) { esc = true; continue; }
      if (c === inStr) inStr = null;
      continue;
    }
    if (c === "'" || c === '"') { inStr = c; continue; }
    if (c === '[' || c === '{') depth++;
    else if (c === ']' || c === '}') { depth--; if (depth === 0) { end = i; break; } }
  }
  if (end < 0) throw new Error('括號配對失敗 ' + name);
  return JSON.parse(src.slice(open, end + 1));
}

const SHARE_RAW = pick('SHARE_RAW');
const GA4 = pick('GA4_SHARE');
const CUT = (src.match(/const CUT = "([^"]+)"/) || [])[1];
const AY = (src.match(/const AY = "([^"]+)"/) || [])[1];
const BUILT_AT = (src.match(/const BUILT_AT = "([^"]+)"/) || [])[1];
if (!CUT || !AY) throw new Error('student-share.html 裡讀不到 CUT／AY');

/* 瀏覽數：與 student-share.html 同一條規則（GA4 pageViews 以 path 對應，無資料記 0） */
SHARE_RAW.forEach(n => { n.pv = GA4.pageViews[n.path] || 0; });

/* 學系名稱 → 健檢 id（學生愛分享端的 dept 已是正式系所全名，可直接對應） */
const idByName = {};
depts.forEach(d => { idByName[d.name] = d.id; });

const byDept = {};
const unmatched = {};
SHARE_RAW.forEach(n => {
  const id = idByName[n.dept];
  if (!id) { unmatched[n.dept] = (unmatched[n.dept] || 0) + 1; return; }
  (byDept[id] = byDept[id] || []).push(n);
});

/* 年度座標軸：全站最早發佈年 ~ 今年，各系共用同一刻度以便互相比較 */
const allYears = SHARE_RAW.map(n => +n.d.slice(0, 4));
const minY = Math.min.apply(null, allYears), maxY = new Date().getFullYear();
const years = [];
for (let y = minY; y <= Math.max(maxY, Math.max.apply(null, allYears)); y++) years.push(y);

const data = {};
depts.forEach(d => {
  const items = (byDept[d.id] || []).slice().sort((a, b) => b.d.localeCompare(a.d));
  const pv = items.reduce((s, n) => s + n.pv, 0);
  const yc = years.map(y => items.filter(n => +n.d.slice(0, 4) === y).length);
  data[d.id] = {
    name: d.name,
    cnt: items.length,
    ay: items.filter(n => n.d >= CUT).length,
    pv: pv,
    avgPv: items.length ? Math.round(pv / items.length) : 0,
    last: items.length ? items[0].d : '',
    first: items.length ? items[items.length - 1].d : '',
    years: yc,
    items: items.map(n => ({ t: n.t, u: n.url, d: n.d, pv: n.pv })),
  };
});

/* 排名：只排有產出的學系（0 篇不佔名次），篇數與瀏覽數各排一次 */
function rank(key) {
  const live = Object.keys(data).filter(id => data[id].cnt > 0);
  live.sort((a, b) => data[b][key] - data[a][key] || data[b].cnt - data[a].cnt);
  live.forEach((id, i) => { data[id][key === 'cnt' ? 'rkCnt' : 'rkPv'] = i + 1; });
  return live.length;
}
const liveN = rank('cnt');
rank('pv');

const totalCnt = SHARE_RAW.length;
const matchedCnt = Object.values(data).reduce((s, v) => s + v.cnt, 0);
const matchedPv = Object.values(data).reduce((s, v) => s + v.pv, 0);

const meta = {
  cut: CUT, ay: AY, builtAt: BUILT_AT,
  gaSince: GA4.since, gaUntil: GA4.until, gaFetched: GA4.fetchedAt,
  gaPv: GA4.pv, gaUsers: GA4.users, gaAvgDur: GA4.avgDur,
  years: years,
  total: totalCnt,              // 全站總篇數（含未對應系所）
  matched: matchedCnt,          // 已對應到健檢學系的篇數
  liveN: liveN,                 // 有產出的學系數（排名分母）
  avgCnt: +(matchedCnt / Math.max(liveN, 1)).toFixed(1),   // 有產出學系的平均篇數
  avgPv: Math.round(matchedPv / Math.max(liveN, 1)),       // 有產出學系的平均瀏覽數
};

fs.writeFileSync(path.join(__dirname, 'share.json'),
  JSON.stringify({ meta: meta, depts: data }, null, 1), 'utf8');

console.log(`學生愛分享：全站 ${totalCnt} 篇，對應到 ${liveN} 個健檢學系共 ${matchedCnt} 篇`);
console.log(`瀏覽數合計 ${matchedPv.toLocaleString()}（GA4 ${GA4.since} ~ ${GA4.until}）`);
const un = Object.keys(unmatched);
if (un.length) console.log('未對應：' + un.map(k => `${k} ${unmatched[k]} 篇`).join('、'));
console.log('→ tools/share.json');

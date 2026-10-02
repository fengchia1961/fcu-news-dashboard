// 從 health-check.html 抽出 DEPTS 資料，輸出改善建議追蹤表所需欄位（JSON）
const fs = require('fs');
const path = require('path');
const BS = String.fromCharCode(92);
const src = fs.readFileSync(path.join(__dirname, '..', 'health-check.html'), 'utf8');
const start = src.indexOf('const DEPTS = [');
if (start < 0) throw new Error('找不到 DEPTS');
// 從 [ 開始做括號配對，找到陣列結尾
const open = src.indexOf('[', start);
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
if (end < 0) throw new Error('括號配對失敗');
const arr = eval(src.slice(open, end + 1));
const out = arr.map(d => ({
  id: d.id, college: d.college, name: d.name, url: d.url,
  overall: d.overall, evaluated: !!d.evaluated,
  priority_issues: d.priority_issues || [],
  pain_points: d.pain_points || [],
  quick_fixes: d.quick_fixes || []
}));
fs.writeFileSync(path.join(__dirname, 'depts.json'), JSON.stringify(out, null, 1), 'utf8');
const n = o => o.reduce((s, x) => s + x, 0);
console.log('學系數', out.length,
  '｜已評估', out.filter(d => d.evaluated).length,
  '｜優先事項', n(out.map(d => d.priority_issues.length)),
  '｜主要問題', n(out.map(d => d.pain_points.length)),
  '｜改善建議', n(out.map(d => d.quick_fixes.length)));

/* 由 tools/improvement-tracker.template.html + tools/depts.json
   產生 improvement-tracker.html（單一檔案、可直接寄給各系同仁）
   用法： node tools/extract-depts.js && node tools/build-tracker.js  */
const fs = require('fs');
const path = require('path');
const root = path.join(__dirname, '..');

const tpl = fs.readFileSync(path.join(__dirname, 'improvement-tracker.template.html'), 'utf8');
const depts = JSON.parse(fs.readFileSync(path.join(__dirname, 'depts.json'), 'utf8'));
const admfixPath = path.join(__dirname, 'admfix.json');
const admfix = fs.existsSync(admfixPath) ? JSON.parse(fs.readFileSync(admfixPath, 'utf8')) : {};

// 只帶入回饋表需要的欄位，縮小檔案
const slim = depts.map(d => ({
  id: d.id, college: d.college, name: d.name, url: d.url, overall: d.overall,
  priority_issues: d.priority_issues, pain_points: d.pain_points, quick_fixes: d.quick_fixes
}));

const d = new Date();
const p = n => String(n).padStart(2, '0');
const built = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
const info = {
  built,
  source: 'health-check.html',
  depts: slim.length,
  priority: slim.reduce((s, x) => s + x.priority_issues.length, 0),
  fixes: slim.reduce((s, x) => s + x.quick_fixes.length, 0)
};

const out = tpl
  .replace('__DEPT_DATA__', JSON.stringify(slim))
  .replace('__BUILD_INFO__', JSON.stringify(info))
  .replace('__ADM_FIX__', JSON.stringify(admfix));

const dest = path.join(root, 'improvement-tracker.html');
if (fs.existsSync(dest)) {
  fs.copyFileSync(dest, dest + '.bak');
  console.log('已備份舊檔 → improvement-tracker.html.bak');
}
fs.writeFileSync(dest, out, 'utf8');
console.log('已產生 improvement-tracker.html');
const nAdm = Object.values(admfix).reduce((s, v) => s + v.length, 0);
console.log(`學系 ${info.depts}｜優先改善事項 ${info.priority}｜具體改善建議 ${info.fixes}｜招生連結待修正 ${nAdm}｜合計待回饋 ${info.priority + info.fixes + nAdm} 項`);
console.log('檔案大小', (Buffer.byteLength(out, 'utf8') / 1024).toFixed(0) + ' KB');

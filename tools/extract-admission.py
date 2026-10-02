# -*- coding: utf-8 -*-
"""從 admission-link-check.html 抽出各系招生連結查核結果 → tools/admission.json

欄位：
  url      系所網址（與 health-check.html 的 DEPTS.url 對應用）
  name     報告中的系所名稱
  college  學院
  units    115 學年度對應招生單位（可能多個）
  levels   學制對應連結 [{t:'學士 ✓', c:'ok', ti:'連結正確'}]
  path     招生頁入口路徑 {text, url, clicks, cc}
  dead     失效連結條數
  issue    查核說明（純文字，無則空字串）
"""
import io, re, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
src = io.open(os.path.join(ROOT, 'admission-link-check.html'), encoding='utf-8').read()

def unesc(t):
    for a, b in [('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'), ('&quot;', '"'), ('&#39;', "'"), ('&nbsp;', ' ')]:
        t = t.replace(a, b)
    return t

def text(html):
    return unesc(re.sub(r'<[^>]+>', '', html)).strip()

out = []
# 逐學院切出表格，再切出每一列
for college, body in re.findall(
        r'<i class="ti ti-building-bank"></i>\s*([^<]+?)<span class="cnt">.*?<tbody>(.*?)</tbody>', src, re.S):
    for row in re.findall(r'<tr>(.*?)</tr>', body, re.S):
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
        if len(tds) != 5:
            print('!! 欄位數異常', college, len(tds)); continue
        c_name, c_lv, c_path, c_dead, c_iss = tds

        m = re.search(r'<a href="([^"]+)"[^>]*>(.*?)</a>', c_name, re.S)
        url, name = (m.group(1), text(m.group(2))) if m else ('', text(c_name))
        units = [text(u) for u in re.findall(r'<span class="un(?: dim)?">(.*?)</span>', c_name, re.S)]
        units = [u for u in units if u and u != '—']

        levels = [{'t': text(t), 'c': c.strip(), 'ti': unesc(ti)}
                  for c, ti, t in re.findall(r'<span class="lv ([a-z]+)"(?: title="([^"]*)")?>(.*?)</span>', c_lv, re.S)]

        pm = re.search(r'<a href="([^"]+)"[^>]*>(.*?)</a>', c_path, re.S)
        clk = re.search(r'<span class="clk ([a-z0-9]+)">(.*?)</span>', c_path, re.S)
        path_txt = text(re.sub(r'<div class="clkwrap">.*?</div>', '', c_path, flags=re.S))
        path = {'text': path_txt,
                'url': pm.group(1) if pm else '',
                'clicks': text(clk.group(2)) if clk else '',
                'cc': clk.group(1) if clk else ''}

        dm = re.search(r'<span class="(zero|dead)">(\d+)</span>', c_dead)
        dead = int(dm.group(2)) if dm else 0

        issue = text(c_iss)
        if issue == '—':
            issue = ''

        out.append({'url': url, 'name': name, 'college': college.strip(), 'units': units,
                    'levels': levels, 'path': path, 'dead': dead, 'issue': issue})

with io.open(os.path.join(HERE, 'admission.json'), 'w', encoding='utf-8', newline='\n') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

print('共', len(out), '站')
print('有查核說明', sum(1 for r in out if r['issue']), '站｜有失效連結', sum(1 for r in out if r['dead']), '站')
print('學制狀態分布', {c: sum(1 for r in out for l in r['levels'] if l['c'] == c)
                      for c in ['ok', 'wk', 'bad', 'nil', 'na']})

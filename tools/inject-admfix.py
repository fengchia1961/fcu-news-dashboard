# -*- coding: utf-8 -*-
"""把招生連結查核的每一項缺失，轉成「改善回饋填寫」分頁裡可逐條回覆的事項。

來源：tools/channel-check.json（狀態為 bad／wk／nil 者）
注入：health-check.html 的 ADM_FIX 常數，並讓 fbItems() 一併納入

用法： python tools/inject-admfix.py
冪等：可重複執行，自動備份。
"""
import io, json, re, shutil, sys, datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
HC = HERE.parent / 'health-check.html'
SRC = HERE / 'channel-check.json'

if not SRC.exists():
    sys.exit('找不到 tools/channel-check.json')

# 管道別 → 官方管道頁（供「應改連」建議）
OFFICIAL = {
    '分發入學': 'college_exam', '繁星推薦': 'college_star', '申請入學': 'college_apply',
    '四技甄選': 'college_s42_interview', '四技技優': 'college_s42_skill',
    '特殊選才': 'college_special', '青年儲蓄四技': 'college_s42_special',
    '運動績優甄試': 'college_sport', '運動績優單招': 'college_sport',
    '學系單招': 'istm_dualdegree', '全校單招': 'istm_dualdegree',
}
BASE = 'https://www.fcu.edu.tw/recurit_list/'
short = lambda u: re.sub(r'^https?://', '', u or '').rstrip('/')

j = json.loads(SRC.read_text(encoding='utf-8'))
fix = {}
for did, rows in j['results'].items():
    items = []
    for r in rows:
        unit = r['name']
        many = len(rows) > 1          # 同一網站掛多個招生單位時標明是哪一個
        page = (r.get('pages') or [''])[0]
        for c in r['channels']:
            s = c['s']
            if s in ('ok', 'ext'):
                continue
            who = f'（{unit}）' if many else ''
            ch, q = c['n'], c['q']
            sug = ''
            if ch in OFFICIAL:
                sug = f'，應改連 {BASE}{OFFICIAL[ch]}/'
            if s == 'bad':
                t = (f'招生連結失效{who}：「{ch}」（{q} 名）的連結實測為 404'
                     f'（{short(c.get("url"))}），位於 {short(c.get("src")) or "招生頁"}{sug}')
            elif s == 'wk':
                why = c.get('why', '連結不正確')
                t = (f'招生連結待修正{who}：「{ch}」（{q} 名）{why}'
                     f'（現連往 {short(c.get("url"))}），位於 {short(c.get("src")) or "招生頁"}{sug}')
            else:   # nil
                where = short(page) or '招生頁（目前找不到招生入口，需先建立）'
                t = f'招生連結缺漏{who}：招生頁未提供「{ch}」（{q} 名）的連結，建議於 {where} 補上{sug[2:] if sug else "對應的官方招生管道頁連結"}'
            items.append({'t': t, 's': s, 'ch': ch, 'q': q})
    if items:
        fix[did] = items

(HERE / 'admfix.json').write_text(json.dumps(fix, ensure_ascii=False, indent=1), encoding='utf-8')

html = HC.read_text(encoding='utf-8')
CONST = 'const ADM_FIX = ' + json.dumps(fix, ensure_ascii=False, separators=(',', ':')) + ';\n'
if 'const ADM_FIX = ' in html:
    html = re.sub(r'const ADM_FIX = \{.*?\};\n', lambda _m: CONST, html, count=1, flags=re.S)
else:
    html = html.replace('const FB_DEPTS = ', CONST + '\nconst FB_DEPTS = ', 1)

# ── fbItems 納入招生連結事項 ──
OLD_ITEMS = """  (d.quick_fixes||[]).forEach((t,i)=>list.push({type:'fx',typeLabel:'具體改善建議',no:String(i+1),text:t,key:d.id+'|fx|'+fbHash(t)}));
  return list;"""
NEW_ITEMS = """  (d.quick_fixes||[]).forEach((t,i)=>list.push({type:'fx',typeLabel:'具體改善建議',no:String(i+1),text:t,key:d.id+'|fx|'+fbHash(t)}));
  (ADM_FIX[d.id]||[]).forEach((x,i)=>list.push({type:'ad',typeLabel:'招生連結待修正',no:'A'+(i+1),text:x.t,key:d.id+'|ad|'+fbHash(x.t)}));
  return list;"""
if OLD_ITEMS in html:
    html = html.replace(OLD_ITEMS, NEW_ITEMS)
elif "type:'ad'" not in html:
    sys.exit('找不到 fbItems 的插入點')

# ── renderFeedback 增加一張卡 ──
OLD_CARD = """  if(!its.length){
    h += `<div class="card"><div class="pending-note">本系於本次健檢未列改善建議，無需回覆。</div></div>`;
  }"""
NEW_CARD = """  const ads = its.filter(i=>i.type==='ad');
  if(ads.length){
    h += `<div class="card"><div class="sec-lbl"><i class="ti ti-link"></i> 🔗 招生連結待修正（依 115 學年度招生管道逐條查核）</div>${ads.map(fbItemCard).join('')}</div>`;
  }
  if(!its.length){
    h += `<div class="card"><div class="pending-note">本系於本次健檢未列改善建議，無需回覆。</div></div>`;
  }"""
if "🔗 招生連結待修正" in html:
    pass                      # 已注入過，不重複插入
elif OLD_CARD in html:
    html = html.replace(OLD_CARD, NEW_CARD, 1)
else:
    sys.exit('找不到 renderFeedback 的插入點')

# 具體改善建議那張卡只放 fx（原本 fxs 已是 filter 過的，確認無誤）
CSS_MARK = '/* ==FB_AD_CSS== */'
if CSS_MARK not in html:
    html = html.replace('/* ==FEEDBACK_CSS_END== */', CSS_MARK + """
.fb-it.ad .fb-it-hd{background:#EEEDFE;border-bottom-color:#d5d2f5;}
.fb-it.ad .fb-it-no{color:#4338ca;border-color:#d5d2f5;}
.fb-it.ad .fb-it-tx{color:#312e81;}
""" + '/* ==FEEDBACK_CSS_END== */')

bak = HC.with_suffix('.html.bak-admfix-' + datetime.datetime.now().strftime('%Y%m%d%H%M'))
shutil.copyfile(HC, bak)
HC.write_text(html, encoding='utf-8', newline='')

n = sum(len(v) for v in fix.values())
by = {}
for v in fix.values():
    for x in v:
        by[x['s']] = by.get(x['s'], 0) + 1
print(f'已產生 {n} 條招生連結待修正事項，涵蓋 {len(fix)} 個學系')
print('  失效 bad', by.get('bad', 0), '｜待修正 wk', by.get('wk', 0), '｜缺漏 nil', by.get('nil', 0))
print('備份：', bak.name, '｜檔案', round(HC.stat().st_size / 1024), 'KB')

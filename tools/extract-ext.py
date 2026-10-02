# -*- coding: utf-8 -*-
"""從總機分機表抽出各系分機（＝改善回饋填寫分頁的登入密碼）→ tools/auth-map.json

用法：
    python tools/extract-ext.py                      # 用預設路徑的分機表
    python tools/extract-ext.py "D:\\...\\總機分機表_115-2.xlsx"

對應方式：以單位名稱去掉括號／空白後比對 tools/depts.json 的學系全名。
分機表查不到、或名稱對不起來的，在 tools/auth-overrides.json 指定。
"""
import json, re, sys, datetime
from pathlib import Path
import openpyxl

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
XLSX = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r'Z:\工讀生\總機分機表_115-1.xlsx')
OUT = HERE / 'auth-map.json'

if not XLSX.exists():
    sys.exit('找不到分機表：%s' % XLSX)

ADMIN_USER = 'fcupubulic'
ADMIN_UNIT = '公共事務組'      # 管理者密碼＝公共事務組分機，一併從分機表取


def norm(s):
    s = re.sub(r'[（(].*?[）)]', '', str(s))
    return s.replace(' ', '').replace('\u200b', '').replace('\xa0', '').strip()


wb = openpyxl.load_workbook(XLSX, data_only=True)
table = {}
for ws in wb.worksheets:
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue
        unit = norm(row[0])
        ext = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ''
        ext = ext.split('、')[0].strip()          # 「2181、2187」取第一個
        if unit and ext and ext != '-' and unit not in table:
            table[unit] = ext

depts = json.loads((HERE / 'depts.json').read_text(encoding='utf-8'))
ov = json.loads((HERE / 'auth-overrides.json').read_text(encoding='utf-8'))

out, miss, guessed, changed = {}, [], [], []
for d in depts:
    o = ov.get(d['id'])
    if isinstance(o, dict) and o.get('hash'):
        # 該單位自行改過密碼（apply-pwd-changes.py 寫入），直接沿用雜湊
        out[d['id']] = {'name': d['name'], 'ext': o.get('ext', ''), 'hash': o['hash'],
                        'from': o.get('from', '自行變更密碼')}
        changed.append((d['id'], d['name'], o.get('from', '')))
        continue
    if isinstance(o, dict) and o.get('ext'):
        out[d['id']] = {'name': d['name'], 'ext': o['ext'], 'from': o.get('from', '人工指定')}
        if o.get('from', '').startswith('代用'):
            guessed.append((d['id'], d['name'], o['ext'], o['from']))
        continue
    ext = table.get(norm(d['name']))
    if ext:
        out[d['id']] = {'name': d['name'], 'ext': ext, 'from': '分機表'}
    else:
        miss.append((d['id'], d['name']))

admin_ext = table.get(ADMIN_UNIT)
if not admin_ext:
    sys.exit('分機表裡找不到「%s」，無法決定管理者密碼' % ADMIN_UNIT)

bad = [(i, v['ext']) for i, v in out.items()
       if not v.get('hash') and not re.fullmatch(r'\d{3,5}', v['ext'])]
if bad:
    print('⚠ 分機格式異常（非 3–5 位數字）：', bad)

admin = {'user': ADMIN_USER, 'ext': admin_ext, 'unit': ADMIN_UNIT}
adm_ov = ov.get('_admin')
if isinstance(adm_ov, dict) and adm_ov.get('hash'):
    admin['hash'] = adm_ov['hash']
    admin['from'] = adm_ov.get('from', '自行變更密碼')

OUT.write_text(json.dumps({
    'src': XLSX.name,
    'built': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
    'admin': admin,
    'depts': out,
}, ensure_ascii=False, indent=1), encoding='utf-8')

print('分機表：%s｜對應成功 %d / %d 系' % (XLSX.name, len(out), len(depts)))
print('管理者：%s / %s' % (ADMIN_USER, '（已自行變更密碼）' if admin.get('hash') else admin_ext + '（%s 分機）' % ADMIN_UNIT))
if changed:
    print('以下單位已自行變更密碼（沿用雜湊，不再套用分機）：')
    for i, n, f in changed:
        print('   - %-16s %-28s %s' % (i, n, f))
if guessed:
    print('以下為推定值，請各單位確認後改 tools/auth-overrides.json：')
    for i, n, e, f in guessed:
        print('   - %-16s %-28s %s　%s' % (i, n, e, f))
if miss:
    print('⚠ 仍查不到分機（這些系將無法登入）：')
    for i, n in miss:
        print('   - %s %s' % (i, n))
print('→ tools/auth-map.json')

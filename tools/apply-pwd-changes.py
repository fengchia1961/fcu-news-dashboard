# -*- coding: utf-8 -*-
"""把各系回傳的「密碼變更檔」寫進 tools/auth-overrides.json，讓新密碼全校生效。

各系在健檢儀表板的「✍️ 改善回饋填寫 → 變更密碼」改完密碼後，按「匯出密碼變更檔」
回傳一個 JSON（裡面只有 SHA-256 雜湊，沒有密碼原文）。公共事務組收到後：

    python tools/apply-pwd-changes.py 密碼變更_inde_2026-10-02.json [更多檔案...]
    python tools/extract-ext.py
    python tools/sync-auth.py

之後重新發布 health-check.html，所有人就都改用新密碼。
要把某個單位還原成預設的分機密碼，直接把它在 auth-overrides.json 裡的
`hash` 欄位刪掉（或整筆刪掉）再重跑後兩支。
"""
import json, re, sys, datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
OV = HERE / 'auth-overrides.json'
SALT = 'fcu-healthcheck-auth-v1'

if len(sys.argv) < 2:
    sys.exit('用法：python tools/apply-pwd-changes.py <密碼變更檔.json> [更多檔案...]')

ov = json.loads(OV.read_text(encoding='utf-8'))
depts = {d['id'] for d in json.loads((HERE / 'depts.json').read_text(encoding='utf-8'))}
ADMIN_U = 'fcupubulic'

applied, skipped = [], []
for arg in sys.argv[1:]:
    p = Path(arg)
    if not p.exists():
        skipped.append((arg, '檔案不存在')); continue
    try:
        j = json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        skipped.append((p.name, '不是合法的 JSON：%s' % e)); continue
    if j.get('format') != 'fcu-healthcheck-pwd-v1':
        skipped.append((p.name, '不是密碼變更檔（format 不符）')); continue
    if j.get('salt') != SALT:
        skipped.append((p.name, 'salt 不符，可能來自不同版本的儀表板')); continue
    for c in j.get('changes', []):
        i, h, rst = c.get('id'), c.get('hash'), bool(c.get('reset'))
        when = c.get('changedAt', '')
        if not i or (not rst and not re.fullmatch(r'[0-9a-f]{64}', str(h or ''))):
            skipped.append((p.name, '資料不完整：%r' % c)); continue
        if i != ADMIN_U and i not in depts:
            skipped.append((p.name, '查無此帳號：%s' % i)); continue

        if rst:
            # 還原為預設分機密碼：把 hash 拿掉即可（ext 與原本的 from 說明保留）
            if i == ADMIN_U:
                ov.pop('_admin', None)
            else:
                prev = ov.get(i) if isinstance(ov.get(i), dict) else None
                if prev:
                    prev.pop('hash', None)
                    # 只剩「變更密碼」的說明文字就整筆清掉；原本就有的 ext 指定要留著
                    if not prev.get('ext'):
                        ov.pop(i, None)
                    elif '變更密碼' in str(prev.get('from', '')):
                        prev['from'] = '還原為預設分機密碼（%s）' % when
            applied.append((p.name, i + '（還原為預設分機密碼）'))
            continue

        if i == ADMIN_U:
            ov['_admin'] = {'hash': h, 'from': '管理者變更密碼（%s）' % when}
        else:
            prev = ov.get(i) if isinstance(ov.get(i), dict) else {}
            ov[i] = {k: v for k, v in prev.items() if k == 'ext'}
            ov[i]['hash'] = h
            ov[i]['from'] = '%s 變更密碼（%s）' % (i, when)
        applied.append((p.name, i))

if not applied:
    print('沒有任何變更被套用。')
else:
    ov['_更新'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    OV.write_text(json.dumps(ov, ensure_ascii=False, indent=2), encoding='utf-8')
    print('已套用 %d 筆密碼變更 → tools/auth-overrides.json' % len(applied))
    for f, i in applied:
        print('   - %-28s（來自 %s）' % (i, f))
    print('\n接著請執行：')
    print('   python tools/extract-ext.py')
    print('   python tools/sync-auth.py')

if skipped:
    print('\n⚠ 略過：')
    for f, why in skipped:
        print('   - %s：%s' % (f, why))

# -*- coding: utf-8 -*-
"""依 115 學年度各系招生管道別，重新檢視各系網站招生頁：
   ① 每一個招生管道是否有相對應之招生連結
   ② 招生頁是否能在兩個點擊內找到

資料來源：health-check.html 的 ADMIT_115（含各系 ch 管道別）與 DEPTS（系網網址）
輸出：tools/channel-check.json

用法：
    python tools/check-admission-channels.py            # 全部
    python tools/check-admission-channels.py inde mse   # 只跑指定學系 id
"""
import io, json, re, sys, time, html as html_mod
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import urljoin, urlparse

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
HC = HERE.parent / 'health-check.html'
OUT = HERE / 'channel-check.json'

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
TIMEOUT = 20
PAUSE = 0.25

# ── 管道別 → 判定關鍵字（出現在連結文字或網址即視為有對應連結）──
KEYS = {
    '分發入學':       ['考試入學分發', '入學分發', '分發入學', '考試分發'],
    '繁星推薦':       ['繁星'],
    '申請入學':       ['申請入學', '個人申請', 'apply_personal', 'personal'],
    '四技甄選':       ['四技二專甄選', '科技校院', '四技甄選', '甄選入學'],
    '四技登記分發':   ['登記分發'],
    '四技技優':       ['技優'],
    '運動績優甄試':   ['運動績優', '運動成績優良', '運動優良'],
    '運動績優單招':   ['運動績優'],
    '全校單招':       ['單獨招生', '單招'],
    '學系單招':       ['單獨招生', '單招'],
    '特殊選才':       ['大學特殊選才', '特殊選才'],
    '單招其他':       ['單獨招生', '單招'],
    '原民分發':       ['原住民'],
    '原民繁星':       ['原住民'],
    '原民申請':       ['原住民'],
    '原民單招':       ['原住民'],
    '資安學研申請':   ['資安', '資通安全'],
    '資安學研特殊選才': ['資安', '資通安全'],
    '青年儲蓄申請':   ['青年儲蓄', '青年教育與就業儲蓄'],
    '青年儲蓄四技':   ['青年儲蓄', '青年教育與就業儲蓄'],
    '四技登記分發':   ['四技二專登記分發', '登記分發'],
    '四技技優外加':   ['技優'],
}
# 管道別 → 官方管道頁網址代號（第一優先比對，比文字可靠）
SLUG = {
    '分發入學':     ['college_exam'],
    '繁星推薦':     ['college_star'],
    '申請入學':     ['college_apply'],
    '四技甄選':     ['college_s42_interview'],
    '四技登記分發': ['college_s42_exam'],
    '四技技優':     ['college_s42_skill'],
    '四技技優外加': ['college_s42_skill'],
    '特殊選才':     ['college_special'],
    '青年儲蓄四技': ['college_s42_special'],
    '學系單招':     ['istm_dualdegree'],
    '全校單招':     ['istm_dualdegree'],
    '運動績優甄試': ['college_sport'],      # 大學運動績優甄試（實測存在）
    '運動績優單招': ['college_sport'],
}

# 學士班管道不得對應到碩博士管道頁
GRAD = ['mastr_', 'master_', 'phd', 'doctor']
# 已知管道頁 slug → 所屬管道（用於偵測「連結與文字不符」）
SLUG_OWNER = {sl: nm for nm, sls in {
    '分發入學': ['college_exam'], '繁星推薦': ['college_star'], '申請入學': ['college_apply'],
    '四技甄選': ['college_s42_interview'], '四技技優': ['college_s42_skill'],
    '特殊選才': ['college_special'], '青年儲蓄四技': ['college_s42_special'],
}.items() for sl in sls}

# 招生頁入口的判定（導覽列文字）
ADM_NAV = ['招生', '入學', 'admission', 'apply', 'recruit']
# 全校招生總覽頁（只連到這裡 → 僅連總覽頁）
OVERVIEW = ['www.fcu.edu.tw/apply', 'www.fcu.edu.tw/admission']   # 全校招生總覽頁；recurit_list 為官方管道頁

_cache = {}


def fetch(url, tries=3):
    """取得頁面；逾時或連線錯誤重試，HTTP 錯誤碼直接回傳（不重試）"""
    if url in _cache:
        return _cache[url]
    import urllib.error
    last = ''
    for i in range(tries):
        try:
            r = urlopen(Request(url, headers={'User-Agent': UA}), timeout=TIMEOUT)
            body = r.read().decode('utf-8', errors='ignore')
            _cache[url] = (r.status, body)
            break
        except urllib.error.HTTPError as e:
            _cache[url] = (e.code, '')
            break
        except Exception as e:
            last = f'{type(e).__name__}: {e}'
            if i < tries - 1:
                time.sleep(1.2 * (i + 1))
    else:
        _cache[url] = (0, '')
        print(f'    ⚠ 取得失敗（重試 {tries} 次）{url}：{last}')
    time.sleep(PAUSE)
    return _cache[url]


def head_ok(url):
    """實際請求並判斷是否為有效頁面（非 404 / 非錯誤頁）"""
    st, body = fetch(url)
    if st == 0:
        return False, '重試 3 次仍無法連線'
    if st >= 400:
        return False, f'HTTP {st}'
    low = body[:4000]
    if re.search(r'404\s*(not found|錯誤|找不到)|頁面不存在|page not found', low, re.I):
        return False, '內容為 404 頁'
    return True, ''


LINK_RE = re.compile(r'<a\b[^>]*href\s*=\s*["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', re.S | re.I)
TAG_RE = re.compile(r'<[^>]+>')


def links_of(url, body):
    out = []
    for href, text in LINK_RE.findall(body):
        t = html_mod.unescape(TAG_RE.sub('', text)).strip()
        t = re.sub(r'\s+', ' ', t)
        if not href or href.lower().startswith(('javascript:', 'mailto:', 'tel:')):
            continue
        out.append((urljoin(url, href), t))
    return out


def find_admission_pages(site):
    """回傳 (招生頁清單, 點擊深度, 路徑說明)"""
    st, body = fetch(site)
    if st == 0:
        return [], 0, '首頁無法連線'
    host = urlparse(site).netloc
    ls = links_of(site, body)
    # 1 次點擊：首頁上直接連往本站的招生頁
    first = []
    for u, t in ls:
        if urlparse(u).netloc != host:
            continue
        hay = (t + ' ' + u).lower()
        if any(k.lower() in hay for k in ADM_NAV):
            first.append((u, t))
    # 去重、排除首頁本身
    seen, pages = set(), []
    for u, t in first:
        key = u.rstrip('/')
        if key == site.rstrip('/') or key in seen:
            continue
        seen.add(key)
        pages.append((u, t))
    if pages:
        return pages[:6], 1, '首頁 → ' + (pages[0][1] or '招生')
    # 2 次點擊：進入第一層頁面再找
    for u, t in ls[:40]:
        if urlparse(u).netloc != host:
            continue
        st2, b2 = fetch(u)
        if st2 == 0:
            continue
        sub = [(x, y) for x, y in links_of(u, b2)
               if urlparse(x).netloc == host and any(k.lower() in (y + ' ' + x).lower() for k in ADM_NAV)]
        if sub:
            return sub[:6], 2, f'首頁 → {t or "次頁"} → {sub[0][1] or "招生"}'
    return [], 0, '首頁與導覽列皆無招生入口'


def check_unit(unit, site):
    res = {'name': unit['n'], 'site': site, 'channels': [], 'clicks': 0, 'path': '', 'deadLinks': []}
    pages, clicks, path = find_admission_pages(site)
    res['clicks'], res['path'] = clicks, path
    res['pages'] = [u for u, _ in pages]

    # 蒐集招生頁上的連結，並往下追一層招生子頁（如 /enrollment/college、/apply/undergraduate）
    SUB = ['學士', '大學部', '本國生', '日間', 'undergrad', 'college', '招生', '入學']
    host = urlparse(site).netloc
    visited, all_links, extra = set(), [], []
    for u, _ in pages:
        st, b = fetch(u)
        if not st:
            continue
        visited.add(u.rstrip('/'))
        ls = links_of(u, b)
        all_links += [(x, t, u) for x, t in ls]
        base = u.rstrip('/').rsplit('/', 1)[0] + '/'
        for x, t in ls:
            if urlparse(x).netloc != host or x.rstrip('/') in visited:
                continue
            hay = (t + ' ' + x).lower()
            if x.startswith(base) or any(k.lower() in hay for k in SUB):
                if x not in extra:
                    extra.append(x)
    for x in extra[:10]:                      # 最多再追 10 個子頁
        if x.rstrip('/') in visited:
            continue
        visited.add(x.rstrip('/'))
        st, b = fetch(x)
        if st:
            all_links += [(y, t, x) for y, t in links_of(x, b)]
            res.setdefault('subPages', []).append(x)

    for ch in unit.get('ch', []):
        name, quota = ch['n'], ch['q']
        if ch.get('x'):          # 外加名額：隨主管道一併報名，系網無須獨立連結
            res['channels'].append({'n': name, 'q': quota, 's': 'ext',
                                    'why': '外加名額，併於主管道報名'})
            continue
        keys = KEYS.get(name, [name])
        slugs = SLUG.get(name, [])

        # (1) 以官方管道頁網址代號精準比對
        pick, kind = None, ''
        for sl in slugs:
            for u, t, src in all_links:
                if '/' + sl in u:
                    pick, kind = (u, t, src), 'slug'
                    break
            if pick:
                break
        # (2) 退而求其次：以連結文字比對
        hits = [(u, t, src) for u, t, src in all_links
                if any(k.lower() in (t + ' ' + u).lower() for k in keys)
                and not any(g in u.lower() for g in GRAD)]      # 排除碩博士管道頁
        if not pick and hits:
            chan = [h for h in hits if 'recurit_list' in h[0] or 'national_list' in h[0]]
            over = [h for h in hits if any(o in h[0] for o in OVERVIEW)]
            if chan:
                pick, kind = chan[0], 'text-channel'
            elif over:
                pick, kind = over[0], 'overview'
            else:
                pick, kind = hits[0], 'other'
        if not pick:
            res['channels'].append({'n': name, 'q': quota, 's': 'nil', 'why': '招生頁找不到對應連結'})
            continue

        ok, why = head_ok(pick[0])
        rec = {'n': name, 'q': quota, 'url': pick[0], 't': pick[1], 'src': pick[2]}
        if not ok:
            rec.update(s='bad', why=why)
            res['deadLinks'].append(pick[0])
        elif kind == 'overview':
            rec.update(s='wk', why='僅連全校招生總覽頁')
        elif kind == 'other':
            rec.update(s='wk', why='連往說明或自站頁面，非官方招生管道頁')
        elif kind == 'text-channel' and any(
                ('/' + sl) in pick[0] and owner != name for sl, owner in SLUG_OWNER.items()):
            other = next(o for sl, o in SLUG_OWNER.items() if ('/' + sl) in pick[0])
            rec.update(s='wk', why=f'連結與文字不符，實際連往「{other}」管道頁')
        else:
            rec.update(s='ok')
        res['channels'].append(rec)
    return res


def main():
    s = HC.read_text(encoding='utf-8')
    A = json.loads(re.search(r'const ADMIT_115 = (\{.*?\});\n', s, re.S).group(1))
    D = {d['id']: d['url'] for d in json.loads((HERE / 'depts.json').read_text(encoding='utf-8'))}

    want = set(sys.argv[1:])
    jobs = []
    for c in A['colleges']:
        for u in c['units']:
            if not u.get('ch'):
                continue
            did = u.get('did')
            site = D.get(did)
            if not site:
                continue
            if want and did not in want:
                continue
            jobs.append((c['name'], u, site))

    print(f'待檢查 {len(jobs)} 個學士班招生單位\n')
    out = {}
    for i, (col, u, site) in enumerate(jobs, 1):
        print(f'[{i}/{len(jobs)}] {u["n"]}  {site}')
        r = check_unit(u, site)
        r['college'] = col
        r['did'] = u.get('did')
        out.setdefault(u.get('did'), []).append(r)
        n = {'ok': 0, 'wk': 0, 'bad': 0, 'nil': 0, 'ext': 0}
        for ch in r['channels']:
            n[ch['s']] += 1
        print(f'    點擊 {r["clicks"] or "找不到"}｜✓{n["ok"]} △{n["wk"]} ✗{n["bad"]} —{n["nil"]} ＋外加{n["ext"]}')

    OUT.write_text(json.dumps({'checked': time.strftime('%Y-%m-%d'), 'results': out},
                              ensure_ascii=False, indent=1), encoding='utf-8')
    tot = {'ok': 0, 'wk': 0, 'bad': 0, 'nil': 0, 'ext': 0}
    for rs in out.values():
        for r in rs:
            for ch in r['channels']:
                tot[ch['s']] += 1
    print(f'\n完成｜管道別合計 {sum(tot.values())} 項：'
          f'✓連結正確 {tot["ok"]}　△僅連總覽頁 {tot["wk"]}　✗失效 {tot["bad"]}　—無對應連結 {tot["nil"]}　＋外加名額 {tot["ext"]}')
    print('輸出：', OUT)


if __name__ == '__main__':
    main()

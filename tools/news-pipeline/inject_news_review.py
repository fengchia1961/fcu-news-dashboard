# -*- coding: utf-8 -*-
"""
inject_news_review.py — 將 v4.0 審核的「非新聞」判定注入儀表板。

依使用者決定（2026-08-01），v4.0 在儀表板上**只標示非新聞**，不顯示完整度/照片建議。

動作（冪等，可重複執行）：
 1. 備份儀表板 HTML
 2. 注入／更新 `const NEWS_REVIEW={url:{nn:1,why:'理由'},...}`（插在 function grd 之前）
 3. 於各系新聞列表的來源欄加上「非新聞」標籤（滑鼠移上顯示判定理由）

用法：python inject_news_review.py
資料來源：article_review_v4.json
"""

# ── 路徑已改為相對本專案（2026-10-01 從「工具程式」資料夾搬入）──
# 本檔位置：fcu-news-dashboard/tools/news-pipeline/
from pathlib import Path as _P
PROJ = _P(__file__).resolve().parents[2]   # fcu-news-dashboard/
HERE = _P(__file__).resolve().parent       # tools/news-pipeline/
DASHBOARD = PROJ / 'index.html'            # 新聞監測儀表板

import sys, io, os, re, json, shutil, datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = str(DASHBOARD)
REVIEW_FILE = os.path.join(BASE, 'article_review_v4.json')

BADGE = ("${(NEWS_REVIEW[n.url]||{}).nn?`<span style=\"display:inline-block;font-size:11px;"
         "padding:2px 8px;border-radius:4px;background:#FBE9E7;color:#B3261E;font-weight:700;"
         "border:1px solid #F5C6C0;margin-left:4px;cursor:help;\" title=\"經 v4.0 審核判定為非新聞"
         "（${esc((NEWS_REVIEW[n.url]||{}).why||'')}）——公告、報名、招生等內容不屬新聞稿\">"
         "非新聞</span>`:''}")


def main():
    with open(REVIEW_FILE, encoding='utf-8') as f:
        review = json.load(f)

    # 只保留非新聞者，體積最小
    nn = {u: {'nn': 1, 'why': v.get('non_news_keyword') or ''}
          for u, v in review.items() if v['verdict'] == '🔴 非新聞'}
    js = 'const NEWS_REVIEW=' + json.dumps(nn, ensure_ascii=False, separators=(',', ':')) + ';'

    raw = open(HTML_FILE, 'rb').read()
    has_bom = raw[:3] == b'\xef\xbb\xbf'
    content = raw.decode('utf-8-sig').replace('\r\n', '\n')

    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak = os.path.join(BASE, f'FCU新聞監測儀表板_backup_{stamp}.html')
    shutil.copy2(HTML_FILE, bak)
    print(f'備份 → {bak}')

    # ── 1. 注入或更新 NEWS_REVIEW ──
    if 'const NEWS_REVIEW=' in content:
        content = re.sub(r'const NEWS_REVIEW=\{.*?\};', js, content, count=1, flags=re.S)
        print(f'更新 NEWS_REVIEW（{len(nn)} 篇非新聞）')
    else:
        anchor = 'function grd(tot){'
        if anchor not in content:
            print('錯誤：找不到插入點 function grd'); sys.exit(1)
        block = ('// ── NEWS_REVIEW：v4.0 審核之非新聞判定'
                 '（review_news_v4.py 產生）──\n' + js + '\n\n')
        content = content.replace(anchor, block + anchor, 1)
        print(f'注入 NEWS_REVIEW（{len(nn)} 篇非新聞）')

    # ── 2. 於來源欄加上標籤（僅在尚未加過時）──
    old_cell = '<td class="stk-badge" style="text-align:center;">${srcBdg}</td>'
    new_cell = f'<td class="stk-badge" style="text-align:center;">${{srcBdg}}{BADGE}</td>'
    if 'NEWS_REVIEW[n.url]' in content:
        print('列表標籤：已存在，略過')
    elif old_cell in content:
        content = content.replace(old_cell, new_cell, 1)
        print('列表標籤：已加入')
    else:
        print('警告：找不到來源欄位樣板，標籤未加入')

    out = (b'\xef\xbb\xbf' if has_bom else b'') + content.replace('\n', '\r\n').encode('utf-8')
    open(HTML_FILE, 'wb').write(out)
    print('完成，已寫回儀表板。')


if __name__ == '__main__':
    main()

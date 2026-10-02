#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FCU 新聞監測儀表板 — 增量更新腳本
=====================================================
用法：
  python update_fcu_news.py           # 增量更新（只抓新文章，保留既有評分）
  python update_fcu_news.py --force   # 強制全量重爬（清空快取重新抓）
  python update_fcu_news.py --dept mse  # 只更新指定學系

排程：每月 1 日 09:00 自動執行
"""

# ── 路徑已改為相對本專案（2026-10-01 從「工具程式」資料夾搬入）──
# 本檔位置：fcu-news-dashboard/tools/news-pipeline/
from pathlib import Path as _P
PROJ = _P(__file__).resolve().parents[2]   # fcu-news-dashboard/
HERE = _P(__file__).resolve().parent       # tools/news-pipeline/
DASHBOARD = PROJ / 'index.html'            # 新聞監測儀表板


import json, re, sys, time, os, io
from datetime import datetime, date, timedelta
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError
from html.parser import HTMLParser
import xml.etree.ElementTree as ET

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ── 設定 ──────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
CACHE_FILE  = HERE / "fcu_news_cache.json"
HTML_FILE   = DASHBOARD
CUT         = "2025.08.01"
CUT_END     = "2026.07.31"   # 114學年度上限：發佈時間須落在 [CUT, CUT_END]（2026-08-10 使用者指示）
CUT_ISO     = "2025-08-01"
MONTHS      = 10.5
FORCE       = "--force" in sys.argv
ONLY_DEPT   = None
if "--dept" in sys.argv:
    idx = sys.argv.index("--dept")
    if idx + 1 < len(sys.argv):
        ONLY_DEPT = sys.argv[idx + 1]

HEADERS = {"User-Agent": "FCU-NewsBot/2.0 (contact@fcu.edu.tw)"}

# ── 學系清單（54 個單位）───────────────────────────
# 名稱與清單一律以逢甲官網 organization/<college>-units 為準（使用者指示 2026-08-07），
# 對照表見 claude code\official_depts.json，比對與補齊由 inject_missing_depts.py 處理。
#
# ⚠ 只收「該系網站自有的文章」：這批系網有一半的 /news/ 列表頁是整頁轉貼校網
#   （www.fcu.edu.tw/news/…）的內容，imem 與 nze 甚至是一模一樣的 60 篇。
#   照抄會讓它們在儀表板上變成發文最多的系所，而那些文章早已在 SCHOOL_RAW 裡。
#   fetch_dept_news() 第 1 頁走 RSS（/news/feed/，實測 100% 為自站文章）所以天然乾淨；
#   若哪天系網改版讓 parse_wp_news_page() 開始吃到轉貼內容，要記得在這裡加自站網域過濾。
DEPT_LIST = [
    # 工程與科學學院
    {"id":"aero",     "col":"eng", "name":"航太與系統工程學系",           "url":"https://aero.fcu.edu.tw/news/"},
    {"id":"mse",      "col":"eng", "name":"材料科學與工程學系",           "url":"https://mse.fcu.edu.tw/news/"},
    {"id":"mcae",     "col":"eng", "name":"機械與電腦輔助工程學系",       "url":"https://mcae.fcu.edu.tw/news/"},
    {"id":"fcm",      "col":"eng", "name":"纖維與複合材料學系",           "url":"https://fcm.fcu.edu.tw/news/"},
    {"id":"inde",     "col":"eng", "name":"工業工程與系統管理學系",       "url":"https://inde.fcu.edu.tw/news/"},
    {"id":"che",      "col":"eng", "name":"化學工程學系",                 "url":"https://che.fcu.edu.tw/news/"},
    {"id":"apmath",   "col":"eng", "name":"應用數學系",                   "url":"https://apmath.fcu.edu.tw/news/"},
    {"id":"ees",      "col":"eng", "name":"環境工程與科學學系",           "url":"https://ees.fcu.edu.tw/news/"},
    {"id":"photonics","col":"eng", "name":"光電科學與工程學系",           "url":"https://photonics.fcu.edu.tw/news/"},
    {"id":"psd",      "col":"eng", "name":"精密系統設計學士學位學程",     "url":"https://psd.fcu.edu.tw/news/"},
    {"id":"earmp",    "col":"eng", "name":"電聲碩士學位學程",             "url":"https://earmp.fcu.edu.tw/news/"},
    {"id":"gest",     "col":"eng", "name":"綠色能源科技碩士學位學程",     "url":"https://gest.fcu.edu.tw/news/"},
    {"id":"ds",       "col":"eng", "name":"數據科學碩士學位學程",         "url":"https://ds.fcu.edu.tw/news/"},
    {"id":"imem",     "col":"eng", "name":"智能製造與工程管理碩士在職學位學程", "url":"https://imem.fcu.edu.tw/news/"},
    {"id":"mae",      "col":"eng", "name":"機械與航空工程博士學位學程",   "url":"https://mae.fcu.edu.tw/news/"},
    {"id":"space",    "col":"eng", "name":"太空系統工程碩士學位學程",     "url":"https://space.fcu.edu.tw/news/"},
    {"id":"nze",      "col":"eng", "name":"學士後工程與科學學院淨零智慧永續學士班", "url":"https://nze.fcu.edu.tw/news/"},
    # 商學院
    {"id":"acct",     "col":"biz", "name":"會計學系",                     "url":"https://acct.fcu.edu.tw/news/"},
    {"id":"itra",     "col":"biz", "name":"國際經營與貿易學系",           "url":"https://itra.fcu.edu.tw/news/"},
    {"id":"biba",     "col":"biz", "name":"國際企業管理全英語學士班",     "url":"https://biba.fcu.edu.tw/news/"},
    {"id":"pf",       "col":"biz", "name":"財稅學系",                     "url":"https://pf.fcu.edu.tw/news/"},
    {"id":"coop",     "col":"biz", "name":"合作經濟暨社會事業經營學系",   "url":"https://coop.fcu.edu.tw/news/"},
    {"id":"stat",     "col":"biz", "name":"統計學系",                     "url":"https://stat.fcu.edu.tw/news/"},
    {"id":"econ",     "col":"biz", "name":"經濟學系",                     "url":"https://econ.fcu.edu.tw/news/"},
    {"id":"ba",       "col":"biz", "name":"企業管理學系",                 "url":"https://ba.fcu.edu.tw/news/"},
    {"id":"mkt",      "col":"biz", "name":"行銷學系",                     "url":"https://marketing.fcu.edu.tw/news/"},
    {"id":"bce",      "col":"biz", "name":"商學學士學位學程",             "url":"https://bce.fcu.edu.tw/news/"},
    {"id":"econlaw",  "col":"biz", "name":"財經法律研究所",               "url":"https://econlaw.fcu.edu.tw/news/"},
    # 商學專業碩士在職(bm)、商學博士(bphd) 是 Google Sites，最新消息無獨立網址、抓不到，
    # 不列在此清單；兩者以 extHost:1 的空殼形式由 inject_missing_depts.py 寫入並原樣保留
    # 金融學院
    {"id":"rmi",      "col":"fin", "name":"風險管理與保險學系",           "url":"https://rmi.fcu.edu.tw/news/"},
    {"id":"fina",     "col":"fin", "name":"財務金融學系",                 "url":"https://fina.fcu.edu.tw/news/"},
    {"id":"bpfeas",   "col":"fin", "name":"財務工程與精算學士學位學程",   "url":"https://bpfeas.fcu.edu.tw/news/"},
    {"id":"upfc",     "col":"fin", "name":"金融學院學士班",               "url":"https://upfc.fcu.edu.tw/news/"},
    # 人文社會學院
    {"id":"cl",       "col":"hum", "name":"中國文學系",                   "url":"https://cl.fcu.edu.tw/news/"},
    {"id":"fll",      "col":"hum", "name":"外國語文學系",                 "url":"https://fll.fcu.edu.tw/news/"},
    # ghhr（歷史與文物研究所）、cohss（人文社會學士學位學程）：不在使用者提供的官方學系表中，
    # 2026-08-10 使用者指示自儀表板移除，勿再加回 DEPT_LIST
    {"id":"gipp",     "col":"hum", "name":"公共事務與社會創新研究所",     "url":"https://gipp.fcu.edu.tw/news/"},
    {"id":"csi",      "col":"hum", "name":"文化與社會創新碩士學位學程",   "url":"https://csi.fcu.edu.tw/news/"},
    # 資訊電機學院
    # 資訊工程學系（真實網域為 iecs.fcu.edu.tw，非 WordPress 的 Porto CMS、無 RSS）
    # 不在此清單管理，改由 inject_iecs.py 專門抓取寫入 id:'iecs'，見該檔案說明
    {"id":"ee",       "col":"ece", "name":"電機工程學系",                 "url":"https://ee.fcu.edu.tw/news/"},
    {"id":"fcuece",   "col":"ece", "name":"電子工程學系",                 "url":"https://fcuece.fcu.edu.tw/news/"},
    {"id":"auto",     "col":"ece", "name":"自動控制工程學系",             "url":"https://auto.fcu.edu.tw/news/"},
    {"id":"ce",       "col":"ece", "name":"通訊工程學系",                 "url":"https://ce.fcu.edu.tw/news/"},
    {"id":"upiee",    "col":"ece", "name":"資訊電機學院學士班",           "url":"https://upiee.fcu.edu.tw/news/"},
    {"id":"ics",      "col":"ece", "name":"資通安全碩士學位學程",         "url":"https://ics.fcu.edu.tw/news/"},
    {"id":"bmie",     "col":"ece", "name":"生醫資訊暨生醫工程碩士學位學程","url":"https://bmie.fcu.edu.tw/news/"},
    {"id":"gece",     "col":"ece", "name":"電機與通訊工程博士學位學程",   "url":"https://gece.fcu.edu.tw/news/"},
    {"id":"pbiecs",   "col":"ece", "name":"資訊工程學系學士後專班",       "url":"https://pbiecs.fcu.edu.tw/news/"},
    {"id":"miee",     "col":"ece", "name":"資訊電機工程碩士在職學位學程", "url":"https://miee.fcu.edu.tw/news-list/"},
    # rdms（產業研發碩士專班）為 events-list/?id= 動態頁、JS 渲染，靜態抓取抓不到列表，
    # 不列入本清單；沿用既有 D 內容，如需更新須人工核對
    # 建設學院
    {"id":"civil",    "col":"con", "name":"土木工程學系",                 "url":"https://civil.fcu.edu.tw/news/"},
    {"id":"he",       "col":"con", "name":"水利工程與資源保育學系",       "url":"https://he.fcu.edu.tw/news/"},
    {"id":"up",       "col":"con", "name":"都市計畫與空間資訊學系",       "url":"https://up.fcu.edu.tw/news/"},
    {"id":"tl",       "col":"con", "name":"運輸與物流學系",               "url":"https://tl.fcu.edu.tw/news/"},
    {"id":"lm",       "col":"con", "name":"土地管理學系",                 "url":"https://lm.fcu.edu.tw/news/"},
    {"id":"mppm",     "col":"con", "name":"專案管理碩士在職學位學程",     "url":"https://mppm.fcu.edu.tw/news/"},
    {"id":"mcd",      "col":"con", "name":"建設碩士在職學位學程",         "url":"https://mcd.fcu.edu.tw/news/"},
    {"id":"gche",     "col":"con", "name":"建設規劃與工程博士學位學程",   "url":"https://gche.fcu.edu.tw/news/"},
    {"id":"imsc",     "col":"con", "name":"智慧城市碩士學位學程",         "url":"https://imsc.fcu.edu.tw/news-list/"},
    {"id":"cocd",     "col":"con", "name":"建設學院",                     "url":"https://cocd.fcu.edu.tw/news/"},
    # 經營管理學院
    {"id":"smd",      "col":"mgt", "name":"經營管理學院",                 "url":"https://smd.fcu.edu.tw/news/"},
    # 國際科技與管理學院 / 建築專業學院
    # 兩院的 10／7 個雙聯學程共用同一個網站，逐一列會讓同一批文章重複 10 次，
    # 因此比照 smd（經營管理學院）以「學院層級一筆」處理
    {"id":"istm",      "col":"istm","name":"國際科技與管理學院",          "url":"https://istm.fcu.edu.tw/news/"},
    {"id":"archschool","col":"arch","name":"建築專業學院",                "url":"https://archschool.fcu.edu.tw/news/"},
    # 室內設計學士學位學程：官網清單列在建築專業學院，2026-08-07 由商學院改掛此處
    {"id":"id",        "col":"arch","name":"室內設計學士學位學程",        "url":"https://id.fcu.edu.tw/news/"},
    # 通識 / 創能
    {"id":"pmp",      "col":"gen", "name":"全校國際生大一不分系學士班",   "url":"https://pmp.fcu.edu.tw/news/"},
    # pe（體育教學中心）：不在使用者提供的官方學系表中，2026-08-10 使用者指示自儀表板移除，
    # 勿再加回 DEPT_LIST
    {"id":"aita",     "col":"cre", "name":"人工智慧技術與應用學士學位學程","url":"https://aita.fcu.edu.tw/news/"},
    {"id":"aitm",     "col":"cre", "name":"人工智慧科技與管理碩士學位學程","url":"https://aitm.fcu.edu.tw/news/"},
    # 工程與科學學院（追加，2026-08-10 使用者提供清單新增）
    # 產業碩士專班：官網 /news/ 為 404，實際列表在 /release/（news-detail/?id= 動態主題）
    {"id":"iem",      "col":"eng", "name":"產業碩士專班",                 "url":"https://iem.fcu.edu.tw/release/"},
]

# ── 評分函數（與 JS autoSc 對應）────────────────
def auto_score(title: str, date_str: str):
    """回傳 (g, v, a) 各維度分數，與 JS autoSc 邏輯一致"""
    # 1. 時效 GEO (40分)
    is_recent = True
    ev = re.search(r'(\d{1,2})月(\d{1,2})日', title)
    if ev and date_str:
        try:
            y, m, d = map(int, date_str.replace('-','.').split('.'))
            pub = date(y, m, d)
            em, ed = int(ev.group(1)), int(ev.group(2))
            ey = y - 1 if em > m else y
            ev_d = date(ey, em, ed)
            diff = (pub - ev_d).days
            is_recent = 0 <= diff <= 7
        except Exception:
            pass
    has_num     = bool(re.search(r'\d+[人組件萬%名屆強校所位項]', title))
    has_acronym = bool(re.search(r'AI|GEO|MOU|NVIDIA|IEET|EUR-ACE|WBC|ESG|SDG|USR|IEEE|ISO|RTX|AAIS|APT|AIA', title))
    has_rank    = bool(re.search(r'全國[冠亞季]軍|全國第[一二三1-3]|全球排名|世界前\d|四強|蟬聯|冠軍', title))
    has_geo = has_num or has_acronym or has_rank
    g = (40 if has_geo else 30) if is_recent else (20 if has_geo else 10)

    # 2. 視覺版面 (30分)
    if re.search(r'公告|甄選|作業|招生|通知|截止|規定|注意事項|辦理|開放申|月報', title):
        v = 0
    elif re.search(r'競賽|頒獎|典禮|畢典|成果展|發表會|音樂會|展覽|盛典|簽署|訪問|參訪|黑客松|馬拉松|錦標賽|授旗|授證', title):
        v = 30
    elif re.search(r'論文|研究|期刊|升等|入選|獲聘|學報|計畫通過', title):
        v = 10
    else:
        v = 20

    # 3. 語氣真誠 (30分)
    if re.search(r'相關事項|作業規定|甄選公告|注意事項|依規辦理|敬請|依規定|填報', title):
        a = 0
    elif re.search(r'展現.{0,5}量能|再創佳績|大放異彩|豐碩成果|矚目成就|精彩呈現|卓越表現|璀璨|耀眼|亮眼|深耕|締造|強強聯手', title):
        a = 10
    elif re.search(r'引領|探索|思索|體驗|走進|漫談|分享|訪談|對談|翻轉|返校|守護|陪伴|聆聽|重塑|攜手|用心', title):
        a = 30
    else:
        a = 20

    return g, v, a

# ── HTTP 抓取工具 ──────────────────────────────
def fetch(url: str, timeout=20) -> str:
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=timeout) as r:
            enc = r.headers.get_content_charset() or 'utf-8'
            return r.read().decode(enc, errors='replace')
    except Exception as e:
        print(f"  ⚠ 抓取失敗 {url}: {e}")
        return ""

# ── RSS 解析（校網 + 部分學系支援）──────────────
def parse_rss(xml_text: str) -> list:
    """回傳 [{"d": "YYYY.MM.DD", "t": title, "url": link, "cats": [...]}]"""
    items = []
    try:
        root = ET.fromstring(xml_text)
        ns = {'dc': 'http://purl.org/dc/elements/1.1/',
              'content': 'http://purl.org/rss/1.0/modules/content/'}
        for item in root.iter('item'):
            title = (item.findtext('title') or '').strip()
            link  = (item.findtext('link')  or '').strip()
            pub   = item.findtext('pubDate') or ''
            cats  = [c.text.strip() for c in item.findall('category') if c.text]
            # 日期轉 YYYY.MM.DD
            d_str = ''
            m = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', pub)
            if m:
                MONTHS_MAP = {'Jan':'01','Feb':'02','Mar':'03','Apr':'04',
                              'May':'05','Jun':'06','Jul':'07','Aug':'08',
                              'Sep':'09','Oct':'10','Nov':'11','Dec':'12'}
                d_str = f"{m.group(3)}.{MONTHS_MAP.get(m.group(2),'00')}.{m.group(1).zfill(2)}"
            if title and d_str:
                items.append({"d": d_str, "t": title, "url": link, "cats": cats})
    except Exception as e:
        print(f"  ⚠ RSS 解析失敗: {e}")
    return items

# ── HTML 新聞列表解析（WordPress 通用）──────────
def parse_wp_news_page(html: str) -> list:
    """從 WordPress 新聞列表頁提取 [{"d": "YYYY.MM.DD", "t": title, "url": url}]"""
    items = []
    # 標題選取：嘗試常見 WordPress 結構
    title_pattern = re.compile(
        r'<(?:h[123456]|div)[^>]*class="[^"]*(?:entry-title|post-title|title)[^"]*"[^>]*>'
        r'\s*(?:<a[^>]+href="([^"]+)"[^>]*>)?\s*([^<]{3,}?)\s*(?:</a>)?\s*</(?:h[123456]|div)>',
        re.I | re.S
    )
    date_pattern = re.compile(
        r'<(?:time|span|div)[^>]*(?:datetime="(\d{4}-\d{2}-\d{2})[^"]*"|class="[^"]*date[^"]*")[^>]*>'
        r'(?:[^<]*?(\d{4})[.\-/年](\d{1,2})[.\-/月](\d{1,2}))?',
        re.I | re.S
    )
    # 簡化策略：抓所有包含日期的行與鄰近標題
    # 策略1：找 <article> 或 <li class="post..."> 等容器
    containers = re.findall(
        r'<(?:article|li)[^>]*class="[^"]*(?:post|news|type-post)[^"]*"[^>]*>(.*?)</(?:article|li)>',
        html, re.S | re.I
    )
    for block in containers:
        # 取標題
        t_m = re.search(r'<(?:h[1-6]|div)[^>]*>[^<]*<a[^>]+href="([^"]+)"[^>]*>([^<]{3,})</a>', block, re.S)
        if not t_m:
            t_m = re.search(r'<a[^>]+href="([^"]+)"[^>]*>\s*<(?:h[1-6]|span)[^>]*>([^<]{3,})', block, re.S)
        # 取日期
        d_m = re.search(r'(?:datetime|content)="(\d{4}-\d{2}-\d{2})', block)
        if not d_m:
            d_m = re.search(r'(\d{4})[.\-年](\d{1,2})[.\-月](\d{1,2})', block)
        if t_m and d_m:
            title = re.sub(r'<[^>]+>', '', t_m.group(2)).strip()
            url   = t_m.group(1).strip()
            if d_m.lastindex == 1:
                d_str = d_m.group(1).replace('-', '.')
            else:
                d_str = f"{d_m.group(1)}.{d_m.group(2).zfill(2)}.{d_m.group(3).zfill(2)}"
            if title and d_str >= '2025.':
                items.append({"d": d_str, "t": title, "url": url})

    # 策略2（備援）：直接配對所有 <a>標題 + 日期
    if not items:
        pairs = re.findall(
            r'<a\s+href="(https?://[^"]+/\d{8,}/[^"]*)"[^>]*>\s*([^<]{5,}?)\s*</a>',
            html
        )
        date_re = re.compile(r'/(\d{4})(\d{2})(\d{2})\d*/')
        for url, title in pairs:
            dm = date_re.search(url)
            if dm:
                d_str = f"{dm.group(1)}.{dm.group(2)}.{dm.group(3)}"
                if d_str >= '2025.':
                    items.append({"d": d_str, "t": title.strip(), "url": url})

    # 去重（同標題只保留第一筆）
    seen = set()
    result = []
    for it in items:
        if it["t"] not in seen:
            seen.add(it["t"])
            result.append(it)
    return result

# ── 取得一個學系的全部新聞（CUT 後）──────────────
def fetch_dept_news(dept: dict, known_titles: set, force: bool) -> list:
    """
    增量模式：抓頁面直到遇到所有已知標題（或日期早於 CUT）
    全量模式：一直抓到 CUT 為止
    回傳僅【新的】文章 list

    2026-08-10 修正：RSS 分頁（/feed/?paged=N）與校網 update_school_news() 走
    同一支路，第 2 頁起也適用——先前只有第 1 頁試 RSS，第 2 頁起改抓
    /page/N/ 這個「瀏覽器版」列表頁做 HTML 解析，但實測多數系網（如 he）這個
    網址其實是完全不同的版型（school-relay 卡片，non-post class），
    parse_wp_news_page() 抓不到任何東西、靜默回傳空清單，導致分頁在第 1 頁
    後就停了——CUT 前尚未觸及就停，較舊但仍在區間內的文章永遠抓不到
    （水利系 2025-08-18～2025-09-26 四篇即因此漏掉，2026-08-10 使用者回報）。
    也不再以「本頁是否已知」作為翻頁與否的依據：只要日期還沒早於 CUT
    就繼續翻頁，已知標題只是跳過重複，不影響是否繼續探頁。
    """
    base_url = dept["url"]
    new_articles = []
    page = 1
    stop = False

    while not stop:
        rss_url = base_url.rstrip('/') + '/feed/' + (f'?paged={page}' if page > 1 else '')
        rss_text = fetch(rss_url)
        items = parse_rss(rss_text) if rss_text and '<rss' in rss_text else []

        if not items and page == 1:
            # 少數系網無 RSS：僅第 1 頁退而求其次嘗試 HTML 列表頁
            html = fetch(base_url)
            if html:
                items = parse_wp_news_page(html)

        if not items:
            break

        for it in items:
            if it["d"] < CUT:
                stop = True
                break
            if it["d"] > CUT_END:
                continue   # 114學年度尚未開始的未來文章（如下學期選課公告），不計入
            if it["t"] in known_titles:
                continue
            new_articles.append(it)

        if not stop:
            page += 1
            if page > 20:
                break

        time.sleep(0.8)  # 禮貌爬取

    return new_articles

# ── 快取管理 ──────────────────────────────────
def load_cache() -> dict:
    if CACHE_FILE.exists() and not FORCE:
        with open(CACHE_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {"lastUpdate": "", "school": [], "depts": {}}

def save_cache(cache: dict):
    cache["lastUpdate"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"✅ 快取已儲存：{CACHE_FILE}")

# ── 從 HTML 讀取現有資料作為初始快取 ────────────
def extract_cache_from_html() -> dict:
    """首次執行時從 HTML 提取已有資料，避免重複爬取"""
    cache = {"lastUpdate": "", "school": [], "depts": {}}
    if not HTML_FILE.exists():
        return cache

    html = HTML_FILE.read_text(encoding='utf-8')

    # 提取 SCHOOL_RAW（校網新聞）
    sr_m = re.search(r'const SCHOOL_RAW=\[(.*?)\];', html, re.S)
    if sr_m:
        for m in re.finditer(r"\{d:'([^']+)',t:'([^']+)',url:'([^']+)',cats:\[([^\]]*)\]\}", sr_m.group(1)):
            cats = re.findall(r"'([^']+)'", m.group(4))
            cache["school"].append({"d": m.group(1), "t": m.group(2), "url": m.group(3), "cats": cats})

    # 提取各學系新聞
    for m in re.finditer(r'\{id:\'([^\']+)\'.*?news:\[(.*?)\]\}', html, re.S):
        dept_id = m.group(1)
        news_raw = m.group(2)
        articles = []
        for nm in re.finditer(r'\{d:\'([^\']+)\',t:\'([^\']+)\'\}', news_raw):
            t = nm.group(2)
            d = nm.group(1)
            g, v, a = auto_score(t, d)
            articles.append({"d": d, "t": t, "g": g, "v": v, "a": a, "tot": g + v + a})
        cache["depts"][dept_id] = articles

    return cache

# ── 重新產生 HTML 中的校級新聞區塊 ───────────────
def build_school_js(cache: dict) -> str:
    """產生 JS 格式的校級新聞（SCHOOL_RAW）字串"""
    lines = ["const SCHOOL_RAW=["]
    seen_urls = set()
    for s in sorted(cache["school"], key=lambda x: x["d"], reverse=True):
        # 同一網址只輸出一次（最後一道防線，快取萬一又混進重複也不會顯示兩則）
        if s.get("url"):
            if s["url"] in seen_urls:
                continue
            seen_urls.add(s["url"])
        d = s["d"].replace('.', '-')
        t_escaped = s["t"].strip(" \t\r\n　 ").replace("'", "\\'")
        url_escaped = s["url"].replace("'", "\\'")
        cats = ",".join("'" + c.replace("'", "\\'") + "'" for c in s.get("cats", []))
        lines.append(f"  {{d:'{d}',t:'{t_escaped}',url:'{url_escaped}',cats:[{cats}]}},")
    lines.append("];")
    return "\n".join(lines)

# ── 重新產生 HTML 中的學系資料區塊 ───────────────
def build_dept_js(dept: dict, articles: list) -> str:
    """產生 JS 格式的學系資料字串。

    注意：**必須輸出 url 欄位**。update_html() 是把整個 const D=[...] 區塊覆蓋重寫，
    這裡漏掉 url 會把先前 fetch_article_urls.py 補進去的網址全部洗掉
    （2026-08-01 實際發生過：40 個系所的 url 全失，儀表板無法連到原文、
    評分管線也抓不到內文）。快取本來就存有 url，照寫即可。
    """
    lines = [f"  {{id:'{dept['id']}',col:'{dept['col']}',name:'{dept['name']}',url:'{dept['url']}',news:["]
    for a in sorted(articles, key=lambda x: x["d"], reverse=True):
        t_escaped = a["t"].replace("'", "\\'")
        u = (a.get("url") or "").strip()
        if u:
            u_escaped = u.replace("'", "\\'")
            lines.append(f"    {{d:'{a['d']}',t:'{t_escaped}',url:'{u_escaped}'}},")
        else:
            # 少數抓不到網址者維持 {d,t}，儀表板的 n.url 判斷才不會拿到空字串
            lines.append(f"    {{d:'{a['d']}',t:'{t_escaped}'}},")
    lines.append("  ]},")
    return "\n".join(lines)

def split_existing_depts(html: str):
    """把現有 const D=[...] 拆成 [(id, 區塊文字), …]，供保留非 DEPT_LIST 的系所之用。"""
    ds = html.find('const D=[')
    de = html.find('\n];', ds)
    if ds < 0 or de < 0:
        return []
    body = html[ds + len('const D=['):de]
    out = []
    for part in re.split(r'(?=\n  \{id:\')', body):
        m = re.search(r"\{id:'([^']+)'", part)
        if m:
            out.append((m.group(1), part))
    return out


def update_html(cache: dict):
    """將快取資料寫回 HTML 檔案，保留所有其他結構不變。

    **非 DEPT_LIST 的系所必須原樣保留**：本清單只涵蓋標準 WordPress 系網，
    像 iecs（Porto CMS）、pmpf／fphd（Wix）等是由各自的 inject_*.py 寫入的。
    早期版本直接依 DEPT_LIST 重建整個 D 陣列，導致每跑一次就把它們刪掉——
    2026-08-01 那次執行一口氣刪掉 15 個系所、97 篇文章，且毫無錯誤訊息。
    """
    html = HTML_FILE.read_text(encoding='utf-8')

    known = {d["id"]: d for d in DEPT_LIST}
    existing = split_existing_depts(html)
    existing_ids = [i for i, _ in existing]

    # 重建 const D=[...]：沿用現有順序，DEPT_LIST 內的重新產生，其餘原樣保留
    d_block_lines = ["const D=["]
    kept = []
    for did, block in existing:
        if did in known:
            d_block_lines.append(build_dept_js(known[did], cache["depts"].get(did, [])))
        else:
            d_block_lines.append(block.strip('\n'))
            kept.append(did)
    # DEPT_LIST 有、但 HTML 尚無的（新增系所）附加在最後
    for dept in DEPT_LIST:
        if dept["id"] not in existing_ids:
            d_block_lines.append(build_dept_js(dept, cache["depts"].get(dept["id"], [])))
            print(f"  ＋ 新增系所 {dept['id']}")
    d_block_lines.append("];")
    new_d_block = "\n".join(d_block_lines)
    if kept:
        print(f"  ↻ 保留非 DEPT_LIST 系所 {len(kept)} 個：{'、'.join(kept)}")

    # 替換 HTML 中的 const D=[...]; 區塊
    html_new = re.sub(
        r'const D=\[.*?\];',
        new_d_block,
        html,
        count=1,
        flags=re.S
    )

    # 替換 HTML 中的 const SCHOOL_RAW=[...]; 區塊
    new_school_block = build_school_js(cache)
    html_new = re.sub(
        r'const SCHOOL_RAW=\[.*?\];',
        new_school_block,
        html_new,
        count=1,
        flags=re.S
    )

    # 更新頁首的更新日期
    today = datetime.now().strftime("%Y-%m-%d")
    html_new = re.sub(
        r'(\d{4}-\d{2}-\d{2})(.*?更新)',
        f"{today}\\2",
        html_new,
        count=2
    )

    HTML_FILE.write_text(html_new, encoding='utf-8')
    print(f"✅ HTML 已更新：{HTML_FILE}")

    verify_html(before_depts=len(existing_ids))


# ── 寫回後自我檢查 ────────────────────────────────
def verify_html(before_depts: int = None):
    """寫回後驗證 D 陣列，攔截已知會靜默出錯的問題。

    ① **系所數減少**：最嚴重且最容易被忽略。update_html() 早期依 DEPT_LIST
       重建整個 D 陣列，把 inject_*.py 另外加入的系所全部刪光——2026-08-01
       一次刪掉 15 個系所、97 篇文章，exit code 仍是 0、摘要仍顯示成功。
       現已改為保留非 DEPT_LIST 的系所，這裡再做一次數量把關。
    ② url 遺失：build_dept_js() 若沒輸出 url 欄位，會把先前補齊的網址洗掉，
       儀表板連結會退回系所列表頁，評分管線也抓不到內文。（2026-08-01 發生過）
    """
    html = HTML_FILE.read_text(encoding='utf-8')
    m = re.search(r'const D=\[.*?\n\];', html, re.S)
    if not m:
        print("⚠️  驗證失敗：找不到 const D=[...] 區塊")
        return
    block = m.group(0)

    entries = re.findall(r"\{d:'[^']+',t:'(?:[^'\\]|\\.)*'(?:,url:'([^']*)')?\}", block)
    total = len(entries)
    with_url = sum(1 for u in entries if u)

    dept_count = len(re.findall(r"\{id:'", block))
    print("\n── 寫回後自我檢查 ──")
    print(f"   系所 {dept_count} 個｜文章 {total} 篇｜有網址 {with_url} 篇")

    ok = True
    if before_depts is not None and dept_count < before_depts:
        ok = False
        print(f"   ⚠️  系所數由 {before_depts} 減為 {dept_count}，有 {before_depts - dept_count} 個被刪除！")
        print("       非 DEPT_LIST 的系所（iecs／pmpf／fphd 等）本應原樣保留，請勿忽略此警告。")
        print("       還原：python \"tools\\news-pipeline\\restore_lost_depts.py\"")
    if "id:'iecs'" not in block:
        ok = False
        print("   ⚠️  D 陣列缺少 iecs（資訊工程學系，由 inject_iecs.py 管理）。")
        print("       執行：python \"tools\\news-pipeline\\inject_iecs.py\"")
    if total and with_url / total < 0.8:
        ok = False
        print(f"   ⚠️  僅 {with_url}/{total} 篇有 url，比例偏低——網址可能又被洗掉。")
        print("       修復（不需連網，直接從快取補回）：")
        print("       python \"tools\\news-pipeline\\repair_dept_urls.py\"")
    if ok:
        print("   ✅ 系所數未減少、iecs 存在、網址完整")

# ── 更新校網新聞（RSS 分頁）────────────────────
def update_school_news(cache: dict):
    """以 **url** 判斷是否抓過，不能用標題。

    2026-08-07：原本用 `{s["t"] for s in cache["school"]}` 以標題去重，校網編輯
    事後在標題尾端多打一個全形空白 U+3000，同一個網址就被當成新文章再存一筆
    （'…榮獲英國FADA冬季賽雙白金' 與 '…榮獲英國FADA冬季賽雙白金　'）。
    儀表板的 schOnly 分支不會拿 SCHOOL_RAW 自己去重，於是工工系那則顯示兩次、
    系所與校級則數各多算一。既有重複已由 dedupe_school_raw.py 清掉。
    """
    known = {s["url"] for s in cache["school"] if s.get("url")}
    new_items = []
    print("📡 抓取校網新聞（RSS 分頁）...")
    for page in range(1, 21):
        url = f"https://www.fcu.edu.tw/news/feed/?paged={page}"
        text = fetch(url)
        if not text:
            break
        items = parse_rss(text)
        if not items:
            break
        stopped = False
        for it in items:
            if it["d"] < CUT.replace('.', '-')[:10]:
                stopped = True
                break
            it["t"] = it["t"].strip(" \t\r\n　 ")   # 去掉尾端全形空白
            it["d_fmt"] = it["d"].replace('-', '.')
            if it["d_fmt"] > CUT_END:
                continue   # 114學年度尚未開始的未來文章，不計入
            if it["url"] not in known and not FORCE:
                if it.get("d_fmt", "") < CUT:
                    stopped = True
                    break
            if it["url"] not in known:
                new_items.append(it)
                known.add(it["url"])
        if stopped and not FORCE:
            break
        time.sleep(0.5)

    added = 0
    for it in new_items:
        d_dot = it.get("d", "")
        if len(d_dot) == 10 and d_dot >= CUT:
            d = d_dot.replace('.', '-')
            cache["school"].append({"d": d, "t": it["t"], "url": it["url"], "cats": it.get("cats", [])})
            added += 1
    if added:
        print(f"  ＋新增 {added} 筆校網新聞")
    else:
        print("  — 無新增")

# ── 主程式 ────────────────────────────────────
def main():
    print("=" * 55)
    print(f"FCU 新聞增量更新  {'【強制全量模式】' if FORCE else '【增量模式】'}")
    print(f"執行時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 55)

    # 載入或從 HTML 初始化快取
    if CACHE_FILE.exists() and not FORCE:
        cache = load_cache()
        print(f"📂 讀取快取（上次更新：{cache.get('lastUpdate','—')}）")
    else:
        print("📂 從現有 HTML 初始化快取...")
        cache = extract_cache_from_html()
        if not cache["depts"]:
            cache = {"lastUpdate": "", "school": [], "depts": {}}

    # 更新校網新聞
    update_school_news(cache)

    # 逐系更新
    targets = [d for d in DEPT_LIST if ONLY_DEPT is None or d["id"] == ONLY_DEPT]
    total_added = 0

    for dept in targets:
        did = dept["id"]
        existing = cache["depts"].get(did, [])
        known_titles = {a["t"] for a in existing}
        print(f"\n🔍 [{did}] {dept['name']}（已知 {len(existing)} 筆）")

        new_arts = fetch_dept_news(dept, known_titles, FORCE)

        if not new_arts:
            print("  — 無新增")
            if did not in cache["depts"]:
                cache["depts"][did] = []
            continue

        # 對新文章評分
        for a in new_arts:
            g, v, ax = auto_score(a["t"], a["d"])
            a["g"] = g; a["v"] = v; a["a"] = ax; a["tot"] = g + v + ax

        # 合併（新 + 舊），去重
        merged_map = {a["t"]: a for a in existing}
        for a in new_arts:
            if a["t"] not in merged_map:
                merged_map[a["t"]] = a
                total_added += 1
                print(f"  ＋ {a['d']} {a['t'][:45]}")

        cache["depts"][did] = list(merged_map.values())

    print(f"\n{'=' * 55}")
    print(f"✅ 本次共新增 {total_added} 筆新聞")

    # 儲存快取 & 更新 HTML
    save_cache(cache)
    update_html(cache)
    print("🎉 完成！")

if __name__ == "__main__":
    main()

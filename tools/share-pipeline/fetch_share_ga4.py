# -*- coding: utf-8 -*-
import os
from pathlib import Path
HERE = Path(__file__).resolve().parent
PROJ = HERE.parent.parent          # fcu-news-dashboard/
import json
from datetime import datetime, timedelta
from urllib.parse import urlparse
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest, DateRange, Metric, Dimension,
    FilterExpression, FilterExpressionList, Filter, OrderBy
)

PROPERTY_ID = "258034980"
# GA4 服務帳戶金鑰：不放進本專案（公開 repo）。預設沿用原位置，可用環境變數 FCU_GA4_KEY 覆蓋。
KEY_FILE        = os.environ.get("FCU_GA4_KEY", r"Z:\12.Claude專屬資料夾\工具程式\claude code\grand-quarter-500104-t6-e6073fb673e7.json")
SHARE_FULL_FILE = HERE / "share_full.json"
OUT_FILE        = HERE / "share_ga4.json"
# 2026-08-12 使用者明確指定：GA4數據只抓114學年度起(CUT)~昨天這個固定區間，取代先前的
# 全站歷史累計(GA4_FLOOR起)設計；起迄日期需完整標註在儀表板上。
CUT = "2025-08-01"
END_DATE = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")  # 抓到「昨天」，避免當天資料尚未跑完而低估

SHARE_FILTER = FilterExpression(
    filter=Filter(
        field_name="pagePath",
        string_filter=Filter.StringFilter(value="/share", match_type=Filter.StringFilter.MatchType.BEGINS_WITH)
    )
)

def load_known_paths():
    # /share/ 是長期可瀏覽的學生分享故事（非時效性新聞），舊文章近期仍可能持續有人瀏覽，
    # 故熱門/冷門排行採全站153篇已知網址，而非僅CUT後發布者。
    items = json.load(open(SHARE_FULL_FILE, encoding="utf-8"))
    path_title = {urlparse(it["link"]).path: it["title"] for it in items}
    path_date  = {urlparse(it["link"]).path: it["post_date"][:10] for it in items}
    return path_title, path_date

def exact_path_filter(paths):
    return FilterExpression(
        or_group=FilterExpressionList(expressions=[
            FilterExpression(filter=Filter(
                field_name="pagePath",
                string_filter=Filter.StringFilter(value=p, match_type=Filter.StringFilter.MatchType.EXACT)
            )) for p in paths
        ])
    )

def fetch_summary(client, start_date, end_date, with_detail=False):
    # screenPageViews/activeUsers 與 averageSessionDuration 分屬不同 scope（event vs session）。
    # 實測發現：把 averageSessionDuration 跟它們放在同一個 request 裡，會讓 GA4 Data API
    # 連帶把 pagePath 篩選器跑壞，screenPageViews 暴增近2倍（已用對照測試驗證），
    # 所以這兩種 metric 必須拆成兩個獨立 request 分開查詢。
    req = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        metrics=[Metric(name="screenPageViews"), Metric(name="activeUsers")],
        dimension_filter=SHARE_FILTER,
    )
    r = client.run_report(req)
    if not r.rows:
        out = {"pv": 0, "users": 0}
    else:
        row = r.rows[0]
        out = {"pv": int(row.metric_values[0].value), "users": int(row.metric_values[1].value)}

    if with_detail:
        dur_req = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            metrics=[Metric(name="averageSessionDuration")],
            dimension_filter=SHARE_FILTER,
        )
        dr = client.run_report(dur_req)
        out["avgDur"] = round(float(dr.rows[0].metric_values[0].value)) if dr.rows else 0
    return out

def fetch_top_channel(client, start_date, end_date):
    req = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name="sessionSourceMedium")],
        metrics=[Metric(name="sessions")],
        dimension_filter=SHARE_FILTER,
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
        limit=1,
    )
    r = client.run_report(req)
    if r.rows:
        return r.rows[0].dimension_values[0].value, int(r.rows[0].metric_values[0].value)
    return "—", 0

# 少數文章在API清單裡的網址，跟GA4實際記到的網址不一樣（站方換過slug、或舊版多字母縮寫網址
# 沒設redirect），導致同一篇文章的瀏覽量被GA4拆成兩個互不相干的pagePath各自累計。
# 每一筆都用「抓即時頁面標題比對」核實過是同一篇文章才收錄，沒驗證過的（例如頁面已404、
# 無法確認內容的）寧可漏算也不亂猜合併。
ALIAS_PATHS = {
    "/share/mcae002/": "/share/mcae01/",  # 站方將 mcae002 改名為 mcae01（2026-07 前後），舊 URL 仍有少量殘留流量
    "/share/一路摸索，慢慢找到自己的方向｜逢甲資訊系-楊孟/": "/share/iecs013/",
    "/share/專業、挑戰與成長：我的大學與碩士探索之路/": "/share/mse003/",
}

def fetch_page_views(client, start_date, end_date, known_paths, limit=300):
    # 同一網址有沒有結尾斜線，WordPress不一定會自動轉址，GA4會把兩者當成不同的pagePath，
    # 所以查詢時兩種形式都要找，再合併回標準（有斜線）網址底下。
    no_slash_map = {p.rstrip("/"): p for p in known_paths}
    query_paths = set(known_paths) | set(no_slash_map.keys()) | set(ALIAS_PATHS.keys())

    req = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name="pagePath")],
        metrics=[Metric(name="screenPageViews")],
        dimension_filter=exact_path_filter(list(query_paths)),
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"), desc=True)],
        limit=limit,
    )
    r = client.run_report(req)

    known_set = set(known_paths)
    result = {}
    for row in r.rows:
        p = row.dimension_values[0].value
        pv = int(row.metric_values[0].value)
        canon = p if p in known_set else ALIAS_PATHS.get(p) or no_slash_map.get(p)
        if canon is None:
            continue
        result[canon] = result.get(canon, 0) + pv
    return result

def main():
    client = BetaAnalyticsDataClient.from_service_account_file(KEY_FILE)

    # 固定區間統計：CUT(114學年度起)~END_DATE(昨天)，含完整明細。全部指標（總覽、熱門/冷門排行
    # 用的逐頁瀏覽數）都只查這個區間，不再抓GA4全站歷史累計。
    summary = fetch_summary(client, CUT, END_DATE, with_detail=True)
    channel, channel_sessions = fetch_top_channel(client, CUT, END_DATE)

    path_title, path_date = load_known_paths()
    page_views = fetch_page_views(client, CUT, END_DATE, list(path_title.keys()))

    result = {
        "since": CUT,
        "until": END_DATE,
        "fetchedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "pv": summary["pv"],
        "users": summary["users"],
        "avgDur": summary["avgDur"],
        "topChannel": channel,
        "topChannelSessions": channel_sessions,
        "pageViews": page_views,
    }

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"=== /share/ GA4 統計（{CUT} ~ {END_DATE}）===")
    print(f"瀏覽次數 {result['pv']:,}｜不重複使用者 {result['users']:,}｜平均停留 {result['avgDur']}秒")
    print(f"最大流量來源：{channel}（{channel_sessions:,} 工作階段）")
    print(f"有瀏覽紀錄的頁面：{len(page_views)} / {len(path_title)} 篇")
    print("已儲存", OUT_FILE)

if __name__ == "__main__":
    main()

# 新聞抓取流程（已搬入本專案）

2026-10-01 從 `Z:\12.Claude專屬資料夾\工具程式\` 搬進來，所有路徑都已改成相對本專案，
不再依賴那個資料夾。原檔保留在原處未動，但**以後請用這裡的版本**。

每支腳本開頭都有這段：

```python
PROJ = Path(__file__).resolve().parents[2]   # fcu-news-dashboard/
HERE = Path(__file__).resolve().parent       # tools/news-pipeline/
DASHBOARD = PROJ / 'index.html'              # 新聞監測儀表板
```

## 例行更新（最常用）

```bash
python tools/news-pipeline/update_fcu_news.py    # 1. 增量抓各系 RSS，更新 index.html
node tools/extract-news.js                       # 2. 重算統計 → tools/news.json
python tools/sync-news-to-healthcheck.py         # 3. 同步進 health-check.html 的新聞成效分頁
```

主更新器的其他用法：

```bash
python tools/news-pipeline/update_fcu_news.py --force       # 強制全量重爬
python tools/news-pipeline/update_fcu_news.py --dept mse    # 只更新單一學系
```

原排程為每月 1 日 09:00。

## 校級新聞與學系歸屬（需要時才跑）

```bash
python tools/news-pipeline/fetch_all_school_news.py   # 校網 JSON API → school_news_full.json
python tools/news-pipeline/fetch_all_hashtags.py      # 逐篇抓文章頁 #hashtag → school_raw_full.json
python tools/news-pipeline/inject_url_cats.py         # url_cats.json → index.html 的 URL_CATS
```

## 非新聞審核 v4.0（需要時才跑）

```bash
python tools/news-pipeline/review_news_v4.py <article_list.json>   # → article_review_v4.json
python tools/news-pipeline/inject_news_review.py                   # → index.html 的 NEWS_REVIEW
```

## 修補用（出狀況時）

| 腳本 | 時機 |
| --- | --- |
| `restore_lost_depts.py` | 系所數變少（inject_* 另外加入的系所被覆蓋） |
| `inject_iecs.py` | D 陣列缺少 iecs（資訊工程學系，Porto CMS，由此腳本管理） |
| `repair_dept_urls.py` | 文章網址被洗掉（從快取補回，不需連網） |
| `dedupe_school_raw.py` | 校級新聞重複，導致系所與校級則數各多算一 |
| `fetch_article_urls.py` | 補抓文章網址 |

備份一律寫到 `tools/news-pipeline/backup/`。

## 資料檔

| 檔案 | 大小 | 內容 |
| --- | --- | --- |
| `fcu_news_cache.json` | 208 KB | 各系文章快取（增量更新的基礎） |
| `school_news_full.json` | 385 KB | 校網 JSON API 原始抓取結果 |
| `school_raw_full.json` | 94 KB | 校級新聞＋hashtag（→ SCHOOL_RAW） |
| `url_cats.json` | 25 KB | 每篇校網文章的學系標籤（→ URL_CATS） |
| `article_review_v4.json` | 273 KB | v4.0 審核結果（→ NEWS_REVIEW） |
| `article_content_cache.json` | 1.6 MB | 內文／圖片快取（規則調整時免重抓） |

## 已驗證

搬入後做過唯讀煙霧測試，主更新器能正確讀到本專案的 `index.html`：

```
系所 71 個｜文章 309 篇｜有網址 306 篇
✅ 系所數未減少、iecs 存在、網址完整
```

11 支腳本語法檢查全部通過。**尚未實際執行過更新**（會連外抓資料並改寫 index.html）。

抓取方法的原理說明見 [../新聞數量更新流程.md](../新聞數量更新流程.md)。

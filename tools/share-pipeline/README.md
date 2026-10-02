# 學生愛分享資料管線

`student-share.html`（學生愛分享儀表板）的產生腳本與快取，2026-10-02 從
`Z:\12.Claude專屬資料夾\工具程式\claude code\` 搬進本專案，路徑已全部改成相對本專案。

完整說明見 [../學生愛分享更新流程.md](../學生愛分享更新流程.md)。

| 檔案 | 用途 |
| --- | --- |
| `fetch_share_stats.py` | 抓校網 `/wp-json/api/share` → `share_full.json`／`share_since_cut.json` |
| `fetch_share_ga4.py` | 抓 GA4（property 258034980，`/share` 區段）→ `share_ga4.json` |
| `map_share_depts.py` | 標題簡稱 → 正式系所全名（對照 `學院系列表.xlsx`）→ `share_dept_map.json` |
| `build_share_dashboard.py` | 三份資料合併，**整個覆蓋**產生 `../../student-share.html` |
| `學院系列表.xlsx` | 系所全名清單（`map_share_depts.py` 的對照基準） |

## GA4 金鑰

服務帳戶金鑰**不放進本專案**（公開 repo）。`fetch_share_ga4.py` 預設沿用原位置：

```
Z:\12.Claude專屬資料夾\工具程式\claude code\grand-quarter-500104-t6-e6073fb673e7.json
```

要換位置時設環境變數 `FCU_GA4_KEY`。

## 注意

- `build_share_dashboard.py` 會覆蓋 `student-share.html`，版面要改請改該檔裡的 `TEMPLATE`。
- 新文章若出現沒收錄的系所簡稱，會落到「未對應系所」而不是亂猜；
  跑完 `map_share_depts.py` 要看它印出的 unmatched 清單，回頭補 `ALIAS`。

# 改善建議回饋追蹤表 — 產生方式

`improvement-tracker.html`（各系填寫改善狀況的回饋表）是**自動產生**的，
資料來源是 `health-check.html` 裡的 `DEPTS` 陣列，請勿直接手改產出檔。

## 重新產生（健檢資料更新後執行）

```bash
node tools/extract-depts.js   # 從 health-check.html 抽出資料 → tools/depts.json
node tools/build-tracker.js   # 套用模板 → improvement-tracker.html（舊檔自動備份為 .bak）
```

| 檔案 | 用途 |
| --- | --- |
| `tools/extract-depts.js` | 解析 `health-check.html`，抽出各系的 `priority_issues`／`pain_points`／`quick_fixes` |
| `tools/depts.json` | 中繼資料（可直接檢視，勿手改） |
| `tools/improvement-tracker.template.html` | 回饋表版型與程式碼，**要改介面請改這裡** |
| `tools/build-tracker.js` | 把資料注入模板，產生單一檔 `improvement-tracker.html` |

## 設計重點

- **單一 HTML 檔**：資料內嵌，可直接 email 給各系同仁，或放 GitHub Pages。
- **填寫內容存在使用者本機瀏覽器**（localStorage，key = `fcu-healthcheck-feedback-v1`），
  沒有後端伺服器；同仁填完須按「匯出本系回覆」把 CSV／JSON 回傳。
- **事項鍵值**用建議文字的雜湊（`系id|pr或fx|hash`），健檢文字若修改，該項回覆會對不上而略過，
  匯入時會顯示略過數量。
- 公共事務組彙整：用「匯入／彙整回覆檔」一次選取多個系回傳的 JSON，再「匯出全部回覆（CSV）」。

---

# 招生連結查核分頁（health-check.html 內）

各系頁面的「🔗 招生連結查核」分頁，資料來自 `admission-link-check.html`（全校報告）。

```bash
python tools/extract-admission.py   # 解析全校報告 → tools/admission.json（70 站）
```

抽出後的資料是**內嵌**在 `health-check.html` 的 `ADM` 常數裡（`==ADMISSION_JS_START==` 區塊）。
全校報告若重新產出，請重跑上面的腳本，再把 `tools/admission.json` 的內容更新到該常數。
兩邊以**系所網址**對應（去掉協定與結尾斜線後比對），目前 70 站全數對應成功。

開放範圍同樣用一行開關控制：

```javascript
const ADM_DEPTS = ['inde'];   // 全面開放 → const ADM_DEPTS = 'all';
```

分頁順序由面板 id 決定（`switchTab('tpadm')`），兩個分頁各自可單獨開關，不會錯位。

---

# 新聞成效分頁（health-check.html 內）

**新聞數量一律以 `index.html`（新聞監測儀表板）為唯一來源，不要另行統計或手動填入。**

```bash
node tools/extract-news.js   # 重算各系新聞統計 → tools/news.json（71 站）
```

抽取器重現 `index.html` 內 `D.forEach` 的前置計算：校網介接判定（`URL_CATS` ／ `SCHOOL_RAW`）、
非新聞扣除（`NEWS_REVIEW` 的 `nn`）、月分布、達標基準（114 學年度 20 則）。
已用全 71 站 × 9 項數值的雜湊值比對過，與線上儀表板完全一致。

資料內嵌在 `health-check.html` 的 `NW` 常數（`==NEWS_JS_START==` 區塊）。
`index.html` 更新後重跑抽取器，再把 `tools/news.json` 的 `depts` 內容更新到該常數。

對應方式以**網址主機名**比對，id 兩邊不完全一致：

| 學系 | 健檢 id | 新聞 id |
| --- | --- | --- |
| 行銷學系 | `marketing` | `mkt` |
| 智慧城市碩士學位學程 | `msc` | `imsc` |

新聞端另有健檢未收錄的「創新智慧製造與管理產業碩士專班」（`iem`），不影響對應。

```javascript
const NW_DEPTS = ['inde'];   // 全面開放 → const NW_DEPTS = 'all';
```

---

# 115 學年度招生系所一覽表 — 招生管道別

一覽表（健檢儀表板左側「115學年度招生系所一覽表」）的各學士班單位名稱下方，
列出該系的招生管道與名額。資料來源為教育部【表7-2】日間學制學士班新生招生名額分配表。

```bash
python tools/extract-admit-channels.py "C:\...\【表7-2】...xlsx"   # xlsx → tools/admit-channels.json
python tools/inject-admit-channels.py                               # → health-check.html 的 ADMIT_115
```

兩支都可重複執行（資料常數整段取代、版面程式碼有 marker 保護），注入時自動備份。

## 資料解讀重點

- **僅涵蓋日間學制學士班**；碩博士班與進修學制的管道別不在此表範圍。
- 欄位對應以合併儲存格確認：欄 5–16 為內含名額、欄 17 為各領域擴充名額、
  欄 18–26 為外加名額（原住民 4 欄、資安學研 2 欄、青年儲蓄 2 欄、四技二專技優 1 欄）。
- ⚠️ **欄 18 的來源資料有誤**：該欄標題是「原住民考生／分發入學」，但實際填的是擴充比例字串
  `5%`（24 列）或空白（25 列），沒有任何數字，抽取時已排除。
- 核對結果：各單位內含名額逐一等於小計，全校合計 **3,975 名**，與 Excel 總計列一致；
  外加名額另計 139 名。

## 名稱對應

以去除括號、「大學」、「學位學程→學程」正規化後比對，50 個學士班單位中 48 個對應成功：

| 情形 | 單位 |
| --- | --- |
| 一覽表有、名額表無 | 國際雙學士學位學程（對內招生）、資訊工程學系學士後專班 |
| 名額表有、一覽表無 | 全校國際生大一不分系學士班（只收境外生） |

表格中灰底為內含名額、黃底為外加名額、紫底為該系學士班總名額。

---

# 學生愛分享分頁（health-check.html 內）

**學生愛分享的篇數與瀏覽數一律以 `student-share.html`（學生愛分享儀表板）為唯一來源，
不要另行統計或手動填入。**

```bash
node tools/extract-share.js                 # 重算各系篇數與流量 → tools/share.json
python tools/sync-share-to-healthcheck.py   # 注入 health-check.html 的 SH／SH_META
```

資料內嵌在 `health-check.html` 的 `SH` 常數（`==SHARE_JS_START==` 區塊），
版面 CSS 在 `==SHARE_CSS_START==` 區塊。兩支都可重複執行，注入時自動備份。

對應方式以**學系全名**比對 `tools/depts.json`：全站 165 篇中 162 篇對應到 37 個學系，
其餘 3 篇在來源端就標為「未對應系所」（逢甲創設系、RMIT-FCU／SJSU-FCU 雙聯學位）。

```javascript
const SH_DEPTS = 'all';   // 僅開放部分學系 → const SH_DEPTS = ['inde'];
```

來源端（`student-share.html` 本身）怎麼重新產生，以及 GA4 金鑰、標題簡稱對照表的維護，
見 [學生愛分享更新流程.md](學生愛分享更新流程.md)。

---

# 改善回饋填寫分頁的登入門檻（health-check.html 內）

各系「✍️ 改善回饋填寫」分頁要先登入才能填寫。
**帳號＝學系網址代號**（如工工系 `inde`）、**密碼＝該單位總機分機**。
另有管理者帳號 `fcupubulic`（密碼＝公共事務組分機），可編輯任何一系。

```bash
python tools/extract-ext.py     # 總機分機表 xlsx → tools/auth-map.json
python tools/sync-auth.py       # 算雜湊並注入 health-check.html
```

分機表換版（如 115-2）時重跑這兩支即可：

```bash
python tools/extract-ext.py "Z:\工讀生\總機分機表_115-2.xlsx" && python tools/sync-auth.py
```

## 變更密碼

密碼由公共事務組統一管理，**變更一律走「申請 → 套用 → 重新發布」**，改完全校一起生效。

登入後分頁上方有「變更密碼」：

1. **各系**：輸入目前密碼 → 新密碼（至少 4 字元）兩次 → 「加入變更清單」
   **管理者**：可重設目前所看那一系（免輸入該系舊密碼），或改自己的（需舊密碼），可一次累積多筆
2. 按「**下載密碼變更檔**」，把 JSON 回傳公共事務組
   （檔案裡只有 SHA-256 雜湊、沒有密碼原文，所以**要另外告知新密碼是什麼**）
3. 公共事務組套用後重新發布：

```bash
python tools/apply-pwd-changes.py 密碼變更_inde_2026-10-02.json   # 可一次給多個檔案
python tools/extract-ext.py && python tools/sync-auth.py          # 重新產製
```

**申請到發布之間，原密碼仍然有效**；發布後才換成新密碼。

要還原成預設的分機密碼，按「申請還原為預設密碼」產生變更檔走同一條流程即可
（也可以直接把該單位在 `auth-overrides.json` 裡的 `hash` 刪掉再重跑後兩支）。

## ⚠️ 這是防呆門檻，不是資安機制

- `health-check.html` 是**純前端單一檔案、沒有後端**，所有檢查都在瀏覽器裡跑。
  檔案內只存 `SHA-256` 雜湊（看原始碼看不到分機），但分機只有 4 碼，
  懂技術的人在瀏覽器主控台暴力試出來只要幾秒；分機本來也公開在各系聯絡頁。
- 它擋的是「**別系同仁點進來誤改**」，不是惡意者。
- 回饋內容存在填表人自己電腦的 `localStorage`（key `fcu-healthcheck-feedback-v1`），
  登入與否都不影響那份資料，登入只是擋住填寫介面。
- 登入狀態存 `sessionStorage`，**關掉瀏覽器就要重新登入**；分頁上有「登出」鈕。
- `improvement-tracker.html`（寄給各系的回饋表）**沒有**這道門檻，要的話得另外加。

## 檔案

| 檔案 | 說明 |
| --- | --- |
| `tools/extract-ext.py` | 讀總機分機表，對應學系全名 → `tools/auth-map.json` |
| `tools/auth-overrides.json` | 分機表查不到／名稱對不起來的單位在這裡指定（**可手改**） |
| `tools/auth-map.json` | 中繼資料，**含明碼分機，已列入 .gitignore，勿推上公開 repo** |
| `tools/auth-list.csv` | 給公共事務組發信通知用的帳密對照表，**同樣不要外流** |
| `tools/sync-auth.py` | 算雜湊、注入 `health-check.html`（`==AUTH_JS_START==` 區塊） |
| `tools/apply-pwd-changes.py` | 把各系回傳的密碼變更檔寫進 `auth-overrides.json`，讓新密碼全校生效 |

## 分機表查不到的單位

分機表上查不到或填「-」的單位，分機記在 `tools/auth-overrides.json`。
下列 5 筆已於 2026-10-02 經公共事務組確認：

| 學系 | 分機 | 說明 |
| --- | --- | --- |
| 商學學士學位學程 `bce` | 4061 | |
| 全球行銷碩士班 `globalmarketing` | 4381 | |
| 資訊工程學系學士後專班 `pbiecs` | 3865 | |
| 資通安全碩士學位學程 `ics` | 3991 | |
| 人工智慧科技與管理碩士學位學程 `aitm` | 2991 | |

日後若有新單位在分機表查不到，`extract-ext.py` 會列出來，補進 `auth-overrides.json` 再重跑即可。

---

# 已自健檢移除的學系

| 學系 | 移除日期 | 原因 |
| --- | --- | --- |
| 學士後工程與科學學院淨零智慧永續學士班 `nze` | 2026-10-02 | 已停招、網站停用，不再列入健檢與優化 |

移除方式：刪掉 `health-check.html` 的 `DEPTS` 項目，以及 `NW`／`SH`／`ADM`／`AUTH`
與 `ADMIT_115.unlisted` 裡的同名鍵值，再重跑 `extract-depts.js`、`build-tracker.js`、
`extract-share.js`＋`sync-share-to-healthcheck.py`、`extract-ext.py`＋`sync-auth.py`。
其他學系查核紀錄裡若提到該系（例如經濟系招生頁誤連 nze 的缺失）屬於該系的問題，要保留。

---

# 師資查核分頁（health-check.html 內）

各系頁面的「📷 師資查核」分頁（排在招生連結查核之後），查核兩件事：

1. **師資照片**：缺漏／明顯模糊或失焦／頭部太貼近上緣／被裁切
2. **師資個人頁**：「More」點進去的個人頁是否至少具備**專長**與**學歷**
3. **師資類別 vs 選單結構**：該系有哪些師資類別（職稱），導覽選單的「師資」底下就該有
   對應的二階連結（例：有一位特約講座，選單就要有「特約講座」）。兩個方向都看：
   **選單缺**（有這類師資、選單沒連結）與**選單多**（有連結、但沒有這類師資，點進去是空的）
4. **排序**：師資名單與選單二階是否都依師資職稱排序原則排列

## 師資職稱排序原則

公共事務組提供，共 25 級，寫在 `check-faculty.py` 的 `TITLE_ORDER`：

何宜武先生學術講座 → 高人言先生學術講座 → 春雨講座 → 生日講座 → 榮譽特聘講座 → 特聘講座 →
講座教授 → 特約講座 → 榮譽特聘教授 → 特聘教授 → 專任教授 → 客座教授 → 特約客座教授 →
榮譽教授 → 專任副教授 → 特約客座副教授 → 專任助理教授 → 專任講師 → 研究教授 → 研究副教授 →
研究助理教授 → 兼任教授 → 兼任副教授 → 兼任助理教授 → 兼任講師

用途：①儀表板上的師資類別依此排列　②檢查師資名單的職稱先後是否符合　③檢查選單二階的先後是否符合。
職稱不在這 25 級內的（各系可能有「專案教授」「專業技術人員」等），會另外列出請人工確認擺放位置，
不當成排序錯誤。日後若排序原則有異動，改 `TITLE_ORDER` 一處即可。

```bash
python tools/check-faculty.py inde            # 查核單一系所（可一次給多個 id，或 --all）
python tools/sync-faculty.py                  # 注入 health-check.html
```

逐系進行：`faculty.json` 會累積，沒查過的系所在分頁上顯示「尚未進行師資查核」。

## 資料怎麼來的

- 師資清單：各系 `/teachers/`，第二頁以後用 `?post_page=N`
- **照片不在 HTML 裡**，是 `teachers.js` 向校網 API 取回 base64：
  `https://www.fcu.edu.tw/wp-json/api/v1/get_teacher_thumb/?id=<工號>&unit_id=<單位代碼>`
  （工號與單位代碼在卡片的 `data-thumb-id` / `data-unit-id`）
- **選單**是伺服器端輸出的，直接抓首頁 HTML 就有：`師資` 底下帶 `job_title` 參數的連結
  （桌機版與手機版各一份，以 `job_title` 去重）
- **個人頁的內容也不在 HTML 裡**：專長、學歷、校內經歷、期刊／會議論文、專利等，
  都是 `teacher.js` 向校網 API 取回後才填進畫面：
  `https://www.fcu.edu.tw/wp-json/api/v1/teacher/info?id=<工號>`
  直接抓個人頁原始碼只會看到伺服器端輸出的「基本資訊」空殼（信箱、分機）

## 判讀門檻（2026-10-02 以工工系 21 張照片目視校準）

| 項目 | 方法 | 門檻 |
| --- | --- | --- |
**只標示兩種照片問題**（2026-10-02 使用者定調：不夠銳利但看得清楚的不算問題）：

| 列為問題 | 方法 | 門檻 |
| --- | --- | --- |
| 缺照片 | 校網師資照片 API 沒有回傳影像 | — |
| 明顯模糊／失焦 | **只量臉部區域**的 Laplacian 變異數（縮到 180px 後計算） | <10 |
| 頭太貼近上緣 | Haar 人臉偵測，臉框上緣距照片頂端的比例 | =0%（臉已貼到頂端） |
| 臉部被裁切 | 臉框是否貼到圖片邊界 | 貼到即判定 |
| 空白／佔位圖 | 整張灰階標準差 | <12 |

下列只列在表格的灰字備註，**不計入「照片有疑慮」**：臉部在原圖 <90px 寬、原圖短邊 <200px、
偵測不到正面人臉（側臉／團體照需人工確認）。

⚠️ **清晰度一定要只量臉部**。早期版本量整張圖，全身照的大片純色背景會把變異數拉到很低，
把構圖正常的全身照全部誤判成模糊（工工系 21 張有 5 張被誤判）。

⚠️ **師資照片與個人頁內容都要走 API，不能抓 HTML**。2026-10-02 建置時連續踩兩次：
先是照片抓不到（誤判成全系缺照片 21 人），改用 `get_teacher_thumb` 後才正常；
接著個人頁只抓到空殼（誤判成全系缺專長與學歷 21 人），改用 `teacher/info` 後，
工工系實際是 21 位全部都有專長與學歷。**日後擴充查核項目，先確認該欄位是不是 JS 帶入的。**

分頁上每位師資都內嵌一張臉部縮圖（84px JPEG），**判讀數值只供排序參考，最終仍請目視確認**。

## 相依套件

`check-faculty.py` 需要 `opencv-python-headless<5`（5.0 的 headless 版沒有 `objdetect`，
`cv2.CascadeClassifier` 會不存在）、`numpy`、`Pillow`、`requests`、`beautifulsoup4`。
校內網站憑證鏈缺 Subject Key Identifier，新版 OpenSSL 會擋，腳本內以 `verify=False` 略過。

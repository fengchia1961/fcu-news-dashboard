# -*- coding: utf-8 -*-
"""把 Canva 原稿匯出的整頁截圖，實體裁切成簡報裡真正要用的那一塊。

原本是用 CSS transform(scale/translate) 在瀏覽器裡裁，瀏覽器沒問題，
但匯入 Canva 時 transform 不會被正確轉換，圖會跑掉、舊標題會露出來。
所以改成先實體裁好，HTML 端就只要單純放圖。

輸出：img/cNN.png，並印出每張的長寬比供 HTML 設定 aspect-ratio。
"""
import pathlib
from PIL import Image

HERE = pathlib.Path(__file__).parent
IMG = HERE / "img"

# 輸出檔名 -> (來源檔, (left, top, right, bottom))，座標以 1280x720 原圖為準
CROPS = {
    "c04":  ("p04", (230,  25, 1035, 695)),  # Google 搜尋結果：去掉左右大留白與右下角 QR
    "c03":  ("p03", (  0,   0, 1280, 712)),  # ChatGPT 工工系：整張，只去掉底部白邊
    "c13":  ("p13", ( 48, 105,  665, 445)),  # 我追問 → AI 承認寫錯 + 實際情況表
    "c18":  ("p18", ( 42, 130, 1198, 232)),  # 會計系紅色警示列
    "c08":  ("p08", ( 28, 140, 1256, 640)),  # 健檢儀表板畫面（去掉舊標題與網址）
    "c09":  ("p09", ( 33, 122, 1218, 620)),  # 對話式開發左右兩張對話截圖
    # 電子系教與學空間（案例一）。健檢原文那一條原本也想用截圖，
    # 但原圖字太小，放到投影片上讀不出來，改成在頁面上打字，只留這張場域圖。
    "c11b": ("p11", (765, 312, 1243, 638)),  # 「電子學實驗室」場域實際呈現
}

for name, (src_name, box) in CROPS.items():
    src = Image.open(IMG / f"{src_name}.png").convert("RGB")
    out = src.crop(box)
    dst = IMG / f"{name}.png"
    out.save(dst, optimize=True)
    w, h = out.size
    print(f"{dst.name:>10}  {w}x{h}  aspect {w/h:.3f}")

# -*- coding: utf-8 -*-
"""從 pitch/index.html 產生 pitch/canva.html（給 Canva 匯入用的靜態版）。

差別：
 - 22 頁全部展開、垂直堆疊，沒有翻頁 JS
 - 每頁加上 data-document-role="page" / data-label / data-speaker-notes
 - 圖片改成 GitHub Pages 絕對網址（Canva 匯入時要抓得到）
 - QR 改成靜態圖片（匯入後直接烘進設計裡）
 - 頁碼直接寫死

改完 index.html 之後重跑：python pitch/_build_canva.py
"""
import re
import html
import pathlib

HERE = pathlib.Path(__file__).parent
BASE = "https://fengchia1961.github.io/fcu-news-dashboard/pitch/"

src = (HERE / "index.html").read_text(encoding="utf-8")

# ── 取出 <style> ────────────────────────────────────────────────
style = re.search(r"<style>(.*?)</style>", src, re.S).group(1)

# 把舞台/互動相關的規則換掉：頁面改成靜態堆疊
style = style.replace(
    "#stage{position:relative;width:1280px;height:720px;transform-origin:center center;flex:none}",
    "#stage{position:relative;width:1280px;margin:0 auto}",
)
style = style.replace(
    ".slide{\n  position:absolute;inset:0;background:var(--paper);",
    ".slide{\n  position:relative;width:1280px;height:720px;background:var(--paper);",
)
style = style.replace(".slide.on{display:flex}", ".slide{display:flex}")
style = style.replace(
    "body{\n  margin:0;background:#1a1012;color:var(--ink);\n  font-family:var(--sans);\n  display:flex;align-items:center;justify-content:center;overflow:hidden;\n}",
    "body{margin:0;background:#fff;color:var(--ink);font-family:var(--sans)}",
)
# 移除只給簡報模式用的 UI
style = re.sub(r"#bar\{[^}]*\}", "", style)
style = re.sub(r"#hud[^{]*\{[^}]*\}", "", style)
style = re.sub(r"#notes[^{]*\{[^}]*\}", "", style)
style = re.sub(r"#grid[^{]*\{[^}]*\}", "", style)
style = re.sub(r"@media print\{.*?\n\}", "", style, flags=re.S)

# ── Canva 轉檔器不吃的效果，在這裡改掉（只影響 canva.html，不動 index.html）──
style += """
/* Canva 匯入修正 */
.hl{background:none;color:var(--orange);font-weight:700}          /* 螢光底色會變成實心色塊 */
.chip{padding:12px 24px;font-size:15px;line-height:1.6;border-radius:26px}  /* 膠囊太窄會爆字 */
ul.bul{list-style:disc;padding-left:24px}                          /* ::before 方塊會跑位 */
ul.bul li{padding-left:0}
ul.bul li::before{display:none}
.step::after{display:none}                                         /* 箭頭三角轉不過去 */
"""

# ── 取出 22 頁 ──────────────────────────────────────────────────
pages = re.findall(r'(<section class="slide[^"]*"[^>]*data-notes="(.*?)">)(.*?)</section>',
                   src, re.S)

out = []
for idx, (open_tag, notes, inner) in enumerate(pages, start=1):
    cls = re.search(r'class="([^"]*)"', open_tag).group(1)

    # 頁面標題：取 h1 或 h2 的純文字
    m = re.search(r"<h[12][^>]*>(.*?)</h[12]>", inner, re.S)
    label = re.sub(r"<[^>]+>", "", m.group(1)) if m else f"第 {idx} 頁"
    label = html.unescape(re.sub(r"\s+", " ", label)).strip()

    body = inner
    # 圖片改絕對網址
    body = body.replace('src="img/', f'src="{BASE}img/')
    # 頁碼寫死
    body = body.replace('<span class="pg"></span>', f'<span class="pg">{idx:02d}</span>')
    # QR 改靜態圖
    def qr(mm):
        url = mm.group(1)
        api = ("https://api.qrserver.com/v1/create-qr-code/?size=420x420&margin=0"
               f"&color=761623&bgcolor=ffffff&data={html.escape(url, quote=True)}")
        return f'<div class="box"><img src="{api}" alt="QR code: {url}"></div>'
    body = re.sub(r'<div class="box" data-qr="([^"]+)"></div>', qr, body)

    notes_attr = html.escape(html.unescape(notes), quote=True)
    out.append(
        f'<section class="{cls}" data-document-role="page" '
        f'data-label="{html.escape(label, quote=True)}" '
        f'data-speaker-notes="{notes_attr}">{body}</section>'
    )

doc = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>AI領航簡報｜秘書處公共事務組（Canva 匯入版）</title>
<meta name="description" content="從網站健檢、新聞監測到議題行銷——逢甲大學秘書處公共事務組與 AI 協作成果簡報，16:9 靜態版，供 Canva 匯入。">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&family=Noto+Serif+TC:wght@600;700;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>{style}</style>
</head>
<body>
<div id="stage">
{chr(10).join(out)}
</div>
</body>
</html>
"""

(HERE / "canva.html").write_text(doc, encoding="utf-8")
print(f"canva.html 已產生：{len(pages)} 頁")

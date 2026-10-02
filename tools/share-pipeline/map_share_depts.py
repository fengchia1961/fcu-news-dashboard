# -*- coding: utf-8 -*-
import os
from pathlib import Path
HERE = Path(__file__).resolve().parent
PROJ = HERE.parent.parent          # fcu-news-dashboard/
import json
import re
import sys
import openpyxl

sys.stdout.reconfigure(encoding='utf-8')   # 未對應清單含罕用字，cp950 會炸

XLSX_FILE       = HERE / "學院系列表.xlsx"
SHARE_FULL_FILE = HERE / "share_full.json"
OUT_FILE        = HERE / "share_dept_map.json"

# 文章標題裡常見的系所簡稱 -> 學院系列表.xlsx 裡的正式系所全名。
# 簡稱沒被這張表收錄的，一律視為「未對應」而不是亂猜，新增文章時用 unmatched 清單回頭補。
ALIAS = {
    "資工系": "資訊工程學系",
    "資訊系": "資訊工程學系",
    "環工系": "環境工程與科學學系",
    "財稅系": "財稅學系",
    "行銷系": "行銷學系",
    "經濟系": "經濟學系",
    "運輸物流系": "運輸與物流學系",
    "材料系": "材料科學與工程學系",
    "財金系": "財務金融學系",
    "財務金融學系": "財務金融學系",
    "風保系": "風險管理與保險學系",
    "航太系": "航太與系統工程學系",
    "財算系": "財務工程與精算學士學位學程",
    "財務工程與精算學士學位學程": "財務工程與精算學士學位學程",
    "外文系": "外國語文學系",
    "外語系": "外國語文學系",
    "自控系": "自動控制工程學系",
    "自動控制工程學系": "自動控制工程學系",
    "會計系": "會計學系",
    "水利系": "水利工程與資源保育學系",
    "企管系": "企業管理學系",
    "機電系": "機械與電腦輔助工程學系",
    "精密系": "精密系統設計學士學位學程",
    "光電系": "光電科學與工程學系",
    "國貿系": "國際經營與貿易學系",
    "都資系": "都市計畫與空間資訊學系",
    "統計系": "統計學系",
    "綠色能源科技碩士學位學程": "綠色能源科技碩士學位學程",
    "中文系": "中國文學系",
    "土管系": "土地管理學系",
    "化工系": "化學工程學系",
    "通訊系": "通訊工程學系",
    "合經系": "合作經濟暨社會事業經營學系",
    "人工智慧學程": "人工智慧技術與應用學士學位學程",
    "電子系": "電子工程學系",
    "創設系": None,          # 查無對應系所，無法確認
    "室內設計系": "建築專業學院",  # xlsx未列出該學院的細項系所，歸入學院層級
    "土木系": "土木工程學系",
    "電機系": "電機工程學系",
    "纖維複合系": "纖維與複合材料學系",
}

# 標題不符合「逢甲OO系/學程 姓名」這種一般格式的少數例外，按文章 id 直接指定。
ID_OVERRIDE = {
    46969: "國際企業管理全英語學士學位學程",
    45213: "國際企業管理全英語學士學位學程",
    37424: "國際企業管理全英語學士學位學程",
    37423: "國際企業管理全英語學士學位學程",
    34772: "國際企業管理全英語學士學位學程",
    33934: "國際企業管理全英語學士學位學程",
    33521: "國際企業管理全英語學士學位學程",
    31718: "國際企業管理全英語學士學位學程",
    38974: "資訊電機學院學士班",
    32979: "財經法律研究所",
    5923:  None,  # RMIT-FCU 雙聯學位，非單一系所
    1788:  None,  # SJSU-FCU 雙聯學位，非單一系所
    52374: "財務金融學系",  # 標題寫「逢甲財金施亘芸」，沒有「系」字，DEPT_PATTERN 抓不到
}

DEPT_PATTERN = re.compile(r"逢甲([一-鿿]{2,12}?(?:系|學程|中心|學院|學位學程))")

def load_colleges():
    wb = openpyxl.load_workbook(XLSX_FILE, data_only=True)
    ws = wb.worksheets[0]
    colleges = []
    depts_by_col = {}
    dept_to_college = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        col, dept = row[0], row[1]
        if not col or not dept:
            continue
        col, dept = col.strip(), dept.strip()
        if col not in depts_by_col:
            depts_by_col[col] = []
            colleges.append({"col": col, "depts": depts_by_col[col]})
        if dept not in depts_by_col[col]:
            depts_by_col[col].append(dept)
        dept_to_college[dept] = col
    return colleges, dept_to_college

def assign_dept(item):
    if item["id"] in ID_OVERRIDE:
        return ID_OVERRIDE[item["id"]]
    m = DEPT_PATTERN.search(item["title"])
    short = m.group(1) if m else None
    return ALIAS.get(short) if short else None

def main():
    colleges, dept_to_college = load_colleges()
    items = json.load(open(SHARE_FULL_FILE, encoding="utf-8"))

    article_dept = {}
    unmatched = []
    for it in items:
        dept = assign_dept(it)
        college = dept_to_college.get(dept) if dept else None
        article_dept[str(it["id"])] = {"college": college, "dept": dept}
        if dept is None:
            unmatched.append({"id": it["id"], "title": it["title"]})

    result = {
        "colleges": colleges,
        "articleDept": article_dept,
        "unmatched": unmatched,
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("已產生", OUT_FILE)
    print(f"   學院數：{len(colleges)}｜官方系所數：{sum(len(c['depts']) for c in colleges)}")
    print(f"   文章總數：{len(items)}｜未對應：{len(unmatched)}")
    for u in unmatched:
        print("   -", u["id"], u["title"][:50])

if __name__ == "__main__":
    main()

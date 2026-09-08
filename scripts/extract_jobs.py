#!/usr/bin/env python3
"""ハローワーク求人票PDF（data/求人票/*.pdf）から主要項目を抽出し、
重複除去・職種分類を行って analysis/data/求人一覧.csv を生成する。

依存: pdfplumber
使い方: python3 scripts/extract_jobs.py
"""
import collections
import csv
import glob
import json
import os
import re

import pdfplumber

PDF_DIR = "data/求人票"
OUT_CSV = "analysis/data/求人一覧.csv"
OUT_JSON = "analysis/data/求人一覧.json"

# ハローワーク求人票（フルタイム）の固定レイアウト上の抽出領域 (x0, top, x1, bottom)
BOXES = {
    "事業所名": (36, 126, 292, 168),
    "就業場所": (312, 144, 560, 182),
    "職種": (40, 248, 292, 276),
    "仕事内容": (40, 274, 292, 470),
    "学歴": (310, 338, 560, 368),
    "経験": (310, 368, 560, 406),
    "PCスキル": (310, 406, 560, 452),
    "免許資格": (310, 452, 560, 532),
    "賃金": (580, 120, 841, 136),
    "特記事項": (290, 940, 560, 1190),
}


def crop_text(page, box):
    """領域内の横書き語を行単位に組み直して返す。"""
    words = [w for w in page.crop(box).extract_words() if w["upright"]]
    words.sort(key=lambda w: (round(w["top"] / 5), w["x0"]))
    lines, cur, buf = [], None, []
    for w in words:
        k = round(w["top"] / 5)
        if cur is not None and k != cur:
            lines.append("".join(buf))
            buf = []
        cur = k
        buf.append(w["text"])
    if buf:
        lines.append("".join(buf))
    return " ".join(lines).strip()


def undouble(s):
    """求人票の太字は同一グリフを2度描画するため畳む（例: 求求人人票票 → 求人票）。"""
    out, i = [], 0
    while i < len(s):
        if i + 1 < len(s) and s[i] == s[i + 1]:
            out.append(s[i])
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


# 職種名だけでは判別できない個別求人の分類（仕事内容を読んで判断）
OVERRIDES = {
    "工事部／マネージャー（新築住宅／リフォーム）": "施工管理・現場監督（工務）",
    "工事部・住宅部のスタッフ": "建材・住宅設備の法人／ルート営業",
}


def classify(rec):
    t = rec["職種"]
    if t in OVERRIDES:
        return OVERRIDES[t]
    if re.search(r"介護|看護師|看護職|准看|ヘルパー|ケアスタッフ|ケアリーダー|生活相談員|"
                 r"サービス提供責任者|施設長|訪問介護|調理員|調理師|高齢者住宅内の調理|"
                 r"高齢者向け住宅管理者|相談員", t):
        return "＜業界外＞介護・看護・給食"
    if re.search(r"オフハウスの販売|ハウスクリーニング", t):
        return "＜業界外＞その他"
    if re.search(r"公営住宅|賃貸住宅管理|指定管理", t):
        return "住宅管理・不動産事務"
    if re.search(r"ＣＡＤ|CADオペ", t):
        return "設計・ＣＡＤオペレーター"
    if re.search(r"設計|代願|確認申請|プランニング補助", t) and "営業" not in t:
        return "設計・ＣＡＤオペレーター"
    if re.search(r"配管|水道|電気工事|設備工事|設備職人|管工事|住宅設備の工事|"
                 r"住宅設備取付|住宅設備機器取付|住宅機器取り付け|^住宅設備$", t):
        return "設備工事（配管・電気・住宅設備）"
    if re.search(r"施工管理|現場監督|現場管理|現場代理人|工務|監督員|品質管理|建設現場管理|"
                 r"現場監理|職長|技術職（工事）|リフォーム全般", t):
        return "施工管理・現場監督（工務）"
    if re.search(r"メンテナンス|アフターサービス|アフターサポート|点検|補修|リペア|検査員", t):
        return "メンテナンス・アフターサービス・点検"
    if re.search(r"大工|多能工|内装|左官|型枠|基礎工事|基礎作業|足場|屋根|外壁|塗装|板金|解体|"
                 r"鍛冶|外構|土木|湿気対策|リフォーム職人|施工スタッフ|施工員|工事スタッフ|"
                 r"現場作業員|現場補助|職人|取り付け|取付|作業員|リフォーム工事等|住宅リフォーム$", t):
        return "施工技能職（大工・内外装・基礎・足場ほか）"
    if re.search(r"ドライバー|配送|運送|配達", t):
        return "配送・ドライバー"
    if re.search(r"製造|組立|加工|オペレーター", t):
        return "製造・加工（プレカット／建材）"
    if re.search(r"事務|受付|広報|マーケティング|プレゼン資料", t):
        return "事務・営業事務・広報"
    if re.search(r"資材|建材|サッシ|住宅設備機器|住設|福祉用具|ルート営業|法人営業|法人ルート", t):
        return "建材・住宅設備の法人／ルート営業"
    if re.search(r"営業|アドバイザー|コンシェルジュ|プランナー|コーディネーター|コンサルタント|"
                 r"販売|クライアントパートナー|エンジニア|担当|スタッフ|不動産", t):
        return "住宅・リフォーム営業（提案営業）"
    return "（未分類）"


def wage_range(s):
    m = re.findall(r"(\d{5,7})円", undouble(s.replace(",", "")))
    return (int(m[0]), int(m[1])) if len(m) >= 2 else (None, None)


def prefecture(filename):
    for p in ("宮崎", "山梨", "愛媛", "鳥取", "千葉"):
        if p in filename:
            return p
    return ""


def main():
    records = []
    for path in sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf"))):
        src = os.path.basename(path)
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages):
                rec = {"出典ファイル": src, "頁": i + 1, "都道府県": prefecture(src)}
                for key, box in BOXES.items():
                    rec[key] = crop_text(page, box)
                records.append(rec)
        print(f"読込 {src}: {len(records)} 件累計")

    # 同一事業所・同一職種の重複（ファイル間の重複掲載）を除去
    seen, uniq = set(), []
    for r in records:
        key = (r["事業所名"], r["職種"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)

    for r in uniq:
        r["分類"] = classify(r)
        lo, hi = wage_range(r["賃金"])
        r["賃金下限"], r["賃金上限"] = lo, hi
        r["未経験可"] = "不問" in r["経験"]
        r["運転免許必須"] = bool(re.search(r"普通自動車運転免許\s*必須", undouble(r["免許資格"])))

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    cols = ["分類", "職種", "事業所名", "都道府県", "就業場所", "賃金下限", "賃金上限",
            "未経験可", "運転免許必須", "経験", "免許資格", "PCスキル", "学歴",
            "仕事内容", "特記事項", "出典ファイル", "頁"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(uniq)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(uniq, f, ensure_ascii=False, indent=1)

    print(f"\n求人票 {len(records)} 頁 → 重複除去後 {len(uniq)} 件")
    for k, v in collections.Counter(r["分類"] for r in uniq).most_common():
        print(f"  {v:>4}  {k}")


if __name__ == "__main__":
    main()

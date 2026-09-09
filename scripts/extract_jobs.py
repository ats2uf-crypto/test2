#!/usr/bin/env python3
"""ハローワーク求人票PDFから主要項目を抽出し、重複除去・職種分類を行ってCSV/JSONを生成する。

依存: pdfplumber
使い方:
    python3 scripts/extract_jobs.py                       # data/求人票 → analysis/data/求人一覧
    python3 scripts/extract_jobs.py <PDFディレクトリ> <出力名の接尾辞>
例:
    python3 scripts/extract_jobs.py data/求人票_2026-09-09 _2026-09-09
"""
import collections
import csv
import glob
import json
import os
import re

import pdfplumber

import sys as _sys

PDF_DIR = _sys.argv[1] if len(_sys.argv) > 1 else "data/求人票"
_SUFFIX = _sys.argv[2] if len(_sys.argv) > 2 else ""
OUT_CSV = f"analysis/data/求人一覧{_SUFFIX}.csv"
OUT_JSON = f"analysis/data/求人一覧{_SUFFIX}.json"

# ハローワーク求人票（フルタイム）の固定レイアウト上の抽出領域 (x0, top, x1, bottom)
BOXES = {
    "産業分類": (690, 72, 841, 92),
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


QUAL_BOX = (292, 450, 560, 534)  # 免許・資格欄（行単位で読む）


def qual_rows(page):
    """免許・資格欄を1行＝1資格として読み、[(資格名, 必須/あれば尚可), ...] を返す。

    欄内は「資格名」と「必須／あれば尚可」が別の列に置かれた行の並びなので、
    行を潰さずに読むこと。行をまとめて読むと隣接資格と結合し、必須件数を取り違える。
    """
    rows = {}
    for w in page.crop(QUAL_BOX).extract_words():
        if not w["upright"] or w["x0"] < 310:   # 縦書きラベル列を除外
            continue
        rows.setdefault(round(w["top"] / 4), []).append(w)
    out = []
    for k in sorted(rows):
        txt = "".join(w["text"] for w in sorted(rows[k], key=lambda w: w["x0"]))
        if "必須" in txt:
            mark = "必須"
        elif "尚可" in txt:
            mark = "あれば尚可"
        else:
            continue                            # 注記行・欄外行は捨てる
        name = re.sub(r"[（(].*$", "", re.split(r"必須|あれば尚可", txt)[0]).strip()
        if name:
            out.append((name, mark))
    return out


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


def clean_industry(s):
    """「産業分類 065木造建築工事業」→「木造建築工事業」。"""
    return re.sub(r"^産業分類\s*\d*\s*", "", s).strip()


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
    return classify_by_duties(rec)


def classify_by_duties(rec):
    """職種名だけでは判別できない求人を「仕事内容」欄から分類する。

    職種名ルールが（未分類）を返したときだけ呼ばれる追加経路であり、
    既存の分類結果を変えない。「建築技術者」「総合職」のように職種名が
    抽象的な求人を拾うために設けた。
    """
    t = rec["職種"] + " " + rec["仕事内容"]
    if re.search(r"アシスタント|事務処理|データ入力|受注対応", t) \
            and not re.search(r"施工管理|現場監督|現場管理", t):
        if re.search(r"リース|資材|建材", t):
            return "建材・住宅設備の法人／ルート営業"
        return "事務・営業事務・広報"
    if re.search(r"施工管理|現場監督|現場管理|工事監督|監督業務|工程管理|安全管理|現場の管理", t):
        return "施工管理・現場監督（工務）"
    if re.search(r"点検|修繕|補修|メンテナンス|アフター", t):
        return "メンテナンス・アフターサービス・点検"
    if re.search(r"給湯|水廻り|水回り|配管|給排水|電気工事|設備工事|据付", t):
        return "設備工事（配管・電気・住宅設備）"
    if re.search(r"断熱|熱絶縁|足場|鳶|溶接|清掃|美装|軽作業|解体|塗装|内装|大工|加工", t):
        return "施工技能職（大工・内外装・基礎・足場ほか）"
    if re.search(r"設計|図面|間取り|プランニング", t):
        return "設計・ＣＡＤオペレーター"
    if re.search(r"リース|資材|建材", t):
        return "建材・住宅設備の法人／ルート営業"
    if re.search(r"営業|提案|接客|お客様", t):
        return "住宅・リフォーム営業（提案営業）"
    return "（未分類）"


def wage_range(s):
    m = re.findall(r"(\d{5,7})円", undouble(s.replace(",", "")))
    return (int(m[0]), int(m[1])) if len(m) >= 2 else (None, None)


PREFECTURES = (
    "北海道", "青森", "岩手", "宮城", "秋田", "山形", "福島", "茨城", "栃木", "群馬",
    "埼玉", "千葉", "東京", "神奈川", "新潟", "富山", "石川", "福井", "山梨", "長野",
    "岐阜", "静岡", "愛知", "三重", "滋賀", "京都", "大阪", "兵庫", "奈良", "和歌山",
    "鳥取", "島根", "岡山", "広島", "山口", "徳島", "香川", "愛媛", "高知", "福岡",
    "佐賀", "長崎", "熊本", "大分", "宮崎", "鹿児島", "沖縄",
)


def prefecture(filename):
    """ファイル名から都道府県を判定する。就業場所欄からの判定は行わない。"""
    for p in PREFECTURES:
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
                qs = qual_rows(page)
                rec["必須資格"] = "／".join(n for n, m in qs if m == "必須")
                rec["尚可資格"] = "／".join(n for n, m in qs if m == "あれば尚可")
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
        r["産業分類"] = clean_industry(r["産業分類"])
        r["分類"] = classify(r)
        lo, hi = wage_range(r["賃金"])
        r["賃金下限"], r["賃金上限"] = lo, hi
        r["未経験可"] = "不問" in r["経験"]
        r["運転免許必須"] = "普通自動車運転免許" in r["必須資格"]

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    cols = ["分類", "職種", "事業所名", "都道府県", "産業分類", "就業場所", "賃金下限", "賃金上限",
            "未経験可", "運転免許必須", "経験", "必須資格", "尚可資格", "免許資格", "PCスキル", "学歴",
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

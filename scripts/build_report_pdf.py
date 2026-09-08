#!/usr/bin/env python3
"""報告書PDFを生成する。内容は scripts/report_content.py に定義したものを描画するだけ。

出力: report/職業訓練カリキュラム開発_求人分析報告書.pdf
依存: reportlab, IPAゴシック（/usr/share/fonts/opentype/ipafont-gothic/）
"""
import os
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report_content as RC  # noqa: E402

OUT = "report/職業訓練カリキュラム開発_求人分析報告書.pdf"
FONT_DIR = "/usr/share/fonts/opentype/ipafont-gothic/"
pdfmetrics.registerFont(TTFont("JP", FONT_DIR + "ipagp.ttf"))
pdfmetrics.registerFontFamily("JP", normal="JP", bold="JP", italic="JP", boldItalic="JP")

INK = colors.HexColor("#1a1a1a")
ACCENT = colors.HexColor("#1f4e79")
LINE = colors.HexColor("#c8d4e0")
BAND = colors.HexColor("#eef3f8")
MUTED = colors.HexColor("#555555")
EMPH = "#1f4e79"


def emph(t):
    """太字フォントを持たないため、強調は色で表現する。"""
    return t.replace("<b>", f"<font color='{EMPH}'>").replace("</b>", "</font>")


S = {
    "title": ParagraphStyle("title", fontName="JP", fontSize=17, leading=24,
                            textColor=ACCENT, spaceAfter=2),
    "sub": ParagraphStyle("sub", fontName="JP", fontSize=9.5, leading=14, textColor=MUTED),
    "h1": ParagraphStyle("h1", fontName="JP", fontSize=12.5, leading=18, textColor=ACCENT,
                         spaceBefore=13, spaceAfter=5),
    "h2": ParagraphStyle("h2", fontName="JP", fontSize=10.5, leading=15, textColor=INK,
                         spaceBefore=8, spaceAfter=3),
    "body": ParagraphStyle("body", fontName="JP", fontSize=9.3, leading=15.2,
                           textColor=INK, spaceAfter=4),
    "bullet": ParagraphStyle("bullet", fontName="JP", fontSize=9.3, leading=15.2,
                             textColor=INK, leftIndent=11, bulletIndent=2, spaceAfter=2.5,
                             bulletFontName="JP", bulletFontSize=9.3),
    "note": ParagraphStyle("note", fontName="JP", fontSize=8.4, leading=13,
                           textColor=MUTED, spaceAfter=3),
    "warn": ParagraphStyle("warn", fontName="JP", fontSize=9.1, leading=14.5,
                           textColor=colors.HexColor("#8a4b08"), spaceAfter=3),
    "cell": ParagraphStyle("cell", fontName="JP", fontSize=8.2, leading=11.5, textColor=INK),
    "cellh": ParagraphStyle("cellh", fontName="JP", fontSize=8.2, leading=11.5,
                            textColor=colors.white),
    "small": ParagraphStyle("small", fontName="JP", fontSize=7.4, leading=10.2, textColor=INK),
    "smallh": ParagraphStyle("smallh", fontName="JP", fontSize=7.2, leading=9.8,
                             textColor=colors.white, alignment=TA_CENTER),
}
for _st in S.values():
    _st.wordWrap = "CJK"
S["cellr"] = ParagraphStyle("cellr", parent=S["cell"], alignment=TA_RIGHT)
S["smallr"] = ParagraphStyle("smallr", parent=S["small"], alignment=TA_RIGHT)


def P(t, s="body"):
    return Paragraph(emph(t), S[s])


def make_table(blk):
    fs = "small" if blk.get("small") else "cell"
    hstyle = "smallh" if fs == "small" else "cellh"
    rstyle = "smallr" if fs == "small" else "cellr"
    rf = blk.get("right_from")
    data = []
    for i, row in enumerate(blk["rows"]):
        cells = []
        for j, c in enumerate(row):
            if i == 0:
                st = hstyle
            elif rf is not None and j >= rf:
                st = rstyle
            else:
                st = fs
            cells.append(Paragraph(emph(c).replace("\n", "<br/>"), S[st]))
        data.append(cells)
    pad = 3.4 if fs == "small" else 4
    t = Table(data, colWidths=blk["widths"], repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), pad - 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), pad - 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BAND]),
    ]))
    return t


def make_meta(blk):
    data = [[Paragraph(c, S["cell"]) for c in row] for row in blk["rows"]]
    t = Table(data, colWidths=blk["widths"], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("BACKGROUND", (0, 0), (0, -1), BAND), ("BACKGROUND", (2, 0), (2, -1), BAND),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    return t


def make_callout(blk):
    inner = [Paragraph(f"<font color='#8a4b08'>{blk['title']}</font>", S["h2"])]
    inner += [Paragraph(x.replace("<b>", "<font color='#7a3b00'>").replace("</b>", "</font>"),
                        S["warn"]) for x in blk["lines"]]
    t = Table([[inner]], colWidths=[RC.W], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#e0b070")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fdf6ec")),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("JP", 7.6)
    canvas.setFillColor(MUTED)
    canvas.drawString(25 * mm, 12 * mm, RC.FOOTER)
    canvas.drawRightString(A4[0] - 25 * mm, 12 * mm, f"- {doc.page} -")
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.4)
    canvas.line(25 * mm, 15 * mm, A4[0] - 25 * mm, 15 * mm)
    canvas.restoreState()


def build():
    os.makedirs("report", exist_ok=True)
    doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=25 * mm, rightMargin=25 * mm,
                          topMargin=18 * mm, bottomMargin=20 * mm,
                          title=RC.DOC_TITLE, author="", subject="住宅・リフォーム業界の求人票分析")
    doc.addPageTemplates([PageTemplate(
        id="p", frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")],
        onPage=footer)])

    story = []
    for blk in RC.blocks():
        t = blk["t"]
        if t in ("title", "sub", "h1", "h2", "body", "note"):
            story.append(P(blk["text"], t))
        elif t == "bullets":
            story += [Paragraph(emph(x), S["bullet"], bulletText="・") for x in blk["items"]]
        elif t == "meta":
            story += [Spacer(1, 5), make_meta(blk)]
        elif t == "table":
            story.append(make_table(blk))
        elif t == "callout":
            story += [make_callout(blk), Spacer(1, 4)]
        elif t == "pagebreak":
            story.append(PageBreak())
        else:
            raise ValueError(f"未知のブロック種別: {t}")
    doc.build(story)
    print("生成:", OUT)


if __name__ == "__main__":
    build()

/**
 * 報告書のWord版（.docx）を生成する。
 * 内容は scripts/report_content.py が書き出す report/report_content.json を読むだけで、
 * PDF版と同じ定義から作られる。数値を直すときは report_content.py を直すこと。
 *
 * 使い方: python3 scripts/report_content.py && node scripts/build_report_docx.js
 */
const fs = require("fs");
const {
  AlignmentType, BorderStyle, Document, Footer, HeadingLevel, LevelFormat, PageBreak,
  PageNumber, Packer, Paragraph, ShadingType, Table, TableCell, TableRow, TextRun,
  VerticalAlign, WidthType,
} = require("docx");

const SRC = "report/report_content.json";
const OUT = "report/職業訓練カリキュラム開発_求人分析報告書.docx";

const doc_ = JSON.parse(fs.readFileSync(SRC, "utf8"));
const BLOCKS = doc_.blocks;

// A4(11906dxa) から左右余白25mm(1417dxa)を引いた本文幅
const CONTENT_DXA = 11906 - 1417 * 2;
const SCALE = CONTENT_DXA / doc_.width;
const dxa = (pt) => Math.round(pt * SCALE);

const FONT = { ascii: "Yu Gothic", eastAsia: "Yu Gothic", hAnsi: "Yu Gothic" };
const INK = "1A1A1A";
const ACCENT = "1F4E79";
const LINE = "C8D4E0";
const BAND = "EEF3F8";
const MUTED = "555555";
const WARN = "8A4B08";

/** <b>…</b> を実際の太字ランに変換する。 */
function runs(text, opts = {}) {
  const out = [];
  const re = /<b>(.*?)<\/b>/gs;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...opts }));
    out.push(new TextRun({ text: m[1], ...opts, bold: true }));
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...opts }));
  return out.length ? out : [new TextRun({ text: "", ...opts })];
}

const para = (text, opts = {}, pOpts = {}) =>
  new Paragraph({ children: runs(text, opts), ...pOpts });

/** セル内の改行は段落を分けて表現する（\n は使えない）。 */
function cellParas(text, opts, align) {
  return text.split("\n").map((line) =>
    new Paragraph({
      children: runs(line, opts),
      alignment: align,
      spacing: { before: 20, after: 20 },
    }));
}

function table(blk) {
  const small = !!blk.small;
  const size = small ? 15 : 17;          // half-points (7.5pt / 8.5pt)
  const widths = blk.widths.map(dxa);
  const total = widths.reduce((a, b) => a + b, 0);
  widths[widths.length - 1] += CONTENT_DXA - total;   // 端数を最終列で吸収

  const rows = blk.rows.map((row, i) =>
    new TableRow({
      tableHeader: i === 0,
      children: row.map((c, j) => {
        const isHead = i === 0;
        const right = !isHead && blk.right_from !== null && blk.right_from !== undefined
          && j >= blk.right_from;
        return new TableCell({
          width: { size: widths[j], type: WidthType.DXA },
          shading: {
            type: ShadingType.CLEAR, color: "auto",
            fill: isHead ? ACCENT : (i % 2 === 0 ? BAND : "FFFFFF"),
          },
          verticalAlign: VerticalAlign.CENTER,
          margins: { top: 40, bottom: 40, left: 80, right: 80 },
          children: cellParas(
            c,
            { font: FONT, size, color: isHead ? "FFFFFF" : INK, bold: isHead },
            isHead ? AlignmentType.CENTER : (right ? AlignmentType.RIGHT : AlignmentType.LEFT),
          ),
        });
      }),
    }));

  const b = { style: BorderStyle.SINGLE, size: 3, color: LINE };
  return new Table({
    columnWidths: widths,
    width: { size: CONTENT_DXA, type: WidthType.DXA },
    borders: { top: b, bottom: b, left: b, right: b, insideHorizontal: b, insideVertical: b },
    rows,
  });
}

function meta(blk) {
  const widths = blk.widths.map(dxa);
  widths[widths.length - 1] += CONTENT_DXA - widths.reduce((a, c) => a + c, 0);
  const b = { style: BorderStyle.SINGLE, size: 3, color: LINE };
  return new Table({
    columnWidths: widths,
    width: { size: CONTENT_DXA, type: WidthType.DXA },
    borders: { top: b, bottom: b, left: b, right: b, insideHorizontal: b, insideVertical: b },
    rows: blk.rows.map((row) => new TableRow({
      children: row.map((c, j) => new TableCell({
        width: { size: widths[j], type: WidthType.DXA },
        shading: {
          type: ShadingType.CLEAR, color: "auto",
          fill: j % 2 === 0 ? BAND : "FFFFFF",
        },
        verticalAlign: VerticalAlign.CENTER,
        margins: { top: 50, bottom: 50, left: 80, right: 80 },
        children: cellParas(c, { font: FONT, size: 17, color: INK }, AlignmentType.LEFT),
      })),
    })),
  });
}

function callout(blk) {
  const children = [
    new Paragraph({
      children: runs(blk.title, { font: FONT, size: 20, color: WARN, bold: true }),
      spacing: { before: 40, after: 60 },
    }),
    ...blk.lines.map((l) => new Paragraph({
      children: runs(l, { font: FONT, size: 18, color: WARN }),
      spacing: { after: 60, line: 290 },
    })),
  ];
  const b = { style: BorderStyle.SINGLE, size: 6, color: "E0B070" };
  return new Table({
    columnWidths: [CONTENT_DXA],
    width: { size: CONTENT_DXA, type: WidthType.DXA },
    borders: { top: b, bottom: b, left: b, right: b, insideHorizontal: b, insideVertical: b },
    rows: [new TableRow({
      children: [new TableCell({
        width: { size: CONTENT_DXA, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, color: "auto", fill: "FDF6EC" },
        margins: { top: 120, bottom: 120, left: 180, right: 180 },
        children,
      })],
    })],
  });
}

const spacer = () => new Paragraph({ children: [], spacing: { after: 100 } });

const children = [];
for (const blk of BLOCKS) {
  switch (blk.t) {
    case "title":
      children.push(para(blk.text, { font: FONT, size: 34, color: ACCENT, bold: true },
        { spacing: { after: 60 } }));
      break;
    case "sub":
      children.push(para(blk.text, { font: FONT, size: 19, color: MUTED },
        { spacing: { after: 160 } }));
      break;
    case "h1":
      children.push(para(blk.text, { font: FONT, size: 25, color: ACCENT, bold: true },
        { heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 120 } }));
      break;
    case "h2":
      children.push(para(blk.text, { font: FONT, size: 21, color: INK, bold: true },
        { heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 80 } }));
      break;
    case "body":
      children.push(para(blk.text, { font: FONT, size: 19, color: INK },
        { spacing: { after: 100, line: 300 } }));
      break;
    case "note":
      children.push(para(blk.text, { font: FONT, size: 17, color: MUTED },
        { spacing: { after: 100, line: 270 } }));
      break;
    case "bullets":
      for (const it of blk.items) {
        children.push(para(it, { font: FONT, size: 19, color: INK },
          { numbering: { reference: "bullets", level: 0 }, spacing: { after: 60, line: 300 } }));
      }
      break;
    case "meta":
      children.push(meta(blk), spacer());
      break;
    case "table":
      children.push(table(blk), spacer());
      break;
    case "callout":
      children.push(callout(blk), spacer());
      break;
    case "pagebreak":
      children.push(new Paragraph({ children: [new PageBreak()] }));
      break;
    default:
      throw new Error("未知のブロック種別: " + blk.t);
  }
}

const document = new Document({
  title: doc_.title,
  description: "住宅・リフォーム業界の求人票分析",
  styles: { default: { document: { run: { font: FONT, size: 19, color: INK } } } },
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: "・", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 340, hanging: 200 } } },
      }],
    }],
  },
  sections: [{
    properties: { page: { margin: { top: 1020, bottom: 1130, left: 1417, right: 1417 } } },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          border: { top: { style: BorderStyle.SINGLE, size: 3, color: LINE } },
          tabStops: [{ type: AlignmentType.RIGHT, position: CONTENT_DXA }],
          children: [
            new TextRun({ text: doc_.footer, font: FONT, size: 15, color: MUTED }),
            new TextRun({ text: "\t- ", font: FONT, size: 15, color: MUTED }),
            new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 15, color: MUTED }),
            new TextRun({ text: " -", font: FONT, size: 15, color: MUTED }),
          ],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(document).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log("生成:", OUT, buf.length, "bytes");
});

#!/usr/bin/env python3
"""제안서 마크다운(제한된 문법) → DOCX(python-docx) + PDF(reportlab). 그림 삽입 위치의 '파일:' 경로가 실제로 있으면 그림을 넣는다."""
import re, sys
from pathlib import Path

SRC = Path(sys.argv[1]); FIGROOT = Path(__file__).resolve().parents[1]
FONT_R = str(Path(__file__).resolve().parents[2]) + "/work/fonts/NanumGothic-Regular.ttf"
FONT_B = str(Path(__file__).resolve().parents[2]) + "/work/fonts/NanumGothic-Bold.ttf"

def parse(text):
    blocks = []; lines = text.splitlines(); i = 0
    while i < len(lines):
        l = lines[i]
        if not l.strip():
            i += 1; continue
        if l.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            blocks.append(("table", rows)); continue
        if l.startswith(">"):
            q = []
            while i < len(lines) and lines[i].startswith(">"):
                q.append(lines[i].lstrip("> ").rstrip()); i += 1
            blocks.append(("figure", q)); continue
        m = re.match(r"(#{1,3}) (.*)", l)
        if m:
            blocks.append((f"h{len(m.group(1))}", m.group(2))); i += 1; continue
        if l.strip() == "---":
            blocks.append(("hr", None)); i += 1; continue
        m = re.match(r"\s*(- |\d+\. )(.*)", l)
        if m:
            blocks.append(("bullet" if m.group(1) == "- " else "num", m.group(2), m.group(1))); i += 1; continue
        blocks.append(("p", l.strip())); i += 1
    return blocks

def runs(s):
    s = s.replace("`", "")
    out = []
    for part in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", s):
        if not part:
            continue
        if part.startswith("**"):
            out.append((part[2:-2], "b"))
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            out.append((part[1:-1], "i"))
        else:
            out.append((part, ""))
    return out

def fig_info(q):
    title = q[0].replace("**", "")
    path = next((re.search(r"`([^`]+)`", x).group(1) for x in q if x.startswith("파일")), None)
    cap = next((x.split(":", 1)[1].strip() for x in q if x.startswith("캡션")), "")
    p = FIGROOT / path if path else None
    return title, p if (p and p.exists()) else None, cap, path

blocks = parse(SRC.read_text(encoding="utf-8"))

# ---------------------------------------------------------------- DOCX
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
doc = Document()
sec = doc.sections[0]; sec.left_margin = sec.right_margin = Cm(2.0); sec.top_margin = sec.bottom_margin = Cm(1.8)
def setfont(style, size, bold=False, color=None):
    st = doc.styles[style]; st.font.name = "맑은 고딕"; st.font.size = Pt(size); st.font.bold = bold
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "맑은 고딕")
    if color: st.font.color.rgb = RGBColor.from_string(color)
setfont("Normal", 10); setfont("Heading 1", 15, True, "1C5CAB"); setfont("Heading 2", 13, True, "1C5CAB"); setfont("Heading 3", 11, True, "1F1F1E")
def add_runs(p, s, size=None):
    for t, f in runs(s):
        r = p.add_run(t); r.bold = f == "b"; r.italic = f == "i"
        if size: r.font.size = Pt(size)
for b in blocks:
    k = b[0]
    if k in ("h1", "h2", "h3"):
        doc.add_heading(b[1].replace("**", ""), level=int(k[1]))
    elif k == "p":
        p = doc.add_paragraph(); add_runs(p, b[1]); p.paragraph_format.space_after = Pt(4)
    elif k in ("bullet", "num"):
        p = doc.add_paragraph(style="List Bullet" if k == "bullet" else "List Number"); add_runs(p, b[1])
    elif k == "table":
        rows = b[1]; t = doc.add_table(rows=len(rows), cols=len(rows[0])); t.style = "Light Grid Accent 1"
        for i, row in enumerate(rows):
            for j, c in enumerate(row):
                cell = t.cell(i, j); cell.text = ""; add_runs(cell.paragraphs[0], c, 8.5)
                if i == 0:
                    for r in cell.paragraphs[0].runs: r.bold = True
        doc.add_paragraph()
    elif k == "figure":
        title, p_img, cap, path = fig_info(b[1])
        if p_img:
            doc.add_picture(str(p_img), width=Cm(15.5 if "panel" in p_img.name or "table" in p_img.name else 11.5))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        pc = doc.add_paragraph(); add_runs(pc, f"{title.replace('[', '').replace(' 삽입 위치]', '.')} {cap}", 8.5); pc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif k == "hr":
        pass
out_docx = SRC.with_suffix(".docx"); doc.save(out_docx)

# ---------------------------------------------------------------- PDF
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable, ListFlowable, ListItem
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
pdfmetrics.registerFont(TTFont("NG", FONT_R)); pdfmetrics.registerFont(TTFont("NGB", FONT_B))
addMapping("NG", 0, 0, "NG"); addMapping("NG", 1, 0, "NGB"); addMapping("NG", 0, 1, "NG"); addMapping("NG", 1, 1, "NGB")
BLUE = colors.HexColor("#1c5cab")
S = {"p": ParagraphStyle("p", fontName="NG", fontSize=9.6, leading=15, spaceAfter=4),
     "h1": ParagraphStyle("h1", fontName="NGB", fontSize=15, leading=20, textColor=BLUE, spaceBefore=6, spaceAfter=8),
     "h2": ParagraphStyle("h2", fontName="NGB", fontSize=13.5, leading=18, textColor=BLUE, spaceBefore=10, spaceAfter=6),
     "h3": ParagraphStyle("h3", fontName="NGB", fontSize=11, leading=15, spaceBefore=8, spaceAfter=4),
     "cell": ParagraphStyle("c", fontName="NG", fontSize=8.2, leading=11.5),
     "cap": ParagraphStyle("cap", fontName="NG", fontSize=8.2, leading=11.5, textColor=colors.HexColor("#55544f"), alignment=1, spaceAfter=8)}
def md(s):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("`", "")
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s); s = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", s)
    return s
story = []; W = A4[0] - 3.6 * cm
for b in blocks:
    k = b[0]
    if k in ("h1", "h2", "h3"):
        story.append(Paragraph(md(b[1]), S[k]))
    elif k == "p":
        story.append(Paragraph(md(b[1]), S["p"]))
    elif k in ("bullet", "num"):
        story.append(Paragraph(("• " if k == "bullet" else b[2]) + md(b[1]), ParagraphStyle("li", parent=S["p"], leftIndent=12, firstLineIndent=-9)))
    elif k == "table":
        rows = [[Paragraph(md(c), S["cell"]) for c in r] for r in b[1]]
        n = len(b[1][0]); lens = [max(len(r[j]) for r in b[1]) for j in range(n)]; tot = sum(min(l, 40) + 4 for l in lens)
        t = Table(rows, colWidths=[W * (min(l, 40) + 4) / tot for l in lens], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e3edf9")), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c3c2b7")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        story += [t, Spacer(1, 8)]
    elif k == "figure":
        title, p_img, cap, path = fig_info(b[1])
        if p_img:
            from PIL import Image as PI
            w, h = PI.open(p_img).size; ww = W * (1.0 if ("panel" in p_img.name or "table" in p_img.name or w > 1.6 * h) else 0.7)
            hh = ww * h / w
            if hh > 17 * cm:
                hh = 17 * cm; ww = hh * w / h
            story.append(Image(str(p_img), width=ww, height=hh))
        story.append(Paragraph(md(f"{title.replace('[', '').replace(' 삽입 위치]', '.')} {cap}"), S["cap"]))
    elif k == "hr":
        story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#c3c2b7"), spaceBefore=4, spaceAfter=6))
def pnum(c, d):
    c.setFont("NG", 8); c.drawRightString(A4[0] - 1.8 * cm, 1.0 * cm, f"{d.page}")
out_pdf = SRC.with_suffix(".pdf")
SimpleDocTemplate(str(out_pdf), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.6 * cm, bottomMargin=1.6 * cm,
                  title="평가제안서 A안", author="").build(story, onFirstPage=pnum, onLaterPages=pnum)
print(out_docx, out_pdf)

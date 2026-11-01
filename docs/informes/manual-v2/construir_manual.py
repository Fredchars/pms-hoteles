"""Genera HTML autocontenido, PDF y DOCX del manual por pantalla (Suite v2). Prototipo diseñado para ATm Consulting.
Uso: cd docs/informes && python3 manual-v2/construir_manual.py"""
import re, base64, subprocess, os, markdown
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

N = "manual-pantallas-pms-v2"
md = open(N + ".md", encoding="utf-8").read()
MARCA = "Prototipo diseñado para ATm Consulting"

# ---------- HTML + PDF ----------
css = """body{font-family:Calibri,Arial,sans-serif;max-width:960px;margin:2em auto;padding:0 1em;background:#fff;color:#222;line-height:1.5}
table{border-collapse:collapse;width:100%;margin:1em 0}th,td{border:1px solid #bbb;padding:5px 8px;vertical-align:top;font-size:.9em}th{background:#eef2f7}
img{max-width:100%;height:auto;border:1px solid #e3e8ef;margin:.5em 0}h1,h2,h3{color:#1f3a5f}h2{border-bottom:2px solid #1f3a5f;padding-bottom:.2em}
code{background:#f6f8fa;padding:0 .2em}blockquote{border-left:4px solid #e0a800;background:#fffbea;margin:1em 0;padding:.4em 1em}
header,footer{color:#666;font-size:.85em}header{border-bottom:1px solid #ddd;margin-bottom:1em}footer{border-top:1px solid #ddd;margin-top:2em;padding-top:.5em}
nav.toc{background:#f7f9fc;border:1px solid #e3e8ef;padding:.5em 1.2em;margin:1em 0}nav.toc ul{margin:.1em 0}nav.toc{font-size:.82em;line-height:1.3}
@media print{body{max-width:none;margin:0}h2{page-break-before:always;page-break-after:avoid}h3{page-break-after:avoid}img{page-break-inside:avoid}tr{page-break-inside:avoid}img{max-height:240mm;width:auto;max-width:100%}}"""
mk = markdown.Markdown(extensions=["tables", "toc"], extension_configs={"toc": {"toc_depth": "2-3"}})
body = mk.convert(md)
body = re.sub(r'src="(manual-v2/img/[^"]+)"', lambda m: 'src="data:image/png;base64,' + base64.b64encode(open(m.group(1), "rb").read()).decode() + '"', body)
toc = '<nav class="toc"><strong>Contenido</strong>' + mk.toc.replace('<div class="toc">', "").replace("</div>", "") + "</nav>"
body = body.replace("<h2", toc + "<h2", 1)
h = (f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
     f'<title>Manual de uso por pantalla · PMS Hotelero Suite v2</title><style>{css}</style></head><body>'
     f'<header>{MARCA} · PMS Hotelero Piloto · Suite v2</header>{body}<footer>{MARCA} · datos ficticios</footer></body></html>')
open(N + ".html", "w", encoding="utf-8").write(h)
subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={os.path.abspath(N + '.pdf')}", "file://" + os.path.abspath(N + ".html")],
               check=True, capture_output=True, timeout=180)

# ---------- DOCX ----------
AZUL = RGBColor(0x1F, 0x3A, 0x5F)
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
sec.left_margin = sec.right_margin = Cm(2); sec.top_margin = sec.bottom_margin = Cm(2)
ANCHO = Cm(17)
st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
for nombre, tam in (("Title", 22), ("Heading 1", 16), ("Heading 2", 13)):
    s = doc.styles[nombre]; s.font.name = "Calibri"; s.font.color.rgb = AZUL; s.font.size = Pt(tam)

def campo(par, instr):
    r = par.add_run(); r.font.size = Pt(8.5); r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    for tag, txt in (("begin", None), (None, instr), ("separate", None), ("end", None)):
        if tag:
            e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), tag)
        else:
            e = OxmlElement("w:instrText"); e.set(qn("xml:space"), "preserve"); e.text = txt
        r._r.append(e)

hp = sec.header.paragraphs[0]; hp.text = MARCA + " · PMS Hotelero Suite v2"
hp.runs[0].font.size = Pt(8.5); hp.runs[0].font.color.rgb = RGBColor(0x66, 0x66, 0x66)
fp = sec.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = fp.add_run(MARCA + " · datos ficticios · página "); r.font.size = Pt(8.5); r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
campo(fp, "PAGE")

def sombrear(celda, color):
    tcPr = celda._tc.get_or_add_tcPr(); s = OxmlElement("w:shd")
    s.set(qn("w:val"), "clear"); s.set(qn("w:color"), "auto"); s.set(qn("w:fill"), color); tcPr.append(s)

def runs(par, texto, tam=None):
    for i, trozo in enumerate(re.split(r"\*\*", texto)):
        if not trozo: continue
        trozo = re.sub(r"`([^`]+)`", r"\1", trozo)
        rr = par.add_run(trozo); rr.bold = (i % 2 == 1)
        if tam: rr.font.size = Pt(tam)

lineas = md.split("\n"); i = 0; primero = True
while i < len(lineas):
    l = lineas[i]
    if not l.strip(): i += 1; continue
    if l.startswith("# "):
        doc.add_heading(l[2:], 0); i += 1; continue
    if l.startswith("## "):
        if not primero: doc.add_page_break()
        primero = False
        doc.add_heading(l[3:], 1); i += 1; continue
    if l.startswith("### "):
        doc.add_heading(l[4:], 2); i += 1; continue
    m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", l.strip())
    if m:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        from PIL import Image
        w, hh = Image.open(m.group(2)).size
        alto_max = Cm(19)
        if ANCHO * hh / w > alto_max:
            p.add_run().add_picture(m.group(2), height=alto_max)
        else:
            p.add_run().add_picture(m.group(2), width=ANCHO)
        c = doc.add_paragraph(); c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rc = c.add_run("Figura: " + m.group(1)); rc.italic = True; rc.font.size = Pt(9); rc.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
        i += 1; continue
    if l.startswith("|"):
        filas = []
        while i < len(lineas) and lineas[i].startswith("|"):
            if not re.match(r"^\|[\s\-|:]+\|$", lineas[i]):
                filas.append([x.strip() for x in lineas[i].strip().strip("|").split(" | ")])
            i += 1
        nc = len(filas[0]); t = doc.add_table(rows=0, cols=nc); t.style = "Table Grid"
        for k, f in enumerate(filas):
            cel = t.add_row().cells
            for j in range(nc):
                p = cel[j].paragraphs[0]; runs(p, f[j] if j < len(f) else "", 9.5)
                if k == 0:
                    for rr in p.runs: rr.bold = True
                    sombrear(cel[j], "EEF2F7")
        if nc == 3 and filas[0][0] == "N.º":
            anchos = [1.1, 4.2, 11.7]
        elif nc == 2:
            anchos = [5.5, 11.5]
        else:
            anchos = [17 / nc] * nc
        t.autofit = False
        grid = t._tbl.tblGrid.findall(qn("w:gridCol"))
        for j, g in enumerate(grid): g.set(qn("w:w"), str(int(Cm(anchos[j]).twips)))
        for row in t.rows:
            for j, ce in enumerate(row.cells): ce.width = Cm(anchos[j])
        doc.add_paragraph()
        continue
    if l.startswith(">"):
        txt = []
        while i < len(lineas) and lineas[i].startswith(">"):
            txt.append(lineas[i].lstrip("> ").strip()); i += 1
        t = doc.add_table(rows=1, cols=1); t.style = "Table Grid"; c = t.rows[0].cells[0]; sombrear(c, "FFFBEA")
        runs(c.paragraphs[0], " ".join(txt)); doc.add_paragraph(); continue
    if re.match(r"^\s*[-*] ", l):
        p = doc.add_paragraph(style="List Bullet"); runs(p, re.sub(r"^\s*[-*] ", "", l)); i += 1; continue
    if re.match(r"^\s*\d+\. ", l):
        p = doc.add_paragraph(style="List Number"); runs(p, re.sub(r"^\s*\d+\. ", "", l)); i += 1; continue
    # párrafo (une líneas contiguas)
    par = [l.strip()]; i += 1
    while i < len(lineas) and lineas[i].strip() and not re.match(r"^(#|\||>|!\[|\s*[-*] |\s*\d+\. )", lineas[i]):
        par.append(lineas[i].strip()); i += 1
    if len(par) > 1 and all(x.startswith("**") for x in par):
        for x in par: runs(doc.add_paragraph(), x)
    else:
        runs(doc.add_paragraph(), " ".join(par))
doc.core_properties.title = "Manual de uso por pantalla · PMS Hotelero Suite v2"
doc.core_properties.author = "ATm Consulting (prototipo)"
doc.save(N + ".docx")
print("ok", *(f"{e}:{os.path.getsize(N + '.' + e)//1024}KB" for e in ("md", "html", "pdf", "docx")))

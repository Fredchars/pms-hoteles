"""Genera HTML autocontenido y PDF de los 4 informes. Prototipo diseñado para ATm Consulting."""
import json,re,base64,subprocess,markdown,os
S=json.load(open("img/esquema.json"));T,FK=S["T"],S["FK"]
d=[]
for t,cols in T.items():
    d.append(f"### {t}\n\n| Columna | Tipo | Llave |\n|---|---|---|")
    d+= [f"| `{n}` | {ty} | {k} |" for n,ty,k in cols]; d.append("")
r=["| Tabla | Columna | Referencia a | Cardinalidad |","|---|---|---|---|"]
uniq={("pms_estancias","reserva_id"),("pms_reservas_web","reserva_id")}
r+=[f"| {t} | `{c}` | {x}(id) | {'1 a 1' if (t,c) in uniq else 'N a 1'} |" for t,c,x in FK]
r.append("\nON DELETE: no se definió acción (restringe el borrado de filas referenciadas).")
src=open("anexo-modelo-datos-pms.src.md").read() if os.path.exists("anexo-modelo-datos-pms.src.md") else open("anexo-modelo-datos-pms.md").read()
open("anexo-modelo-datos-pms.src.md","w").write(src)
open("anexo-modelo-datos-pms.md","w").write(src.replace("{{DICCIONARIO}}","\n".join(d)).replace("{{RELACIONES}}","\n".join(r)))
css="""body{font-family:Calibri,Arial,sans-serif;max-width:960px;margin:2em auto;padding:0 1em;background:#fff;color:#222;line-height:1.5}
table{border-collapse:collapse;width:100%;margin:1em 0}th,td{border:1px solid #bbb;padding:5px 8px;vertical-align:top;font-size:.9em}th{background:#eef2f7}
img{max-width:100%;height:auto;border:1px solid #e3e8ef;margin:.5em 0}h1,h2,h3{color:#1f3a5f}h2{border-bottom:2px solid #1f3a5f;padding-bottom:.2em}
pre{background:#f6f8fa;padding:.8em;overflow-x:auto;font-size:.85em}code{background:#f6f8fa;padding:0 .2em}blockquote{border-left:4px solid #e0a800;background:#fffbea;margin:1em 0;padding:.4em 1em}
header,footer{color:#666;font-size:.85em}header{border-bottom:1px solid #ddd;margin-bottom:1em}footer{border-top:1px solid #ddd;margin-top:2em;padding-top:.5em}
@media print{body{max-width:none;margin:0}h2{page-break-after:avoid}img{page-break-inside:avoid}}"""
for n in ["especificaciones-tecnicas-pms","manual-uso-pms","continuidad-respaldo-pms","anexo-modelo-datos-pms"]:
    md=open(n+".md").read()
    body=markdown.markdown(md,extensions=["tables","fenced_code","toc"])
    body=re.sub(r'src="(img[^"/]*/[^"]+)"',lambda m:'src="data:image/png;base64,'+base64.b64encode(open(m.group(1),"rb").read()).decode()+'"',body)
    title=re.search(r"^# (.+)$",md,re.M).group(1)
    h=f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{css}</style></head><body><header>Prototipo diseñado para ATm Consulting · PMS Hotelero Piloto</header>{body}<footer>Prototipo diseñado para ATm Consulting · datos ficticios</footer></body></html>'
    open(n+".html","w").write(h)
    subprocess.run(["google-chrome","--headless=new","--no-sandbox","--disable-gpu","--no-pdf-header-footer",f"--print-to-pdf={os.path.abspath(n+'.pdf')}","file://"+os.path.abspath(n+".html")],check=True,capture_output=True,timeout=120)
    print(n,os.path.getsize(n+".html"),os.path.getsize(n+".pdf"))

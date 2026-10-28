import mammoth, base64, re, os
from markdownify import markdownify as md
src="diseno-piloto-pms.docx"
with open(src,"rb") as f:
    r=mammoth.convert_to_html(f)
body=r.value
css="""body{font-family:Calibri,Arial,sans-serif;max-width:900px;margin:2em auto;padding:0 1em;background:#fff;color:#222;line-height:1.5}
table{border-collapse:collapse;width:100%;margin:1em 0}th,td{border:1px solid #bbb;padding:6px 8px;vertical-align:top;font-size:.92em}th{background:#eef2f7}
img{max-width:100%;height:auto}h1,h2,h3{color:#1f3a5f}header{color:#666;font-size:.85em;border-bottom:1px solid #ddd;margin-bottom:1em}"""
html=f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Documento de diseño del piloto PMS</title><style>{css}</style></head><body><header>Prototipo diseñado para ATm Consulting</header>{body}</body></html>'
open("diseno-piloto-pms.html","w",encoding="utf-8").write(html)
# markdown with external images
os.makedirs("img",exist_ok=True)
n=[0]
def sub(m):
    n[0]+=1
    ext=m.group(1); data=base64.b64decode(m.group(2))
    p=f"img/imagen-{n[0]:02d}.{ext}"
    open(p,"wb").write(data); return f'src="{p}"'
h2=re.sub(r'src="data:image/(\w+);base64,([^"]+)"',sub,body)
text=md(h2,heading_style="ATX")
text=re.sub(r'\n{3,}','\n\n',text)
open("diseno-piloto-pms.md","w",encoding="utf-8").write("*Prototipo diseñado para ATm Consulting*\n\n"+text)
print(n[0],[m.message for m in r.messages][:5])

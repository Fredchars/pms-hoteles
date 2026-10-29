"""Diagramas ER del PMS (estilo por dominio) con Graphviz (wasm vía node). Prototipo diseñado para ATm Consulting."""
import re,subprocess,os,html,cairosvg,json
OUT="img-er"; GV="/workspace/gv/dot.mjs"
sql=open("../../db/01_esquema_pms.sql").read()
T={};FK=[];UK={}
for m in re.finditer(r"create table if not exists (\w+) \((.*?)\n\);",sql,re.S):
    t=m.group(1);cols=[];UK[t]=set()
    for l in m.group(2).split("\n"):
        l=l.split("--")[0].strip()
        u=re.match(r"unique \(([^)]*)\)",l)
        if u:
            ks=[x.strip() for x in u.group(1).split(",")]
            if len(ks)==1: UK[t].add(ks[0])
            else: UK[t].add(tuple(ks))
            continue
        c=re.match(r"(\w+) (\w+(?:\(\d+(?:,\d+)?\))?)",l)
        if not c or c.group(1) in("check","primary"): continue
        n=c.group(1); r=re.search(r"references (\w+)",l)
        cols.append(dict(n=n,ty=c.group(2),pk="primary key" in l,fk=bool(r),uk=" unique" in l,nn="not null" in l or "primary key" in l))
        if r: FK.append((t,n,r.group(1)))
    T[t]=cols
T["pms_habitaciones"].append(dict(n="vista_mar",ty="boolean",pk=0,fk=0,uk=0,nn=1))
T["pms_reservas"].append(dict(n="opcion_vence_en",ty="timestamptz",pk=0,fk=0,uk=0,nn=0))
for t,s in UK.items():
    for k in s:
        for c in T[t]:
            if (isinstance(k,str) and c["n"]==k): c["uk"]=True
            elif isinstance(k,tuple) and c["n"] in k: c.setdefault("ukc",True)
D=[("Organización y acceso","#1f5fa8","#eaf1fb",["pms_hoteles","pms_usuarios","pms_impuestos"]),
   ("Catálogos y tarifas","#2e7d32","#edf6ee",["pms_tipos_habitacion","pms_tarifas"]),
   ("Inventario y plano","#0f766e","#e8f5f3",["pms_habitaciones","pms_camas","pms_bloqueos","pms_housekeeping"]),
   ("Reservas (núcleo)","#b45309","#fdf3e7",["pms_huespedes","pms_consentimientos","pms_reservas","pms_reserva_noches","pms_estancias"]),
   ("Facturación y pagos","#6d28d9","#f3eefc",["pms_cargos","pms_pagos"]),
   ("Reserva web","#be185d","#fcecf3",["pms_reservas_web","pms_pagos_pasarela","pms_eventos_pasarela","pms_correos"]),
   ("Auditoría","#b91c1c","#fbeaea",["pms_auditoria"])]
DOM={t:d for d in D for t in d[3]}
assert set(DOM)==set(T),set(T)-set(DOM)
def col(t,n): return next(c for c in T[t] if c["n"]==n)
def card(t,n):
    c=col(t,n); one="1" if c["nn"] else "0..1"; many="0..1" if c["uk"] else "0..N"; return one,many
def render(name,dot):
    p=f"{OUT}/{name}.dot";open(p,"w").write(dot);subprocess.run(["node",GV,p],check=True)
    cairosvg.svg2png(url=p[:-4]+".svg",write_to=f"{OUT}/{name}.png",scale=2.0,background_color="white");os.remove(p)
FONT='fontname="Helvetica"'
def tag(c):
    s=[]
    if c["pk"]:s.append('<font color="#b45309"><b>PK</b></font>')
    if c["fk"]:s.append('<font color="#1f5fa8"><b>FK</b></font>')
    if c["uk"]:s.append('<font color="#7c3aed"><b>UK</b></font>')
    return " ".join(s)
def tabla(t,full,dark,light):
    cols=T[t] if full else [c for c in T[t] if c["pk"] or c["fk"] or c["uk"]]
    rest=len(T[t])-len(cols)
    h=f'<table border="0" cellborder="1" cellspacing="0" cellpadding="4" color="{dark}">'
    h+=f'<tr><td colspan="3" bgcolor="{dark}" align="left"><font color="white" point-size="13"><b>{t}</b></font><font color="white" point-size="9">  ·  {len(T[t])} cols</font></td></tr>'
    for c in cols:
        bg=light if c["pk"] else "white"
        h+=f'<tr><td bgcolor="{bg}" align="left">{tag(c)}</td><td bgcolor="{bg}" align="left" port="{c["n"]}"><b>{c["n"]}</b></td><td bgcolor="{bg}" align="left"><font color="#475569">{c["ty"]}{"" if c["nn"] or c["pk"] else " ?"}</font></td></tr>'
    if rest: h+=f'<tr><td colspan="3" bgcolor="{light}"><font color="#64748b" point-size="9">+ {rest} cols (diccionario §4)</font></td></tr>'
    return h+"</table>"
def edge(t,n,r,color,w=1.2,style="solid"):
    one,many=card(t,n)
    tail="teeodot" if many=="0..1" else "crowodot"
    head="teetee" if one=="1" else "teeodot"
    return f'"{t}":"{n}" -> "{r}":"id" [dir=both arrowtail={tail} arrowhead={head} color="{color}" penwidth={w} style={style} headlabel="{one}" taillabel="{many}" fontsize=9 fontcolor="#334155"];\n'
# 1 vista general
g=f'digraph G{{graph[{FONT} label=<<b>PMS Hotelero · Vista general por dominio</b>> labelloc=t fontsize=22 bgcolor=white rankdir=TB nodesep=0.6 ranksep=0.9 pad=0.4];node[{FONT} shape=plaintext];edge[{FONT} color="#334155" fontsize=10 penwidth=1.4];\n'
for i,(n,dk,lt,ts) in enumerate(D):
    rows="".join(f'<tr><td align="left" bgcolor="white"><b>{t}</b></td><td bgcolor="white"><font color="#64748b" point-size="9">{len(T[t])} cols</font></td></tr>' for t in ts)
    g+=f'd{i}[label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="5" color="{dk}"><tr><td colspan="2" bgcolor="{dk}"><font color="white" point-size="13"><b>{n}</b></font></td></tr>{rows}</table>>];\n'
agg={}
for t,n,r in FK:
    a,b=DOM[r][0],DOM[t][0]
    if a!=b: agg.setdefault((a,b),set()).add(n)
idx={d[0]:i for i,d in enumerate(D)}
for (a,b),ns in agg.items(): g+=f'd{idx[a]}->d{idx[b]}[label="{" · ".join(sorted(ns))}"];\n'
g+=f'd{idx["Reservas (núcleo)"]}->d{idx["Auditoría"]}[style=dashed color="#b91c1c" label="toda acción importante\\n(sin FK, solo agregar)"];\n'
render("01-vista-general-dominios",g+"}")
# 2 ER completo
g=f'digraph G{{graph[{FONT} label=<<b>PMS Hotelero · Modelo de datos completo (21 tablas pms_*, db/01_esquema_pms.sql)</b>> labelloc=t fontsize=24 bgcolor=white rankdir=TB newrank=true nodesep=0.3 ranksep=1.0 pad=0.4 splines=true];node[{FONT} shape=plaintext fontsize=10];edge[{FONT} arrowsize=0.8];\n'
for i,(n,dk,lt,ts) in enumerate(D):
    g+=f'subgraph cluster_{i}{{label=<<b>{n}</b>> fontcolor="{dk}" fontsize=16 color="{dk}" penwidth=2 style="rounded,filled" fillcolor="{lt}";\n'
    for t in ts: g+=f'"{t}"[label=<{tabla(t,True,dk,lt)}>];\n'
    g+="}\n"
for t,n,r in FK:
    w,st=(0.6,"dashed") if r in("pms_hoteles","pms_usuarios") else (1.4,"solid")
    g+=edge(t,n,r,DOM[t][1],w,st)
leg='<table border="0" cellborder="0" cellspacing="2"><tr><td colspan="2"><b>Leyenda</b></td></tr>'+"".join(f'<tr><td bgcolor="{d[1]}" width="24"> </td><td align="left">{d[0]}</td></tr>' for d in D)+'<tr><td colspan="2" align="left"><font point-size="9">PK llave primaria · FK foránea · UK única · ? = admite nulos<br/>Pata de gallo = muchos · barra = uno · círculo = opcional<br/>Líneas punteadas: hotel_id y columnas de usuario (quién creó/aprobó)</font></td></tr></table>'
g+=f'leyenda[label=<{leg}>];\n'
render("02-er-completo",g+"}")
# 3 por dominio
for i,(n,dk,lt,ts) in enumerate(D):
    g=f'digraph G{{graph[{FONT} label=<<b>Dominio: {n}</b><br/><font point-size="12" color="#64748b">PK / FK / UK y relaciones internas · columnas restantes en §4 · FK externas en el recuadro</font>> labelloc=t fontsize=22 bgcolor=white rankdir=LR nodesep=0.6 ranksep=1.2 pad=0.4];node[{FONT} shape=plaintext fontsize=11];edge[{FONT}];\n'
    g+=f'subgraph cluster_0{{label="" color="{dk}" penwidth=2.5 style="rounded,filled" fillcolor="{lt}";\n'
    for t in ts: g+=f'"{t}"[label=<{tabla(t,False,dk,lt)}>];\n'
    g+="}\n"
    ext=[]
    for t,c,r in FK:
        if t in ts and r in ts: g+=edge(t,c,r,dk,1.6)
        elif t in ts or r in ts:
            one,many=card(t,c); ext.append(f'{r}.id → {t}.{c}   <b>{one} : {many}</b>')
    if ext:
        rows="".join(f'<tr><td align="left">{e}</td></tr>' for e in ext)
        g+=f'ext[label=<<table border="1" cellborder="0" cellspacing="2" cellpadding="3" color="#cbd5e1"><tr><td align="left"><font point-size="14"><b>FK hacia / desde otros dominios</b></font></td></tr>{rows}</table>>];\n'
    slug=re.sub(r"[^a-z]+","-",n.lower().translate(str.maketrans("áéíóú","aeiou"))).strip("-")
    render(f"03-dominio-{i+1}-{slug}",g+"}")
# 4 ciclo de vida
S={"consulta":("#eaf1fb","#1f5fa8","reservas (sin noches) · auditoria"),
"opcion":("#fdf3e7","#b45309","reservas.opcion_vence_en · reserva_noches (activa)\\ncargos (noche) · huespedes · consentimientos"),
"confirmada":("#fdf3e7","#b45309","reserva_noches · cargos · pagos · correos"),
"alojado":("#e8f5f3","#0f766e","estancias (checkin_real) · cargos (extras) · pagos"),
"salida":("#edf6ee","#2e7d32","estancias (checkout_real) · habitaciones.estado_limpieza='sucia'\\nhousekeeping"),
"cancelada":("#fbeaea","#b91c1c","reserva_noches.activa=false · cargos.anulado\\ncancelacion_* (aprobación de gerencia)"),
"no_show":("#fbeaea","#b91c1c","reserva_noches.activa=false"),
"web_bloqueada":("#fcecf3","#be185d","reservas_web (vence_en 15 min) · reservas en opcion"),
"web_pago":("#fcecf3","#be185d","pagos_pasarela (aprobada) · eventos_pasarela\\npagos (metodo pasarela)")}
lab={"web_bloqueada":"WEB: BLOQUEADA → PAGO_PENDIENTE","web_pago":"WEB: PAGADA"}
g=f'digraph G{{graph[{FONT} label=<<b>Ciclo de vida de una reserva · estados y tablas que se tocan</b>> labelloc=t fontsize=22 bgcolor=white nodesep=0.5 ranksep=0.6 pad=0.4];node[{FONT} shape=box style="rounded,filled" fontsize=10];edge[{FONT} fontsize=10 color="#475569"];\n'
for k,(f,c,d) in S.items():
    g+=f'"{k}"[fillcolor="{f}" color="{c}" label=<<b><font point-size="13">{lab.get(k,k.upper())}</font></b><br/>{html.escape(d).replace(chr(92)+"n","<br/>")}>];\n'
g+='''consulta->opcion[label="aparta (48 h)"];consulta->confirmada[label="confirma"];opcion->confirmada[label="confirma / pago"];
confirmada->alojado[label="check-in"];alojado->salida[label="check-out"];
opcion->cancelada[label="vence opcion_vence_en\\n(liberar vencidos, 5 min)" style=dashed];confirmada->cancelada[label="cancelación aprobada" style=dashed];
confirmada->no_show[label="no llegó" style=dashed];
web_bloqueada->web_pago[label="pago aprobado\\n(firma HMAC, idempotente)"];web_pago->confirmada[label="reserva confirmada\\n+ correo PMS-AAAA-XXXXXX"];
web_bloqueada->cancelada[label="expirada / fallida" style=dashed];
{rank=same;consulta;web_bloqueada}
}'''
render("04-ciclo-vida-reserva",g)
json.dump({"D":[(d[0],d[3]) for d in D]},open(f"{OUT}/dominios.json","w"),ensure_ascii=False)
print(sorted(os.listdir(OUT)))

import re, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sql=open("../../db/01_esquema_pms.sql").read()
T={}; FK=[]
for m in re.finditer(r"create table if not exists (\w+) \((.*?)\n\);",sql,re.S):
    t=m.group(1); cols=[]
    for l in m.group(2).split("\n"):
        l=l.strip()
        c=re.match(r"(\w+) (\w+)",l)
        if not c or c.group(1) in("unique","check","primary"): continue
        r=re.search(r"references (\w+)",l)
        cols.append((c.group(1),c.group(2),"PK" if "primary key" in l else ("FK" if r else "")))
        if r: FK.append((t,c.group(1),r.group(1)))
    T[t]=cols
# extra cols from alter
T["pms_habitaciones"].append(("vista_mar","boolean",""));T["pms_reservas"].append(("opcion_vence_en","timestamptz",""))
import json; json.dump({"T":T,"FK":FK},open("img/esquema.json","w"))
pos={ # x,y grid
"pms_hoteles":(0,0),"pms_impuestos":(0,1),"pms_usuarios":(0,2),"pms_auditoria":(0,3),
"pms_tipos_habitacion":(1,0),"pms_habitaciones":(1,1),"pms_camas":(1,2),"pms_tarifas":(1,3),
"pms_huespedes":(2,0),"pms_consentimientos":(2,1),"pms_reservas":(2,2),"pms_reserva_noches":(2,3),
"pms_estancias":(3,0),"pms_housekeeping":(3,1),"pms_bloqueos":(3,2),"pms_cargos":(3,3),
"pms_pagos":(4,0),"pms_reservas_web":(4,1),"pms_pagos_pasarela":(4,2),"pms_eventos_pasarela":(4,3),"pms_correos":(5,0)}
def draw(full,fn):
    W,H=5.2,(9.5 if full else 2.2)
    fig,ax=plt.subplots(figsize=(6*W,4*H/1.6 if full else 4*H*1.4)); ax.axis("off")
    box={}
    for t,(cx,ry) in pos.items():
        cols=T[t] if full else [c for c in T[t] if c[2]]
        x=cx*W; y=-ry*H; h=0.35*(len(cols)+1)
        ax.add_patch(plt.Rectangle((x,y-h),W*0.85,h,fc="white",ec="#1f3a5f",lw=1.5))
        ax.add_patch(plt.Rectangle((x,y-0.35),W*0.85,0.35,fc="#1f3a5f"))
        ax.text(x+0.1,y-0.18,t,color="white",va="center",fontsize=10,weight="bold")
        for i,(n,ty,k) in enumerate(cols):
            ax.text(x+0.1,y-0.35*(i+1)-0.18,f"{('🔑' if 0 else k):<2} {n}"+(f"  : {ty}" if full else ""),va="center",fontsize=8,color="#b03a2e" if k=="FK" else "#222",family="monospace")
        box[t]=(x,y,h)
    for t,c,r in FK:
        if t==r or r in ("pms_hoteles","pms_usuarios"): continue
        x1,y1,h1=box[t];x2,y2,h2=box[r]
        ax.annotate("",xy=(x2+W*0.85/2,y2-0.2),xytext=(x1+W*0.85/2,y1-0.2),arrowprops=dict(arrowstyle="->",color="#7a8ca3",alpha=.8,lw=1.3,connectionstyle="arc3,rad=.15"))
    ax.set_xlim(-0.3,6*W);ax.set_ylim(-4*H-1,0.5);fig.tight_layout();fig.savefig(fn,dpi=150,facecolor="white");plt.close(fig)
draw(False,"img/er-simplificado.png"); draw(True,"img/er-completo.png")
# domain overview
fig,ax=plt.subplots(figsize=(12,5));ax.axis("off")
dom=[("Organización y acceso","hoteles · usuarios · impuestos · auditoría",(0,1)),("Inventario","tipos_habitacion · habitaciones · camas · tarifas · bloqueos",(1,1)),
("Huéspedes y datos","huespedes · consentimientos (Ley 1581)",(2,1)),("Reserva (núcleo)","reservas · reserva_noches (sin doble venta) · estancias",(1,0)),
("Cuenta","cargos · pagos",(2,0)),("Operación","housekeeping",(0,0)),("Reserva web","reservas_web · pagos_pasarela · eventos_pasarela · correos",(3,0.5))]
for n,d,(x,y) in dom:
    ax.add_patch(plt.Rectangle((x*3,y*2),2.7,1.5,fc="#eef4fb",ec="#1f3a5f",lw=1.5));ax.text(x*3+1.35,y*2+1.05,n,ha="center",weight="bold",color="#1f3a5f");ax.text(x*3+1.35,y*2+.5,d.replace(" · ","\n",1),ha="center",fontsize=8)
ax.set_xlim(-.2,12);ax.set_ylim(-.3,3.7);fig.savefig("img/dominios.png",dpi=110,facecolor="white",bbox_inches="tight")
print(len(T),len(FK))

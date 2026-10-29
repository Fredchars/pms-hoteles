"""Genera las infografías del PMS reutilizando el estilo (CSS + fuentes Plex) de las referencias."""
import base64, re, io, sys
from pathlib import Path
from PIL import Image
A = Path("/home/box/agent-data/agents/bfdd8248-16c2-457a-ac5d-5c93219dab09/attachments")
REF = {"arq": A/"c5f5baac920dedd4b71fc2c512175acd9ace4b194974c33953f6124e3917bad6.html",
       "uso": A/"20537da6f4d40809abf8122f433139e20bfbf8c53536fc91aa7313787dcca76f.html"}
CAP = Path(__file__).resolve().parents[1]/"capturas"
def head(k, titulo):
    h = REF[k].read_text().split("</head>")[0] + "</head>"
    h = re.sub(r"<title>.*?</title>", f"<title>{titulo}</title>", h)
    h = h.replace("--bg:#f4f6f9", "--bg:#ffffff")
    return h
def img(n, w=640):
    im = Image.open(CAP/n).convert("RGB"); im.thumbnail((w, 2000))
    b = io.BytesIO(); im.save(b, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
HDR = lambda kick, h1, sub, meta: f'<header><div><div class="kick">{kick}</div><h1>{h1}</h1><div class="sub">{sub}</div></div><div class="meta">{meta}</div></header>'
META = 'Fuente verificada: <b>Fredchars/pms-hoteles</b> (rama main)<br>pms-hoteles-atm · pms-reservas-atm (Streamlit) · Supabase<br>Revisión: 29-oct-2026 · datos ficticios'
KICK = "PMS Hoteles · Piloto multi-hotel y multimoneda"
FOOT = lambda izq: f'<div class="foot"><span>{izq}</span><span class="pw">Prototipo diseñado para <b>ATm Consulting</b></span></div>'
def li(xs): return "".join(f"<li>{x}</li>" for x in xs)
def chips(cs): return "".join(f'<div class="chip th"><img src="{img(c[0],420)}"><i>{c[1]}</i></div>' if len(c)==2 and c[0].endswith(".png") else f'<div class="chip"><b>{c[0]}</b>{c[1]}</div>' for c in cs)

# ---------------- Arquitectura ----------------
act = [("RE","Recepción","Reservas, plano, check-in/out, cobros"),("GE","Gerencia","Todo + tarifas, reportes, aprobaciones"),
       ("HK","Housekeeping","Estado de limpieza; ve bloqueos"),("AD","Administrador","Configuración, usuarios, tarifas, bloqueos"),
       ("CW","Cliente web","Sin cuenta: busca, bloquea y paga")]
pasos = [("Buscar disponibilidad","Plano o calendario: fechas, adultos, niños, tipo, vista al mar"),
 ("Bloquear / opción","Web: bloqueo 15 min · PMS: opción 48 h; noches apartadas"),
 ("Datos y consentimiento","Huésped + autorización de datos (Ley 1581)"),
 ("Pago","Pasarela simulada con evento firmado (HMAC); valida monto y moneda"),
 ("Confirmar","Número de reserva + correo de confirmación (simulado)"),
 ("Check-in / estancia","Recepción asigna y registra la llegada; cargos"),
 ("Check-out y factura","Cargos, pagos e impuestos configurables por país"),
 ("Housekeeping","La habitación pasa a sucia → limpia → disponible")]
izq = '<div class="izq"><div class="card"><h3>Actores (4 roles + cliente)</h3>' + "".join(
  f'<div class="act"><div class="av">{a}</div><div><b>{b}</b><span>{c}</span></div></div>' for a,b,c in act) + \
  '<div style="font-size:12px;color:var(--mut);margin-top:6px">19 usuarios de prueba; cada uno limitado a su hotel o a todos.</div></div><div class="card"><h3>Flujo de una reserva</h3>' + "".join(
  f'<div class="paso"><div class="n">{i}</div><div><b>{b}</b><span>{c}</span></div></div>' for i,(b,c) in enumerate(pasos,1)) + "</div></div>"
capas = [
 ("#e4e9ef","#2f4255","#24333f","01","Presentación","Streamlit 1.66 · Python 3.13",
  [("plano_planta.png","Plano de habitaciones"),("calendario.png","Calendario"),("web_02_plano.png","Reserva web"),("13 + 1 pantallas","menú por rol con <code>st.navigation</code>")],
  "Presentación","app/Inicio.py · app/paginas/*.py · reserva_web/Reservas.py",
  ["<b>PMS interno</b> (13 pantallas): Dashboard, Calendario, Plano, Reservas, Reservas web, Huéspedes, Housekeeping, Bloqueos, Tarifas, Facturación, Reportes, Configuración, Auditoría.",
   "<b>Mini web pública</b> (pms-reservas-atm): selector de hotel, plano por planta, datos, pago y confirmación.",
   "Ingreso con correo y contraseña (bcrypt); primer ingreso obliga a crear contraseña propia (≥ 10 caracteres).",
   "Sesión con token firmado HMAC en la URL; caduca a las 8 h. Fondo blanco y marca ATm."]),
 ("#dde3ea","#3a5066","#2c3d4e","02","Aplicación y lógica de negocio","pms/*.py",
  [("Reservas y disponibilidad","noches únicas por habitación; sin doble venta"),("Tarifas e impuestos","por tipo y personas; impuestos genéricos por país"),
   ("Plano dibujado","<code>dibujo.py</code>: mar, pasillo, camas a escala"),("Reserva web","bloqueo, pago firmado, correo"),("Seguridad","permisos por rol, hotel y aprobaciones")],
  "Aplicación y lógica","pms/ · Python, sin API REST propia",
  ["<code>reservas.py</code> · <code>disponibilidad.py</code>: crear, modificar, check-in/out, cancelar; misma regla en PMS y web.",
   "<code>tarifas.py</code> · <code>facturacion.py</code>: precio por noche y personas, cargos, pagos, impuestos configurables; moneda local del hotel.",
   "<code>plano.py</code> · <code>dibujo.py</code>: estado por fechas (disponible, ocupada, opción, bloqueada, fuera de servicio).",
   "<code>reserva_web.py</code> · <code>pasarela.py</code> · <code>correo.py</code> · <code>vencimientos.py</code> (libera opciones y bloqueos vencidos).",
   "<code>seguridad.py</code>: matriz de permisos; gerencia aprueba y nunca lo que solicitó · <code>auditoria.py</code>."]),
 ("#d6dde6","#465d74","#36485a","03","Datos","PostgreSQL (Supabase Free)",
  [("21 tablas <code>pms_</code>","17 núcleo PMS + 4 reserva web"),("RLS activo","cada fila con <code>hotel_id</code>"),
   ("Sin doble venta","único (habitación + noche) en <code>pms_reserva_noches</code>"),("Auditoría","<code>pms_auditoria</code> con antes / después")],
  "Datos","db/01_esquema_pms.sql · db/02_rls_pms.sql",
  ["<b>21 tablas</b>: hoteles, impuestos, usuarios, tipos, habitaciones, camas, tarifas, huéspedes, consentimientos, reservas, reserva_noches, estancias, housekeeping, bloqueos, cargos, pagos, auditoría.",
   "Reserva web: <code>pms_reservas_web</code>, <code>pms_pagos_pasarela</code>, <code>pms_eventos_pasarela</code>, <code>pms_correos</code>.",
   "3 hoteles ficticios (Colombia COP, República Dominicana DOP, genérico); 18 habitaciones de prueba: 3 plantas × 6.",
   "Proyecto Supabase compartido; tablas con prefijo <code>pms_</code> y RLS activado."]),
 ("#dfe4ea","#56697d","#435364","04","Integraciones","pasarela · correo · respaldo",
  [("Pasarela","hoy: simulada con firma<br>fase 2: Wompi (CO)"),("Correo","hoy: simulado en <code>pms_correos</code><br>listo: Resend / Brevo"),
   ("Consentimiento","Ley 1581 · <code>pms_consentimientos</code>"),("Sin channel manager","fase posterior")],
  "Integraciones","pms/pasarela.py · pms/correo.py",
  ["Pasarela simulada: no cobra dinero; el PMS valida firma, monto y moneda antes de confirmar.",
   "Adaptador Wompi con verificación SHA-256 ya escrito; falta cuenta del hotel y receptor de webhooks.",
   "Correo real solo con proveedor configurado y lista blanca de destinatarios; si no, se simula y se muestra en pantalla.",
   "Sin facturación electrónica DIAN ni channel manager en el piloto (fases siguientes)."]),
 ("#e6eaee","#66778a","#4f5d6c","05","Operación","Streamlit Community Cloud · GitHub Actions",
  [("Liberar vencidos","cada 5 min: opciones y bloqueos web"),("Respaldo semanal","domingos 3:45 a. m. · cifrado GPG"),
   ("Pruebas CI","pytest · 133 pruebas"),("Preparar Supabase","manual: esquema, RLS, verificación")],
  "Operación",".github/workflows · scripts/",
  ["<code>liberar-vencidos.yml</code> cada 5 min · <code>verificar-reserva-web.yml</code> prueba la reserva web de punta a punta.",
   "<code>respaldo.yml</code>: volcado de las tablas <code>pms_</code> cifrado con GPG, como artefacto de GitHub.",
   "<code>pruebas.yml</code> en cada push · <code>supabase.yml</code>: crea esquema y verifica RLS.",
   "Dos apps públicas: pms-hoteles-atm (personal) y pms-reservas-atm (clientes); secretos solo en Streamlit."])]
filas = ""
for t,f,sd,num,nom,tec,cs,h4,em,lis in capas:
    filas += f'<div class="fila"><div class="slab" style="--t:{t};--f:{f};--sd:{sd}"><div class="top"></div><div class="side"></div><div class="chips">{chips(cs)}</div><div class="front"><span class="num">{num}</span>{nom}<span class="tec">{tec}</span></div></div><div class="card det" style="--f:{f}"><h4>{h4}<em>{em}</em></h4><ul class="b">{li(lis)}</ul></div></div>'
bajo = ('<div class="bajo"><div class="card prop"><h3>Fases siguientes · por construir <span class="tag">no está en el código</span></h3><ul class="b">' +
  li(["Pasarela real (Wompi en Colombia; Azul o CardNET en R. Dominicana) con cuenta a nombre de cada hotel.","Correo real con dominio del hotel.",
      "Facturación electrónica DIAN y normativa por país.","Channel manager (Booking, Expedia, Airbnb).","Datos reales de los hoteles y su layout.",
      "Plan pago privado (Streamlit / otro hosting) y Supabase Pro."]) +
  '</ul></div><div class="card"><h3>Controles que garantiza</h3><ul class="b">' +
  li(["Sin doble venta: restricción única habitación + noche.","Separación por hotel: <code>hotel_id</code> + RLS y filtro en la app.",
      "Permisos por rol y pantalla (ver / editar).","Auditoría con valor anterior y nuevo.","Pago confirmado solo con evento firmado y monto correcto.",
      "Contraseñas bcrypt; cambio obligatorio en el primer ingreso."]) + "</ul></div></div>")
arq = head("arq","Infografía · Arquitectura en capas · PMS Hoteles") + '<body><div class="page">' + \
  HDR(KICK,'Arquitectura en capas <small>vista explotada</small>','Componentes, actores y flujo del PMS hotelero y de la mini web de reservas, tal como están en el código.',META) + \
  f'<main>{izq}<div class="capas">{filas}</div></main>{bajo}' + FOOT("Capturas reales de la app con datos ficticios · Pagos y correos simulados en el piloto") + "</div></body></html>"
Path("arquitectura-capas-pms.html").write_text(arq)

# ---------------- Uso por actor ----------------
P = {"dashboard":"Dashboard del día","calendario":"Calendario","plano":"Plano de habitaciones","reservas":"Reservas","reservas_web":"Reservas web",
     "huespedes":"Huéspedes","housekeeping":"Housekeeping","bloqueos":"Bloqueos","tarifas":"Tarifas","facturacion":"Facturación",
     "reportes":"Reportes","configuracion":"Configuración","auditoria":"Auditoría"}
import ast; _s=(Path(__file__).resolve().parents[2]/"pms/seguridad.py").read_text(); PERMISOS=ast.literal_eval(_s[_s.index("{",_s.index("PERMISOS:")):_s.index("\n}",_s.index("PERMISOS:"))+2])
def menu(rol):
    out=[]
    for k,t in P.items():
        n = PERMISOS["reservas" if k=="reservas_web" else k].get(rol)
        if n: out.append(f'<span{" class=g" if n=="ver" else ""}>{t}{"" if n=="x" else " · ver"}</span>')
    return "".join(out)
acts = [("Recepción","Operación diaria del front desk","recepcion_reservas.png","Reservas",menu("recepcion"),
   ["Busca disponibilidad en el plano por planta y crea la reserva con los datos ya rellenados.","Gestiona opciones, check-in, check-out, cargos y pagos.","Revisa las reservas que llegan por la web y su estado de pago."]),
  ("Gerencia","Control del hotel · aprobaciones","reportes.png","Reportes",menu("gerencia"),
   ["Todo lo de recepción, más tarifas, bloqueos y housekeeping.","Aprueba solicitudes (nunca las que registró) y revisa reportes de ocupación e ingresos.","Consulta configuración y auditoría."]),
  ("Housekeeping","Limpieza y estado de habitaciones","housekeeping_rol.png","Housekeeping",menu("housekeeping"),
   ["Ve la lista de habitaciones por limpiar y cambia su estado.","Consulta los bloqueos y fuera de servicio.","No ve reservas, huéspedes ni dinero."]),
  ("Administrador","Configuración y usuarios","admin_configuracion.png","Configuración",menu("administrador"),
   ["Hoteles, moneda, impuestos, tipos, habitaciones, camas y vista al mar.","Usuarios y roles; genera contraseñas temporales que se muestran una sola vez.","Edita tarifas y bloqueos; el resto lo consulta sin modificar."])]
cards=""
for i,(n,s,cap,ct,men,lis) in enumerate(acts,1):
    cards += f'<div class="card ac"><div class="hd"><div class="n">{i}</div><div><b>{n}</b><span>{s}</span></div></div><div class="shot" style="height:200px"><img src="{img(cap)}"><i>Captura real · {ct}</i></div><div class="bd"><div class="lbl">Pantallas del menú</div><div class="pan">{men}</div><div class="lbl">Qué hace</div><ul class="b">{li(lis)}</ul></div></div>'
web = ('<div class="card ac" style="grid-column:1/-1;flex-direction:row"><div style="flex:0 0 330px;border-right:1px solid var(--line)"><div class="hd"><div class="n" style="background:var(--acc)">5</div><div><b>Cliente web</b><span>Sin cuenta · pms-reservas-atm.streamlit.app</span></div></div><div class="bd"><div class="lbl">Pantallas</div><div class="pan"><span>Buscar</span><span>Plano por planta</span><span>Datos y consentimiento</span><span>Pago (simulado)</span><span>Confirmación</span><span>Consultar mi reserva</span></div><ul class="b">'
  + li(["Elige hotel, fechas y huéspedes; escoge habitación en el plano.","Bloqueo de 15 min con temporizador mientras completa datos y paga.","Recibe número de reserva y correo (simulado)."]) + '</ul></div></div><div style="flex:1;display:grid;grid-template-columns:repeat(5,1fr);gap:8px;padding:10px">'
  + "".join(f'<div style="border:1px solid var(--line);border-radius:5px;overflow:hidden;position:relative;height:200px"><img src="{img(c,520)}" style="width:100%;height:100%;object-fit:cover;object-position:top left"><i style="position:absolute;right:4px;bottom:4px;font-style:normal;font-size:11px;background:rgba(30,41,59,.82);color:#fff;padding:1px 6px;border-radius:3px">{t}</i></div>' for c,t in
    [("web_02_plano.png","Plano"),("web_04_datos_con_temporizador.png","Datos + temporizador"),("web_07_pasarela_simulada.png","Pasarela simulada"),("web_08_confirmacion.png","Confirmación"),("web_09_correo_simulado.png","Correo simulado")])
  + '</div></div>')
flujo = "".join(f'<div class="st"><span class="k">0{i}</span><b>{b}</b><span>{c}</span></div>' for i,(b,c) in enumerate(
  [("Buscar","Recepción o cliente web · plano/calendario"),("Apartar","Opción 48 h o bloqueo web 15 min"),("Registrar huésped","Datos + consentimiento"),("Pagar","Caja o pasarela con evento firmado"),
   ("Confirmar","Número de reserva y correo"),("Check-in","Recepción registra llegada"),("Check-out","Cargos, pagos, impuestos"),("Limpiar","Housekeeping libera la habitación")],1))
abajo = (f'<div class="abajo"><div class="card"><h3>Flujo general de una reserva</h3><div class="flujo">{flujo}</div></div>'
  '<div class="card"><h3>Plano de habitaciones</h3><div class="trd"><div><h5>Lo que dibuja</h5><ul class="b">' + li(["Una planta a la vez (1, 2 y 3) con franja de mar y pasillo.","Camas a escala, m², tipología y precio si está libre.","Etiqueta VISTA MAR en x01 y x02."]) +
  '</ul></div><div><h5>Estados por fechas</h5><ul class="b">' + li(["Disponible · ocupada · en opción.","Bloqueada · fuera de servicio · seleccionada.","Sin capacidad suficiente: en gris."]) +
  '</ul></div></div><div class="cadena"><span>Filtrar</span><em>→</em><span>Elegir habitación</span><em>→</em><span>Ver detalle y precio</span><em>→</em><span>Continuar con la reserva</span></div></div>'
  '<div class="card"><h3>Controles que garantiza</h3><ul class="b">' + li(["Menú y permisos por rol (editar o solo ver).","Un usuario solo trabaja en su hotel asignado.","Misma disponibilidad en PMS y web: sin doble venta.","Gerencia aprueba, nunca lo que ella misma solicitó.","Auditoría de cambios con antes y después.","Opciones y bloqueos vencidos se liberan cada 5 min."]) + '</ul></div></div>')
lim = ('<div class="lim"><div class="card prop"><h3>Fases siguientes</h3><p>Pasarela y correo reales · facturación electrónica DIAN · channel manager · datos y layout reales de los hoteles · app privada en plan de pago.</p></div>'
  '<div class="card"><h3>Límites del piloto</h3><p>Datos ficticios · pagos y correos simulados · impuestos genéricos por país · la app se duerme sin tráfico (Streamlit gratuito).</p></div></div>')
uso = head("uso","Infografía · Uso de pantallas por actor · PMS Hoteles") + "<style>.grid{grid-template-columns:repeat(4,1fr)}</style>" + '<body><div class="page">' + \
  HDR(KICK,"Uso de las pantallas por actor","Qué pantallas ve cada rol en su menú y qué hace en ellas (nombres del menú real; capturas de la app con datos ficticios).",
      'Fuente: <b>app/Inicio.py</b> (menú) y <b>pms/seguridad.py</b> (permisos)<br>pms-hoteles-atm · pms-reservas-atm<br>Revisión: 29-oct-2026 · datos ficticios') + \
  f'<div class="grid">{cards}{web}</div>{abajo}{lim}' + FOOT("Recuadro punteado = solo consulta («· ver») · Todos los usuarios crean su contraseña propia en el primer ingreso") + "</div></body></html>"
uso = uso.replace("<span class=g>","<span class=\"g\">")
Path("uso-pantallas-por-actor-pms.html").write_text(uso)

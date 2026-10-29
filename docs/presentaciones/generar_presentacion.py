"""Genera la presentación HTML autocontenida «Uso de las pantallas por actor» del PMS (solo capturas locales con datos ficticios)."""
import base64, io, re, pathlib
from PIL import Image
B = pathlib.Path(__file__).resolve().parents[2]; CAP = B/"docs/capturas"
REF = pathlib.Path(__file__).with_name("estilo_referencia.css")
TIT = "Uso de las pantallas por actor · PMS Hoteles Piloto"
def img(n, w=1000, crop=None):
    im = Image.open(CAP/f"{n}.png").convert("RGB")
    if crop: im = im.crop((0, 0, im.width, min(im.height, int(im.width*crop))))
    if im.width > w: im = im.resize((w, int(im.height*w/im.width)), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=80, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
def fig(n, cap, crop=0.62, cls="", w=1000, style=""):
    return f'<figure class="shot {cls}" style="{style}"><div class="ov"><img src="{img(n,w,crop)}" alt="Captura: {n}"></div><figcaption>{cap} (captura local, datos ficticios)</figcaption></figure>'
C = {"rec": "#1d5fd0", "ger": "#7a5cc4", "hk": "#1f9d57", "adm": "#14304f", "web": "#e8772e"}
slides = []
def actor(key, nombre, k, kick, h2, f1, f2, need, scr, pasos, res):
    pl = "".join(f"<li><b>{i}</b><span>{p}</span></li>" for i, p in enumerate(pasos, 1))
    slides.append(f'<div class="hd"><span class="chip" style="background:{C[key]}">{nombre} · {k}</span><span class="kick">{kick}</span></div><h2>{h2}</h2>'
      f'<div class="duo">{f1}{f2}</div><div class="b4"><div class="sc need"><h4>Qué necesita</h4><p>{need}</p></div>'
      f'<div class="sc scr"><h4>Qué pantalla usa</h4><p>{scr}</p></div><div class="sc stp"><h4>Pasos clave</h4><ol class="nl">{pl}</ol></div>'
      f'<div class="sc res"><h4>Resultado</h4><p>{res}</p></div></div>')
# 1 portada
slides.append(f'''<div class="cv-l"><img class="logo" src="{'data:image/png;base64,'+base64.b64encode((B/'app/assets/atm_logo.png').read_bytes()).decode() if (B/'app/assets/atm_logo.png').exists() else ''}" alt="" style="height:44px;width:auto;align-self:flex-start;margin-bottom:18px">
<div class="kick">PMS Hoteles · Piloto</div><h1>Uso de las pantallas<br>por actor</h1>
<p class="lead">Qué pantalla usa cada persona del hotel —<b>recepción, gerencia, housekeeping y administrador</b>— y cómo el <b>cliente</b> reserva en línea, con capturas reales del prototipo.</p>
<div class="cv-stats"><div><b>5</b><span>actores: 4 roles internos y el cliente web</span></div><div><b>13</b><span>pantallas del PMS más la mini web de reservas</span></div><div><b>18</b><span>habitaciones en 3 plantas en el plano</span></div></div>
<p class="cv-meta"><b>Prototipo diseñado para ATm Consulting</b> · Datos ficticios · Octubre 2026</p></div>
<div class="cv-r">{fig("plano","Plano de habitaciones",0.62,"tilt",900,"width:470px")}</div>''')
# 2 actores
ac = [("rec","Recepción","Atiende al huésped: crea y gestiona reservas, check-in/out y cobros desde el plano y el calendario.","Su hotel · opera el día a día"),
 ("ger","Gerencia","Supervisa ocupación e ingresos, fija tarifas y bloqueos y aprueba lo que recepción solicita.","Su hotel · decide y aprueba"),
 ("hk","Housekeeping","Ve qué habitaciones limpiar o revisar y marca su estado; consulta bloqueos.","Su hotel · limpieza y estado"),
 ("adm","Administrador","Configura hoteles, habitaciones, usuarios y tarifas; genera contraseñas temporales; audita.","Todos los hoteles · configura"),
 ("web","Cliente web","Elige habitación en el plano, la bloquea unos minutos, paga (simulado) y recibe su número de reserva.","Público · sin cuenta"),]
slides.append('<div class="kick">Quiénes usan el sistema</div><h2>Cinco actores, cada uno con su propio menú</h2><div class="actores" style="grid-template-columns:repeat(5,1fr)">'+
 "".join(f'<div class="ac" style="--c:{C[k]}"><b>{n}</b><p>{d}</p><small>{s}</small></div>' for k,n,d,s in ac)+
 '</div><div class="band">El menú se arma según el rol: <b>cada persona ve solo las pantallas que su rol permite</b>, y un usuario con hotel asignado trabaja solo en ese hotel. Todos entran con correo y contraseña, y en el primer ingreso crean la suya.</div>')
# 3 matriz
P = [("Operación diaria",[("Dashboard del día","dashboard"),("Calendario","calendario"),("Plano de habitaciones","plano"),("Reservas","reservas"),("Reservas web","reservas"),("Huéspedes","huespedes"),("Facturación","facturacion")]),
 ("Habitaciones",[("Housekeeping","housekeeping"),("Bloqueos","bloqueos")]),
 ("Gestión y control",[("Tarifas","tarifas"),("Reportes","reportes"),("Configuración","configuracion"),("Auditoría","auditoria")])]
import ast; _t=(B/'pms/seguridad.py').read_text(); PERMISOS=ast.literal_eval(re.search(r'PERMISOS[^=]*=\s*(\{.*?\n\})',_t,re.S).group(1))
roles=[("recepcion","Recepción","rec"),("gerencia","Gerencia","ger"),("housekeeping","Housekeeping","hk"),("administrador","Administrador","adm")]
rows=""
for g, ps in P:
    rows+=f'<tr class="grp"><td colspan="6">{g}</td></tr>'
    for t,k in ps:
        rows+=f"<tr><td>{t}</td>"+"".join({"x":'<td class="vf">●</td>',"ver":'<td class="vc">○</td>'}.get(PERMISOS[k].get(r),"<td></td>") for r,_,_ in roles)+"<td></td></tr>"
rows+='<tr class="grp"><td colspan="6">Reserva en línea (mini web pública)</td></tr><tr><td>Plano, datos, pago y confirmación</td><td></td><td></td><td></td><td></td><td class="vf">●</td></tr>'
slides.append('<div class="kick">Matriz rol × pantalla</div><h2>Quién trabaja en cada pantalla y quién solo consulta</h2><div class="mx-wrap"><table class="mx"><thead><tr><th></th>'+
 "".join(f'<th style="--c:{C[c]}">{n}</th>' for _,n,c in roles)+f'<th style="--c:{C["web"]}">Cliente web</th></tr></thead><tbody>{rows}</tbody></table>'
 '<div class="mx-side"><h3>Cómo leerla</h3><div class="lgd"><span class="vf">●</span> Trabaja aquí: registra o modifica</div><div class="lgd"><span class="vc">○</span> Solo consulta</div>'
 '<p class="note">Solo <b>gerencia aprueba</b> descuentos y cancelaciones, y nunca quien las solicitó.</p><p class="note">«Reservas web» usa el permiso de Reservas: el administrador la consulta.</p>'
 '<p class="note">Housekeeping no ve reservas, huéspedes ni facturación.</p><p class="note">Fuente: tabla de permisos del código (pms/seguridad.py).</p></div></div>')
# 4 ingreso
actor("adm","Todos","primer ingreso","Correo + contraseña temporal","Entrar y crear la contraseña propia en el primer ingreso",
 fig("00_ingreso","Pantalla de ingreso",None),fig("clave_nueva","Crear contraseña nueva",None),
 "Entrar con su usuario y dejar una contraseña que solo esa persona conozca.","<b>Ingreso</b> y, la primera vez, <b>Crear contraseña nueva</b>.",
 ["Escribe correo y contraseña temporal","Crea una nueva de 10+ caracteres y la repite","Entra al menú de su rol"],"La temporal deja de servir. Tras 5 fallos en 15 min el acceso se bloquea un rato.")
# recepcion
actor("rec","Recepción","1 de 4","Su hotel · inicio del turno","Empezar el turno con el dashboard y el calendario",
 fig("recepcion_dashboard","Dashboard del día"),fig("calendario","Calendario de ocupación"),
 "Saber quién llega, quién sale y qué habitaciones están libres hoy.","<b>📊 Dashboard del día</b> y <b>🗓️ Calendario</b>.",
 ["Revisa llegadas y salidas","Mira la ocupación por fechas","Elige una habitación libre"],"Tiene el panorama del día y salta a la reserva desde el calendario.")
actor("rec","Recepción","2 de 4","Plano · vender sin cruces","Elegir la habitación en el plano de cada planta",
 fig("plano_planta","Plano de una planta: camas, estado y vista al mar",None),fig("plano_detalle","Detalle de la habitación elegida"),
 "Ver de un vistazo qué habitación cabe para el grupo y cuánto cuesta.","<b>🗺️ Plano de habitaciones</b>: filtros de fechas, personas, tipo y vista al mar.",
 ["Pone fechas, adultos y niños","Hace clic en una habitación disponible","Pulsa «Continuar con la reserva»"],"Abre Reservas con fechas, habitación y precio ya rellenados.")
actor("rec","Recepción","3 de 4","Reservas · huésped","Crear y gestionar la reserva",
 fig("flujo_nueva_reserva","Nueva reserva"),fig("flujo_gestionar_reserva","Gestionar: check-in, check-out, cancelar"),
 "Registrar al huésped y mover la reserva por su ciclo.","<b>📝 Reservas</b> y <b>🧑‍🤝‍🧑 Huéspedes</b>.",
 ["Completa huésped y datos","Confirma o deja en opción","Hace check-in y check-out"],"La misma regla de disponibilidad impide vender dos veces una habitación.")
actor("rec","Recepción","4 de 4","Cobro · canal web","Cobrar y atender las reservas que llegan por la web",
 fig("facturacion","Facturación"),fig("pms_reservas_web","Reservas web recibidas"),
 "Cerrar la cuenta del huésped y revisar lo reservado en línea.","<b>🧾 Facturación</b> y <b>🌐 Reservas web</b>.",
 ["Registra cargos y pagos","Emite el comprobante","Revisa las reservas del canal web"],"Cuenta cerrada; las reservas web aparecen con su número y canal.")
# gerencia
actor("ger","Gerencia","1 de 3","Su hotel · aprobar","Aprobar lo que recepción solicita",
 fig("flujo_aprobaciones","Aprobaciones pendientes"),fig("dashboard","Dashboard del día"),
 "Controlar descuentos y cancelaciones sin frenar la operación.","<b>Reservas › Aprobaciones</b> y <b>📊 Dashboard</b>.",
 ["Revisa la solicitud y el motivo","Aprueba o rechaza","Sigue la ocupación del día"],"Separación de funciones: nadie aprueba su propia solicitud.")
actor("ger","Gerencia","2 de 3","Precios y disponibilidad","Fijar tarifas y bloquear habitaciones",
 fig("tarifas","Tarifas por tipo y temporada"),fig("bloqueos","Bloqueos de habitaciones"),
 "Ajustar precios y sacar habitaciones de la venta por mantenimiento.","<b>💲 Tarifas</b> y <b>🚧 Bloqueos</b>.",
 ["Edita la tarifa por tipo","Crea un bloqueo con fechas y motivo","Comprueba el plano"],"El plano y la web muestran el precio nuevo y la habitación bloqueada.")
actor("ger","Gerencia","3 de 3","Resultados","Medir el hotel con reportes y la auditoría",
 fig("reportes","Reportes"),fig("auditoria","Auditoría (solo consulta)"),
 "Conocer ocupación, ingresos y quién cambió qué.","<b>📈 Reportes</b>, <b>🔍 Auditoría</b> y <b>⚙️ Configuración</b> en consulta.",
 ["Elige periodo","Revisa ocupación e ingresos","Exporta o consulta la bitácora"],"Decisiones con datos; la bitácora no se puede editar.")
# housekeeping
actor("hk","Housekeeping","1 de 1","Su hotel · limpieza","Ver qué limpiar y marcar el estado de cada habitación",
 fig("housekeeping_rol","Menú de housekeeping"),fig("flujo_housekeeping","Cambiar estado de limpieza"),
 "Saber qué habitaciones liberar y avisar cuando estén listas.","<b>🧹 Housekeeping</b> y <b>🚧 Bloqueos</b> en consulta.",
 ["Ve la lista por estado","Limpia y marca «Limpia» o «Inspeccionada»","Reporta fuera de servicio"],"Recepción ve al instante qué habitación está lista.")
# admin
actor("adm","Administrador","1 de 2","Todos los hoteles · configurar","Configurar hoteles, habitaciones y usuarios",
 fig("admin_configuracion","Configuración"),fig("configuracion","Habitaciones: camas, metros y vista al mar"),
 "Dejar listo el catálogo que usan todas las pantallas.","<b>⚙️ Configuración</b>, <b>💲 Tarifas</b> y <b>🚧 Bloqueos</b>.",
 ["Crea hotel, plantas y habitaciones","Marca camas y vista al mar","Crea usuarios con su rol"],"El plano y la web se dibujan a partir de esta configuración.")
actor("adm","Administrador","2 de 2","Accesos · control","Generar contraseñas temporales y auditar",
 fig("admin_clave_temporal","Generar contraseña temporal"),fig("auditoria","Auditoría"),
 "Devolver el acceso a quien lo perdió y revisar cambios.","<b>⚙️ Configuración › Usuarios</b> y <b>🔍 Auditoría</b>.",
 ["Elige el usuario","Genera la temporal (se muestra una vez)","Consulta la bitácora"],"El usuario deberá crear su contraseña al entrar. Las operativas las consulta.")
# web
actor("web","Cliente web","1 de 3","Público · sin cuenta","Elegir la habitación en el plano del hotel",
 fig("web_02_plano","Plano en la mini web",0.9,w=800),fig("web_04_datos_con_temporizador","Datos con bloqueo temporal",0.9,w=800),
 "Ver qué hay libre y asegurar la habitación mientras completa datos.","<b>Reserva en línea</b>: hotel, fechas, huéspedes y plano.",
 ["Elige fechas y personas","Hace clic en una habitación libre","Llena sus datos antes de que venza el temporizador"],"La habitación queda bloqueada unos minutos para nadie más.")
actor("web","Cliente web","2 de 3","Consentimiento · pago","Aceptar condiciones y pagar (simulado)",
 fig("web_05_consentimiento","Consentimiento y condiciones",0.9,w=800),fig("web_07_pasarela_simulada","Pasarela en modo de pruebas",0.9,w=800),
 "Pagar con seguridad y saber qué acepta.","<b>Consentimiento</b> y <b>pasarela simulada</b> rotulada como pruebas.",
 ["Acepta datos y política","Paga en la pasarela de prueba","Espera el aviso de pago"],"La reserva pasa de bloqueada a pagada y confirmada. No se cobra dinero real.")
actor("web","Cliente web","3 de 3","Confirmación","Recibir el número de reserva",
 fig("web_08_confirmacion","Confirmación",0.9,w=800),fig("web_09_correo_simulado","Correo de confirmación (simulado)",0.9,w=800),
 "Tener la prueba de su reserva.","<b>Confirmación</b> en pantalla y correo.",
 ["Ve su número de reserva","Revisa el correo con el resumen","Recepción la ve en Reservas web"],"El correo se muestra en pantalla en el prototipo; falta el proveedor real.")
# recorrido
steps=[("web","Cliente","Reserva en la web","web_08_confirmacion"),("rec","Recepción","La ve en Reservas web","pms_reservas_web"),("rec","Recepción","Check-in en Reservas","flujo_gestionar_reserva"),
 ("hk","Housekeeping","Limpia tras la salida","flujo_housekeeping"),("ger","Gerencia","Revisa reportes","reportes"),("adm","Administrador","Audita los cambios","auditoria")]
slides.append('<div class="kick">Una reserva de punta a punta</div><h2>Cómo pasa una reserva por los cinco actores</h2><div class="tline">'+
 "".join(f'<div class="tc">{fig(n,t,0.4,w=500)}<span class="tn" style="background:{C[k]}">{i}</span><div class="tt"><span class="who" style="color:{C[k]}">{w}</span><b>{t}</b></div></div>' for i,(k,w,t,n) in enumerate(steps,1))+
 '</div><div class="band">Todas las pantallas comparten <b>la misma base de datos y la misma regla de disponibilidad</b>: lo que vende la web desaparece del plano del PMS.</div>')
# limitaciones
lims=[("Pago simulado","La pasarela está en modo de pruebas; no se cobra dinero real."),("Correo simulado","La confirmación se muestra en pantalla hasta tener proveedor de correo."),
 ("Opción de 48 h","Aún no vence sola; falta el vencimiento automático."),("App que se duerme","Si no hay tráfico, Streamlit la duerme; se despierta con un botón."),("Datos ficticios","Hoteles, huéspedes y reservas son de prueba.")]
slides.append('<div class="kick">Lo que hay que saber</div><h2>Límites del piloto</h2><div class="lims">'+"".join(f'<div class="lm"><b>{a}</b><p>{b}</p></div>' for a,b in lims)+
 '</div><div class="real"><h3>Lo que sí funciona</h3><div class="chips2"><span>Menú por rol</span><span>Contraseña propia en el primer ingreso</span><span>Plano por planta con camas y vista al mar</span><span>Sin doble venta</span><span>Aprobación por gerencia</span><span>Bloqueo temporal en la web</span><span>Número de reserva</span><span>Auditoría</span></div></div>')
# cta
slides.append('<div class="kick">Pruébelo usted mismo</div><h2>Cómo entrar al piloto</h2><div class="cta-grid"><div class="steps">'
 '<div class="sp"><i>1</i><div><b>PMS del hotel</b>Entre con el correo de su rol y la contraseña temporal que le entregó ATm Consulting.</div></div>'
 '<div class="sp"><i>2</i><div><b>Primer ingreso</b>Cree su contraseña de al menos 10 caracteres.</div></div>'
 '<div class="sp"><i>3</i><div><b>Reserva en línea</b>Abra la mini web, elija habitación y pague en modo de pruebas.</div></div>'
 '<div class="sp"><i>4</i><div><b>Si la app duerme</b>Pulse el botón para despertarla y espere 1 o 2 minutos.</div></div></div>'
 '<div class="ctabox"><small>PMS (personal del hotel)</small><b class="url">pms-hoteles-atm.streamlit.app</b><span>https://pms-hoteles-atm.streamlit.app/</span><div class="sep"></div>'
 '<small>Reserva en línea (cliente)</small><b class="url">pms-reservas-atm.streamlit.app</b><span>https://pms-reservas-atm.streamlit.app/</span><div class="sep"></div>'
 '<div class="ck">Recorrido sugerido (≈ 15 min)</div><ol class="route"><li>Cliente: reservar en la web</li><li>Recepción: plano, reserva y check-in</li><li>Housekeeping: marcar limpia</li><li>Gerencia: aprobar y ver reportes</li><li>Administrador: configuración y auditoría</li></ol></div></div>')
N=len(slides)
css=REF.read_text()+'''
/* PMS: fondo blanco en portada y cierre */
.cover,.cta{background:#fff!important}.cover .cv-l{color:var(--ink)}.cover h1{color:var(--navy)}.cover .kick,.cta .kick{color:var(--or)}
.lead{color:var(--ink)}.lead b{color:var(--navy)}.cv-stats div{background:var(--bg);border-color:var(--line)}.cv-stats b{color:var(--or)}.cv-stats span{color:var(--ink)}
.cv-meta{color:var(--mu)}.cv-meta b{color:var(--navy)}.cover .ft,.cta .ft{color:#9aa6b5;border-color:#eef1f5}.cover .ft span:first-child,.cta .ft span:first-child{color:var(--navy)}
.cta h2{color:var(--navy)}.sp{background:var(--bg);border-color:var(--line);color:var(--ink)}.sp b{color:var(--navy)}.ctabox{box-shadow:0 10px 30px rgba(20,48,79,.15);border:1px solid var(--line)}
html,body{background:#eef1f5}.duo figure.shot img{max-height:350px;object-fit:cover;object-position:left top}.tline{grid-template-columns:repeat(3,1fr)}
'''
out=[]
for i,s in enumerate(slides,1):
    cls="cover" if i==1 else ("cta" if i==N else "")
    out.append(f'<section class="slide {cls}" data-n="{i}">{s}<div class="ft"><span>Powered by ATm · Prototipo diseñado para ATm Consulting</span><span>{TIT}</span><span>{i} / {N}</span></div></section>')
js=pathlib.Path(__file__).with_name("navegacion.js").read_text()
html=f'<!doctype html><html lang="es-CO"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{TIT}</title><style>{css}</style></head><body><div id="bar"></div><div id="deck"><div id="stage">{"".join(out)}</div></div><div id="nav"><button onclick="go(i-1)" aria-label="Anterior">‹</button><span id="cnt"></span><button onclick="go(i+1)" aria-label="Siguiente">›</button></div><script>{js}</script></body></html>'
o=pathlib.Path(__file__).with_name("uso-pantallas-por-actor-pms.html"); o.write_text(html); print(o, N, len(html)//1024, "KB")

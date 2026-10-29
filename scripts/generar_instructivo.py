"""Genera docs/instructivo-pms-por-rol.docx y .pdf (un capítulo por rol, flujos simples, sin datos reales)."""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from docs_comun import *  # noqa

AZ, VE, NA = "#e8f0fe", "#e6f4ea", "#fff3e0"

# ---------- diagramas ----------
D = {}
D["reserva"] = diagrama("flujo_reserva", ["Buscar o crear\nhuésped", "Consentimiento\n(Ley 1581)", "Elegir tipo\ny fechas", "Revisar precio\npor noche", "Guardar\nreserva", "Confirmación\n(simulada)"], cols=3, alto=1.3, ancho=9, colores={4: VE})
D["estancia"] = diagrama("flujo_estancia", ["Confirmada", "Check-in\n(día de llegada)", "Alojado", "Cobrar\ny saldar", "Check-out", "Habitación\nsucia"], colores={2: VE, 5: NA}, cols=3, alto=1.3, ancho=9)
D["cancelar"] = diagrama("flujo_cancelacion", ["Recepción\nsolicita", "Queda\n«pendiente»", "Otra persona de\ngerencia revisa", "Aprueba\no rechaza", "Auditoría\nlo registra"], colores={2: NA, 3: VE}, cols=5, alto=1.3, ancho=11)
D["limpieza"] = diagrama("flujo_limpieza", ["Sucia", "En limpieza", "En inspección", "Lista"], colores={0: NA, 3: VE}, cols=4, alto=1.2, ancho=10)
D["descuento"] = diagrama("flujo_descuento", ["Recepción pide\ndescuento (%)", "Pendiente:\nno cuenta aún", "Gerencia (otra\npersona) decide", "Aprobado: baja\nel total"], colores={1: NA, 3: VE}, cols=4, alto=1.3, ancho=10)
D["primer"] = diagrama("flujo_primer_ingreso", ["Ingresas con tu\ncorreo y la clave\ntemporal", "Aparece solo\n«Crea tu contraseña\nnueva»", "Escribes la nueva\ny la confirmas", "Guardas y\nentras al\nsistema"], colores={1: NA, 3: VE}, cols=4, alto=1.4, ancho=11)
D["temporal"] = diagrama("flujo_clave_temporal", ["Administrador\npulsa «Generar\ncontraseña temporal»", "Se muestra\nUNA sola vez", "La entregas\npor un canal\nprivado", "La persona crea\nsu contraseña\nal ingresar"], colores={1: NA, 3: VE}, cols=4, alto=1.4, ancho=11)
D["plano"] = diagrama("flujo_plano", ["Elegir hotel,\nfechas y\nhuéspedes", "Ver la planta\ncon colores\npor estado", "Clic en una\nhabitación\ndisponible", "Revisar camas\ny desglose\ndel precio", "Continuar con\nla reserva", "Reservas ya\ntrae los datos"], colores={2: NA, 5: VE}, cols=3, alto=1.3, ancho=9)
D["web"] = diagrama("flujo_reserva_web", ["Hotel, fechas\ny huéspedes", "Elegir tipo o\nhabitación\nen el plano", "Bloqueo de\n15 minutos\n(con reloj)", "Datos y\nconsentimiento\n(Ley 1581)", "Pago\n(simulado)", "Confirmación\ncon número\nPMS-AAAA-XXXXXX"], colores={2: NA, 4: NA, 5: VE}, cols=3, alto=1.3, ancho=9)
D["admin"] = diagrama("flujo_admin", ["Crear hotel\n(país y moneda)", "Impuestos\n(nombre y %)", "Tipos de\nhabitación", "Habitaciones\ny camas", "Usuarios\ny roles"], cols=5, alto=1.3, ancho=11)

d = nuevo_documento("Instructivo por rol", "PMS hotelero (piloto) · recepción, gerencia, housekeeping y administrador")
parrafo(d, "Versión 1.3 · 28 de octubre de 2026 · Preparado para ATm Consulting, Colombia", color=GRIS, tam=10)
nota(d, "Todos los datos del piloto son ficticios (hoteles, huéspedes, reservas, pagos). Los correos de confirmación, los pagos y las conexiones "
        "con otras plataformas están simulados: la pantalla siempre lo avisa. El comprobante PDF NO es una factura legal.", "Importante")
salto(d)

d.add_heading(lim("Cómo usar este instructivo"), 1)
parrafo(d, "Cada capítulo explica, con pasos cortos, lo que puede hacer una persona según su rol. Busca el tuyo y sigue los pasos. "
           "Los cuadros amarillos son avisos importantes.")
d.add_heading(lim("Entrar a la aplicación"), 2)
lista(d, ["Abre https://pms-hoteles-atm.streamlit.app/ (si la app estuvo un rato sin uso, puede tardar unos segundos en despertar; pulsa el botón que aparezca).",
          "Escribe tu correo y la contraseña TEMPORAL que te entregó ATm Consulting y pulsa «Entrar». Los datos de acceso se entregan aparte; no los compartas.",
          "La primera vez, el sistema te pide crear tu propia contraseña (ver «Primer ingreso» más abajo). Desde la segunda vez entras con la contraseña que tú creaste.",
          "Si te equivocas 5 veces seguidas, el acceso se bloquea 15 minutos. Es una medida de seguridad.",
          "Tu sesión dura 8 horas. Si recargas la página (F5) no te saca. Para salir, usa «Cerrar sesión» en el menú de la izquierda.",
          "Si trabajas en varios hoteles, elige el hotel en el menú de la izquierda. Cada hotel muestra sus precios en su moneda."], numerada=True)
imagen(d, CAPT / "00_ingreso.png", 14, "Pantalla de ingreso (datos ficticios)")
d.add_heading(lim("Primer ingreso: crea tu contraseña nueva"), 2)
parrafo(d, "La contraseña temporal sirve solo para entrar la primera vez. Al ingresar con ella, la aplicación muestra únicamente la pantalla "
           "«Crea tu contraseña nueva»: no puedes abrir ninguna otra pantalla hasta terminar este paso.")
imagen(d, D["primer"], 15)
lista(d, ["Escribe tu contraseña nueva en «Contraseña nueva». Debe tener al menos 10 caracteres y ser distinta de la temporal.",
          "Vuelve a escribirla en «Confirma la contraseña nueva». Las dos deben ser iguales.",
          "Pulsa «Guardar y entrar». Entras al sistema y la temporal deja de servir.",
          "Si algo no cumple, un aviso rojo te dice qué corregir (por ejemplo, «La contraseña nueva debe tener al menos 10 caracteres») y no se guarda nada."], numerada=True)
imagen(d, CAPT / "clave_nueva.png", 15, "Pantalla «Crea tu contraseña nueva» (usuario ficticio)")
imagen(d, CAPT / "clave_nueva_error.png", 15, "Aviso cuando la contraseña es muy corta")
nota(d, "Si recargas la página (F5) o cierras y vuelves a abrir con la misma sesión antes de guardar, sigues viendo «Crea tu contraseña nueva»: "
        "el bloqueo se mantiene hasta que la crees. Si pulsas «Cerrar sesión» sin guardar, la temporal sigue valiendo para el próximo ingreso. "
        "Elige una contraseña que solo tú conozcas y no la reutilices de otros sistemas.", "Ojo")
d.add_heading(lim("Si olvidaste tu contraseña"), 2)
parrafo(d, "Pide al administrador que te genere una contraseña temporal nueva (capítulo 4). Con ella ingresas y creas otra propia. "
           "Al generarla, las sesiones que tuvieras abiertas se cierran solas.")
d.add_heading(lim("Qué ve cada rol"), 2)
tabla(d, ["Pantalla", "Recepción", "Gerencia", "Housekeeping", "Administrador"], [
    ["Dashboard del día", "Usa", "Usa", "—", "Ver"], ["Calendario", "Usa", "Usa", "—", "Ver"],
    ["Plano de habitaciones", "Usa (puede continuar a Reservas)", "Usa", "—", "Ver (solo consulta)"],
    ["Reservas", "Usa (cancelar pide gerencia)", "Usa y aprueba", "—", "Ver"], ["Huéspedes", "Usa", "Usa", "—", "Ver"],
    ["Housekeeping", "Ver", "Usa", "Usa", "Ver"], ["Bloqueos", "Ver", "Usa", "Ver", "Usa"],
    ["Tarifas", "Ver", "Usa", "—", "Usa"], ["Facturación", "Usa (descuentos piden gerencia)", "Usa y aprueba", "—", "Ver"],
    ["Reportes", "—", "Usa", "—", "Usa"], ["Configuración", "—", "Ver", "—", "Usa"], ["Auditoría", "—", "Ver", "—", "Ver"]],
    anchos=[3.6, 3.6, 3.1, 3.0, 3.0])
parrafo(d, "«Ver» significa que solo puedes consultar. «—» significa que la pantalla no aparece en tu menú. Housekeeping nunca ve precios ni pagos.")
salto(d)

# ---------- RECEPCIÓN ----------
d.add_heading(lim("1. Recepción"), 1)
parrafo(d, "Recepción atiende llegadas, salidas, reservas, huéspedes y cobros.")
d.add_heading(lim("1.1 Empezar el día: Dashboard del día"), 2)
lista(d, ["Entra a «Dashboard del día». Verás las llegadas de hoy, las salidas de hoy, la ocupación y el estado de limpieza.",
          "Los botones azules de cada tarjeta te llevan directo a la reserva o a la habitación."])
imagen(d, CAPT / "recepcion_dashboard.png", 15.5, "Dashboard del día (datos ficticios)")
d.add_heading(lim("1.2 Crear una reserva"), 2)
imagen(d, D["reserva"], 14)
lista(d, ["Ve a «Reservas» y abre la pestaña «➕ Nueva reserva».",
          "Paso 1: busca al huésped por nombre, documento o correo. Si no existe, usa el enlace «Crear huésped» y registra su consentimiento de datos.",
          "Paso 2: elige tipo de habitación, fechas de entrada y salida, adultos y niños. «Habitación (opcional)» te deja escoger una habitación concreta; si la dejas en «Asignar automáticamente», el sistema elige una libre. «Estado inicial» puede ser consulta, opción o confirmada.",
          "Paso 3: revisa el desglose por noche, los impuestos del hotel y el total. El precio de cada noche queda congelado al guardar.",
          "Pulsa «Guardar reserva». El sistema usa la habitación elegida o asigna una libre. Si no hay, te avisa en rojo y no guarda nada.",
          "Para avisar al huésped usa «Simular envío de confirmación» (en «Gestionar una reserva»). Es una simulación: no sale ningún correo real."], numerada=True)
nota(d, "El sistema no permite vender dos veces la misma habitación en la misma noche, ni aunque dos personas guarden al mismo tiempo.")
d.add_heading(lim("1.3 Recibir al huésped (check-in) y despedirlo (check-out)"), 2)
imagen(d, D["estancia"], 14)
lista(d, ["Pestaña «🛠️ Gestionar una reserva» → elige la reserva.",
          "Check-in: solo desde el día de llegada, con la habitación en estado «Lista» y sin cancelación pendiente. Pulsa «Hacer check-in».",
          "Cobros: usa «Facturación» (ver 1.5).",
          "Check-out: pulsa «Hacer check-out». Si queda saldo pendiente, el sistema no te deja; solo gerencia puede forzar la salida.",
          "Al hacer check-out, la habitación pasa sola a «Sucia» para que housekeeping la limpie."], numerada=True)
d.add_heading(lim("1.4 Cambiar o cancelar una reserva"), 2)
lista(d, ["Cambiar fechas, personas o notas: «✏️ Cambiar fechas, personas o notas». Las noches que ya tenía conservan su precio.",
          "Cambiar de habitación: elige la nueva habitación y pulsa «Cambiar habitación» (si está libre esas noches).",
          "No se presentó: si la entrada ya pasó, pulsa «Marcar no-show». La habitación se libera.",
          "Cancelar: escribe el motivo y pulsa «Solicitar cancelación». Recepción no cancela sola: gerencia debe aprobar."])
imagen(d, D["cancelar"], 15)
d.add_heading(lim("1.5 Cobrar: Facturación"), 2)
lista(d, ["Ve a «Facturación» → pestaña «🧾 Cuenta de una reserva» y elige la reserva.",
          "Agregar un extra (minibar, lavandería…): descripción, cantidad y precio → «Agregar extra».",
          "Registrar un pago: método (efectivo, datáfono o transferencia), monto y referencia → «Registrar pago». Los pagos son simulados: no se cobra ninguna tarjeta.",
          "Si te equivocaste: «Anular extra» o «Anular pago» con el motivo. La línea no se borra, queda marcada como anulada.",
          "Descuento: escribe el porcentaje y el motivo → «Solicitar descuento». Queda pendiente hasta que gerencia lo apruebe.",
          "Comprobante: descarga el PDF de la cuenta."], numerada=True)
imagen(d, D["descuento"], 15)
nota(d, "El PDF es un comprobante simple de cuenta. NO es una factura legal ni electrónica.")
d.add_heading(lim("1.6 Huéspedes y consentimiento (Ley 1581)"), 2)
lista(d, ["«Huéspedes» → «🔎 Buscar y ver ficha» o «➕ Nuevo huésped».",
          "En la ficha, sección «Consentimientos»: pulsa «Registrar que el huésped aceptó» cuando el huésped autoriza el uso de sus datos. Sin consentimiento vigente, el sistema te avisa antes de reservar.",
          "Para borrar los datos personales de un huésped (anonimizar) se marca «Entiendo que no se puede deshacer»; las reservas se conservan sin sus datos."])
d.add_heading(lim("1.7 Calendario"), 2)
parrafo(d, "El calendario es una rejilla de habitaciones por días, con colores por estado. Solo sirve para mirar: las reservas se crean y cambian en «Reservas».")
imagen(d, CAPT / "calendario.png", 15.5, "Calendario de solo lectura (datos ficticios)")
d.add_heading(lim("1.8 Plano de habitaciones: elegir la habitación mirando el plano"), 2)
parrafo(d, "Es una forma visual de reservar: ves cada planta del hotel dibujada con sus habitaciones, el color de cada una según su estado en las fechas "
           "que tú escojas, y desde el plano pasas a «Reservas» con todo ya escrito. Usa exactamente las mismas reglas que «Reservas»: "
           "una habitación solo se muestra como disponible si realmente se puede vender esas noches.")
imagen(d, D["plano"], 14)
lista(d, ["Entra a «Plano de habitaciones» en el menú de la izquierda.",
          "Arriba elige el hotel (si tienes varios), la fecha de entrada y de salida, y cuántos adultos y niños. Los números de arriba (disponibles, ocupadas, en opción…) se actualizan solos.",
          "Elige la planta (1, 2 o 3). La planta se dibuja como un plano: arriba la franja azul «MAR» con las habitaciones que tienen vista al mar (etiqueta «🌊 VISTA MAR»), en medio el «PASILLO CENTRAL» y abajo las demás habitaciones y la escalera. Dentro de cada habitación ves sus camas dibujadas con la medida (150 cm matrimonial, 90 cm individual), los metros, la tipología, las personas que caben y el precio por noche si está libre.",
          "Filtros opcionales: «Tipo de habitación», «🌊 Solo vista al mar» y «Ocultar no disponibles» (deja en pantalla solo lo que se puede vender).",
          "Pulsa «Elegir» en una habitación verde (disponible). Se pinta de azul y debajo del plano aparece el detalle: planta, metros, capacidad, vista, camas y el desglose del precio (cada noche, impuestos del hotel y total).",
          "Pulsa «Continuar con la reserva →». Se abre «Reservas» → «Nueva reserva» con el tipo, la habitación, las fechas y los huéspedes ya puestos. Solo te falta elegir al huésped, revisar el precio y pulsar «Guardar reserva»."], numerada=True)
imagen(d, CAPT / "plano_planta.png", 15.5, "Plano dibujado de la planta 1: mar, pasillo, camas y estados (datos ficticios)")
imagen(d, CAPT / "plano.png", 15.5, "Plano de la planta 1 con todos los estados (datos ficticios)")
imagen(d, CAPT / "plano_detalle.png", 15.5, "Habitación elegida: detalle y desglose del precio")
imagen(d, CAPT / "plano_reserva.png", 15.5, "«Reservas» con los datos traídos del plano")
tabla(d, ["Color", "Qué significa"], [
    ["Verde · Disponible", "Se puede vender todas las noches pedidas y cabe el número de personas."],
    ["Rojo · Ocupada", "Ya tiene una reserva (confirmada, alojada…) en alguna de esas noches."],
    ["Amarillo · En opción", "Tiene una reserva solo en opción o consulta: todavía no es firme, pero ya ocupa la noche."],
    ["Rayado rojo · Bloqueada", "Un bloqueo por mantenimiento (pantalla «Bloqueos») la retiene esas fechas."],
    ["Rayado gris · Fuera de servicio", "Housekeeping la marcó fuera de servicio (por ejemplo, una avería). No se puede elegir."],
    ["Azul · Seleccionada", "La habitación que escogiste para continuar con la reserva."],
    ["Gris claro · Capacidad insuficiente", "Está libre, pero no cabe el número de adultos y niños que pusiste. Cambia las personas o elige otra."]], anchos=[5, 11.5])
nota(d, "El plano se actualiza cada vez que cambias un dato. Si mientras tanto otra persona reserva esa habitación, al pulsar «Continuar con la reserva» el sistema te avisa y no pasa nada raro. "
        "Y si «Reservas» no puede guardar por cualquier motivo, no se pierde la sesión ni lo que escribiste.", "Ojo")
salto(d)

# ---------- GERENCIA ----------
d.add_heading(lim("2. Gerencia"), 1)
parrafo(d, "Gerencia hace todo lo de recepción (incluido el Plano de habitaciones, sección 1.8) y además aprueba, cambia tarifas y ve los reportes.")
d.add_heading(lim("2.1 Aprobar o rechazar cancelaciones"), 2)
lista(d, ["«Reservas» → pestaña «⏳ Cancelaciones pendientes».",
          "Lee el motivo, escribe un comentario (opcional) y pulsa aprobar o rechazar.",
          "Regla de separación de funciones: no puedes aprobar una solicitud que registraste tú. Debe aprobarla otra persona de gerencia."])
d.add_heading(lim("2.2 Aprobar descuentos"), 2)
lista(d, ["«Facturación» → pestaña «⏳ Descuentos pendientes».", "Revisa el porcentaje y el motivo; aprueba o rechaza. Solo un descuento aprobado baja el total de la cuenta."])
d.add_heading(lim("2.3 Salida con saldo"), 2)
parrafo(d, "Si un huésped se va con saldo pendiente, en «Gestionar una reserva» aparece «Forzar salida con saldo (gerencia)». Queda registrado en la auditoría.")
d.add_heading(lim("2.4 Tarifas"), 2)
lista(d, ["«Tarifas» → «Editar una tarifa» para cambiar un precio, o «Nueva tarifa» para crear una por tipo de habitación y fechas.",
          "Un cambio de tarifa solo afecta a las noches nuevas: las reservas ya hechas conservan el precio congelado."])
d.add_heading(lim("2.5 Bloqueos por mantenimiento"), 2)
lista(d, ["«Bloqueos» → «Nuevo bloqueo»: elige habitación, fechas y motivo → «Crear bloqueo».",
          "Mientras dure, la habitación no se puede vender. El sistema no deja bloquear fechas que ya tienen una reserva."])
d.add_heading(lim("2.6 Reportes"), 2)
lista(d, ["«Reportes»: ocupación diaria (%), ingreso diario de alojamiento y resumen por mes, con descarga en CSV.",
          "Todo se muestra en la moneda local del hotel elegido. El piloto no convierte entre monedas."])
imagen(d, CAPT / "reportes.png", 15.5, "Reportes (datos ficticios)")
d.add_heading(lim("2.7 Auditoría"), 2)
parrafo(d, "«Auditoría» muestra quién hizo qué y cuándo (ingresos, cambios, aprobaciones). Solo se puede consultar: nadie puede editarla ni borrarla.")
salto(d)

# ---------- HOUSEKEEPING ----------
d.add_heading(lim("3. Housekeeping (limpieza)"), 1)
parrafo(d, "Housekeeping ve solo el tablero de limpieza y los bloqueos. No ve precios, pagos ni datos de huéspedes.")
imagen(d, D["limpieza"], 13)
lista(d, ["Entra a «Housekeeping». Verás una tarjeta por habitación con su estado.",
          "Usa el filtro «Mostrar estados» para ver, por ejemplo, solo las sucias.",
          "Cuando empieces a limpiar, pulsa el botón de la tarjeta para pasarla a «En limpieza»; al terminar, a «En inspección».",
          "Quien inspecciona confirma «Lista». Regla: quien pasó la habitación a inspección no puede darla por lista; lo hace otra persona.",
          "Si hay una avería, elige «Cambiar a» → «Fuera de servicio», escribe la nota (obligatoria) y pulsa «Aplicar cambio». Después se vuelve a «Sucia» y se limpia otra vez."], numerada=True)
imagen(d, CAPT / "housekeeping_rol.png", 15.5, "Tablero de housekeeping (sin precios)")
nota(d, "Una habitación que no está «Lista» no permite hacer check-in.")
salto(d)

# ---------- ADMINISTRADOR ----------
d.add_heading(lim("4. Administrador"), 1)
parrafo(d, "El administrador configura el sistema (hoteles, impuestos, habitaciones y usuarios). Está separado de gerencia a propósito: quien aprueba descuentos no debe poder cambiar también las reglas sin dejar rastro.")
imagen(d, D["admin"], 15)
d.add_heading(lim("4.1 Configuración (pestañas)"), 2)
tabla(d, ["Pestaña", "Para qué sirve"], [
    ["🏨 Hoteles", "Crear un hotel con su país, moneda local y zona horaria."],
    ["🧮 Impuestos", "Cada hotel tiene sus propios impuestos: nombre y porcentaje. Son genéricos, no se asume la norma de un país."],
    ["🛏️ Tipos de habitación", "Nombre, capacidad y descripción (Familiar, Triple, Doble, Individual…)."],
    ["🚪 Habitaciones y camas", "Cada habitación con su planta, tipo, vista, camas y la casilla «Vista al mar» (alimenta el filtro del Plano de habitaciones). El piloto trae una distribución de prueba provisional de 18 habitaciones (3 plantas × 6)."],
    ["👤 Usuarios", "Crear usuarios, asignarles rol y hotel, cambiar contraseña, generar una contraseña temporal o desactivarlos. La tabla indica quién todavía debe crear su contraseña."]], anchos=[4.5, 12])
d.add_heading(lim("4.2 Generar una contraseña temporal"), 2)
parrafo(d, "Sirve cuando alguien olvidó su contraseña o cuando creas a una persona nueva. Está en «Configuración» → pestaña «Usuarios» → «Generar contraseña temporal».")
imagen(d, D["temporal"], 15)
lista(d, ["Busca a la persona en la lista y pulsa «Generar contraseña temporal» junto a su correo.",
          "El sistema crea una contraseña aleatoria segura y la muestra UNA sola vez en pantalla. Cópiala en ese momento: no se vuelve a mostrar ni se guarda en claro en ningún lugar.",
          "Entrégala a la persona por un canal privado (no por un grupo de chat ni en un correo abierto).",
          "Desde ese momento: se cierran las sesiones anteriores de esa persona y, al ingresar, solo verá «Crea tu contraseña nueva». La tabla de usuarios muestra «Sí» en «Debe crear su contraseña» hasta que lo haga.",
          "La acción queda en Auditoría (quién la generó y para quién), sin la contraseña.",
          "No puedes generarte una contraseña temporal a ti mismo: usa «Activar, desactivar o cambiar contraseña». Si cambias la contraseña de otra persona con esa opción, ella también deberá crear la suya al ingresar."], numerada=True)
imagen(d, CAPT / "admin_clave_temporal.png", 15.5, "Configuración → Usuarios → Generar contraseña temporal (usuarios ficticios; aquí aún no se ha generado ninguna)")
nota(d, "Si pulsas otro botón o recargas la página, la contraseña temporal ya no se muestra. Si la perdiste antes de entregarla, genera otra.")
d.add_heading(lim("4.3 Otras tareas"), 2)
lista(d, ["Bloqueos y tarifas: igual que gerencia (ver capítulo 2).", "Reportes: igual que gerencia.",
          "Auditoría: consultar quién hizo qué.", "Dashboard, calendario, plano de habitaciones, reservas, huéspedes y facturación: solo consulta (en el plano puedes ver el detalle y el precio, pero no aparece «Continuar con la reserva»)."])
nota(d, "Los cambios de impuestos solo afectan a las líneas nuevas: las ya cobradas conservan el porcentaje con el que se cobraron.")
imagen(d, CAPT / "admin_configuracion.png", 15.5, "Configuración (datos ficticios)")
salto(d)

# ---------- RESERVA WEB ----------
d.add_heading(lim("5. Reserva web (mini web para clientes)"), 1)
parrafo(d, "Es una página PÚBLICA y separada del PMS donde el cliente elige habitación, la bloquea unos minutos, deja sus datos, paga y recibe un número de reserva. "
           "La reserva aparece sola en el PMS con canal «web». En este prototipo el pago y el correo son SIMULADOS: no se cobra ni se envía nada.")
nota(d, "La dirección de la mini web es https://pms-reservas-atm.streamlit.app/ . La pantalla siempre dice «Prototipo con datos ficticios» y «MODO PRUEBAS: no se cobra dinero». "
        "Usa solo datos inventados (por ejemplo, correo nombre@prueba-web.invalid).", "Importante")
imagen(d, D["web"], 15)
d.add_heading(lim("5.1 Lo que hace el cliente"), 2)
lista(d, ["Elige hotel, fechas, adultos y niños y pulsa «Ver habitaciones disponibles». Ve los tipos de habitación con su precio total e impuestos, y el plano por plantas (solo número, tipo, vista y si está libre).",
          "Pulsa «Reservar este tipo» (el sistema asigna una habitación libre) o «Elegir» en una habitación del plano.",
          "Responde la pregunta de suma (verificación anti-robots) y pulsa «Bloquear mi habitación». Aparece un reloj de 15 minutos: mientras corre, nadie más puede reservar esa habitación.",
          "Escribe nombres, apellidos y correo (teléfono y documento son opcionales), lee el aviso de privacidad (Ley 1581 de 2012) y marca la casilla de autorización (obligatoria). Sin ella no se puede continuar. Pulsa «Continuar al pago».",
          "Revisa el resumen y pulsa «Pagar». Se abre la pantalla de la pasarela SIMULADA («MODO PRUEBAS: no se cobra dinero»): pulsa «Simular pago aprobado» (o «rechazado» para probar el reintento). No se pide ninguna tarjeta.",
          "Ve la confirmación con el número de reserva (PMS-AAAA-XXXXXX), el enlace para ver su reserva y el aviso «Correo simulado: no se envió», con una vista del correo que recibiría."], numerada=True)
imagen(d, CAPT / "web_02_plano.png", 12, "Mini web: tipos de habitación y plano (datos ficticios)")
imagen(d, CAPT / "web_plano_planta.png", 12, "Mini web: plano dibujado de la planta 1 con camas y vista al mar (datos ficticios)")
imagen(d, CAPT / "web_04_datos_con_temporizador.png", 12, "Bloqueo con reloj y datos del huésped con consentimiento")
imagen(d, CAPT / "web_07_pasarela_simulada.png", 12, "Pasarela simulada: MODO PRUEBAS, no se cobra dinero")
imagen(d, CAPT / "web_08_confirmacion.png", 12, "Confirmación con número de reserva y correo simulado")
d.add_heading(lim("5.2 Qué pasa si el cliente no paga a tiempo"), 2)
lista(d, ["Si el reloj llega a cero sin pago, la habitación se libera sola: la reserva pasa a «Cancelada» con el motivo «Opción vencida: se liberó automáticamente» y el bloqueo web queda «El bloqueo venció».",
          "Lo mismo ocurre con las «opciones» que crea recepción: ahora vencen a las 48 horas (antes no vencían nunca). Las opciones antiguas, que no tienen fecha de vencimiento, no se tocan.",
          "La liberación se hace de dos maneras: al consultar disponibilidad (siempre al día) y con una tarea programada cada 5 minutos en GitHub Actions. GitHub puede retrasar esa tarea unos minutos; por eso la primera es la que garantiza que no haya doble venta.",
          "Si el cliente paga justo después de vencer, el sistema intenta recuperar las mismas habitaciones; si ya no están libres, deja el pago en «Requiere revisión» y el personal lo gestiona (devolución o cambio)."])
d.add_heading(lim("5.3 Lo que ve el personal en el PMS"), 2)
lista(d, ["Menú «🌐 Reservas web» (recepción y gerencia): una fila por reserva web con estado, reserva del PMS, huésped, habitación, total, pagado, estado del pago, referencia, hora de vencimiento y estado del correo. El botón «Liberar vencidas ahora» fuerza la liberación.",
          "En «Reservas» las reservas web aparecen con canal «web» y la columna «Vence» muestra cuándo vence cada opción. También se ven en Calendario y Plano.",
          "Mientras el cliente completa sus datos, el huésped figura como «Cliente web (datos pendientes)». Al enviar sus datos se crea el huésped real con su consentimiento registrado.",
          "El pago aprobado queda registrado en la cuenta de la reserva (método «pasarela») y en Facturación."])
imagen(d, CAPT / "pms_reservas_web.png", 15.5, "PMS → «Reservas web» (datos ficticios)")
imagen(d, CAPT / "pms_reservas_canal_web.png", 15.5, "PMS → «Reservas» con canal web y columna «Vence»")
d.add_heading(lim("5.4 Cómo ponerla en la página web del hotel"), 2)
lista(d, ["Opción rápida (enlace): un botón «Reservar» que apunte a https://pms-reservas-atm.streamlit.app/?hotel=ID (ID = número del hotel en el PMS).",
          "Opción incrustada (iframe): pegar en la página del hotel <iframe src=\"https://pms-reservas-atm.streamlit.app/?embed=true&hotel=ID\" width=\"100%\" height=\"900\" style=\"border:0\" title=\"Reservas\"></iframe>. Con embed=true se ocultan la barra y el pie de Streamlit.",
          "En celular conviene usar una altura de 1100 px o abrir el enlace en pestaña nueva.",
          "La página del hotel debe usar https. Si el hotel usa un constructor web (Wix, WordPress…), usa el bloque «Incrustar HTML».",
          "Si la mini web estuvo unas horas sin visitas, Streamlit la «duerme» y la primera carga tarda unos segundos."])
d.add_heading(lim("5.5 Qué es real y qué es simulado en este prototipo"), 2)
tabla(d, ["Parte", "Estado"], [
    ["Disponibilidad, bloqueo de 15 min, no doble venta, vencimiento", "REAL (misma base y mismas reglas que el PMS)"],
    ["Reserva en el PMS con canal web, huésped y consentimiento", "REAL (con datos ficticios)"],
    ["Pasarela de pagos", "SIMULADA: no se cobra. Está preparada para cambiar a Wompi sin tocar el resto"],
    ["Correo de confirmación", "SIMULADO: se guarda la plantilla y se muestra en pantalla; no se envía a nadie"],
    ["Verificación anti-robots y límites por dirección", "Sencillos (suma + máximo de bloqueos por hora); no es un captcha comercial"],
    ["Recibir avisos reales de la pasarela (webhook)", "Pendiente de la fase 2: requiere un receptor externo (Streamlit no recibe webhooks)"]], anchos=[8, 8.5])
salto(d)

d.add_heading(lim("Preguntas frecuentes"), 1)
tabla(d, ["Pregunta", "Respuesta"], [
    ["No me deja guardar la reserva.", "Lee el mensaje rojo: puede que no haya habitación libre, que las fechas estén mal o que falte el consentimiento del huésped."],
    ["No veo una pantalla que mi compañero sí ve.", "El menú depende del rol. Es normal."],
    ["Olvidé mi contraseña.", "Pide al administrador una contraseña temporal nueva. Ingresas con ella y creas otra propia."],
    ["Me pide «Crea tu contraseña nueva» y no me deja avanzar.", "Es lo esperado en el primer ingreso o tras recibir una temporal nueva: crea la contraseña (mínimo 10 caracteres, distinta de la temporal). Hasta entonces no se abre ninguna otra pantalla."],
    ["Me bloquearon el acceso.", "Fueron 5 intentos fallidos. Espera 15 minutos o pídele al administrador que revise tu usuario."],
    ["En el plano no puedo elegir una habitación.", "Solo se pueden elegir las verdes (disponibles). Revisa la leyenda: puede estar ocupada, en opción, bloqueada, fuera de servicio o no caber las personas que indicaste."],
    ["Elegí una habitación y desapareció la selección.", "Cambiaron las fechas, las personas o el estado de esa habitación (por ejemplo, otra persona la reservó). Elige de nuevo."],
    ["¿El correo de confirmación sale de verdad?", "No. Es una simulación y la pantalla lo avisa (también en la mini web)."],
    ["¿La mini web cobra de verdad?", "No. La pasarela es simulada y dice «MODO PRUEBAS: no se cobra dinero». No se piden tarjetas."],
    ["Un cliente bloqueó una habitación y no pagó. ¿Qué pasa?", "A los 15 minutos se libera sola. En «Reservas web» puedes pulsar «Liberar vencidas ahora»."],
    ["Una opción mía no vence.", "Solo vencen (a las 48 h) las opciones creadas desde esta versión. Las anteriores no tienen fecha de vencimiento: cancélalas o confírmalas a mano."],
    ["¿Puedo usar el comprobante como factura?", "No. Es solo un comprobante de cuenta del piloto."],
    ["¿Los datos son reales?", "No. Todo es ficticio. No cargues datos reales de personas en el piloto."]], anchos=[6, 10.5])
ruta, pdf = guardar_y_pdf(d, "instructivo-pms-por-rol")
print(ruta, pdf)

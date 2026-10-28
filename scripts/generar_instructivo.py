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
D["admin"] = diagrama("flujo_admin", ["Crear hotel\n(país y moneda)", "Impuestos\n(nombre y %)", "Tipos de\nhabitación", "Habitaciones\ny camas", "Usuarios\ny roles"], cols=5, alto=1.3, ancho=11)

d = nuevo_documento("Instructivo por rol", "PMS hotelero (piloto) · recepción, gerencia, housekeeping y administrador")
parrafo(d, "Versión 1.0 · 28 de octubre de 2026 · Preparado para ATm Consulting, Colombia", color=GRIS, tam=10)
nota(d, "Todos los datos del piloto son ficticios (hoteles, huéspedes, reservas, pagos). Los correos de confirmación, los pagos y las conexiones "
        "con otras plataformas están simulados: la pantalla siempre lo avisa. El comprobante PDF NO es una factura legal.", "Importante")
salto(d)

d.add_heading(lim("Cómo usar este instructivo"), 1)
parrafo(d, "Cada capítulo explica, con pasos cortos, lo que puede hacer una persona según su rol. Busca el tuyo y sigue los pasos. "
           "Los cuadros amarillos son avisos importantes.")
d.add_heading(lim("Entrar a la aplicación"), 2)
lista(d, ["Abre el enlace de la aplicación que te entregó ATm Consulting.",
          "Escribe tu correo y tu contraseña y pulsa «Ingresar». Tus datos de acceso te los entrega ATm Consulting aparte; no los compartas.",
          "Si te equivocas 5 veces seguidas, el acceso se bloquea 15 minutos. Es una medida de seguridad.",
          "Tu sesión dura 8 horas. Si recargas la página (F5) no te saca. Para salir, usa «Cerrar sesión» en el menú de la izquierda.",
          "Si trabajas en varios hoteles, elige el hotel en el menú de la izquierda. Cada hotel muestra sus precios en su moneda."], numerada=True)
d.add_heading(lim("Qué ve cada rol"), 2)
tabla(d, ["Pantalla", "Recepción", "Gerencia", "Housekeeping", "Administrador"], [
    ["Dashboard del día", "Usa", "Usa", "—", "Ver"], ["Calendario", "Usa", "Usa", "—", "Ver"],
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
          "Paso 2: elige tipo de habitación, fechas de entrada y salida, adultos y niños. «Estado inicial» puede ser consulta, opción o confirmada.",
          "Paso 3: revisa el desglose por noche, los impuestos del hotel y el total. El precio de cada noche queda congelado al guardar.",
          "Pulsa «Guardar reserva». El sistema asigna una habitación libre. Si no hay, te avisa en rojo y no guarda nada.",
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
salto(d)

# ---------- GERENCIA ----------
d.add_heading(lim("2. Gerencia"), 1)
parrafo(d, "Gerencia hace todo lo de recepción y además aprueba, cambia tarifas y ve los reportes.")
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
    ["🚪 Habitaciones y camas", "Cada habitación con su planta, tipo, vista y camas. El piloto trae una distribución de prueba provisional de 18 habitaciones (3 plantas × 6)."],
    ["👤 Usuarios", "Crear usuarios, asignarles rol y hotel, cambiar contraseña o desactivarlos."]], anchos=[4.5, 12])
d.add_heading(lim("4.2 Otras tareas"), 2)
lista(d, ["Bloqueos y tarifas: igual que gerencia (ver capítulo 2).", "Reportes: igual que gerencia.",
          "Auditoría: consultar quién hizo qué.", "Dashboard, calendario, reservas, huéspedes y facturación: solo consulta."])
nota(d, "Los cambios de impuestos solo afectan a las líneas nuevas: las ya cobradas conservan el porcentaje con el que se cobraron.")
imagen(d, CAPT / "admin_configuracion.png", 15.5, "Configuración (datos ficticios)")
salto(d)

d.add_heading(lim("Preguntas frecuentes"), 1)
tabla(d, ["Pregunta", "Respuesta"], [
    ["No me deja guardar la reserva.", "Lee el mensaje rojo: puede que no haya habitación libre, que las fechas estén mal o que falte el consentimiento del huésped."],
    ["No veo una pantalla que mi compañero sí ve.", "El menú depende del rol. Es normal."],
    ["Me bloquearon el acceso.", "Fueron 5 intentos fallidos. Espera 15 minutos o pídele al administrador que revise tu usuario."],
    ["¿El correo de confirmación sale de verdad?", "No. Es una simulación y la pantalla lo avisa."],
    ["¿Puedo usar el comprobante como factura?", "No. Es solo un comprobante de cuenta del piloto."],
    ["¿Los datos son reales?", "No. Todo es ficticio. No cargues datos reales de personas en el piloto."]], anchos=[6, 10.5])
ruta, pdf = guardar_y_pdf(d, "instructivo-pms-por-rol")
print(ruta, pdf)

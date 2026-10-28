"""Genera la guía de pruebas por escenarios (Word + PDF) y la lista de chequeo en Excel (.xlsx)."""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from docs_comun import *  # noqa
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

U = {"rec": "recepcion1.col@pms-demo.test", "rec2": "recepcion2.col@pms-demo.test", "ger1": "gerencia1.col@pms-demo.test",
     "ger2": "gerencia2.col@pms-demo.test", "hk1": "housekeeping1.col@pms-demo.test", "hk2": "housekeeping2.col@pms-demo.test",
     "adm": "admin@pms-demo.test"}
# (id, grupo, título, usuario, pasos, esperado)
E = [
 ("E01", "Acceso", "Ingreso correcto y contraseña mala", U["rec"],
  ["Abre la aplicación.", "Escribe un correo válido con una contraseña equivocada y pulsa Ingresar.", "Ingresa con la contraseña correcta."],
  "Con la contraseña mala sale un mensaje claro y no entra. Con la correcta entra y ve el menú de recepción."),
 ("E02", "Acceso", "Bloqueo por intentos fallidos", U["hk2"],
  ["Falla la contraseña 5 veces seguidas.", "Intenta entrar con la contraseña correcta."],
  "Después del 5.º fallo avisa que el acceso está bloqueado unos minutos, aunque la contraseña sea correcta. Queda en Auditoría (ingresar como gerencia para verlo)."),
 ("E03", "Acceso", "La sesión sobrevive a recargar la página", U["rec"],
  ["Ingresa.", "Pulsa F5 (recargar).", "Cambia de pantalla varias veces y recarga otra vez."],
  "No pide ingresar de nuevo. Sigue en la misma pantalla y en el mismo hotel."),
 ("E04", "Acceso", "Sin acceso de demostración abierto", "—",
  ["Mira la pantalla de ingreso de la dirección de producción."],
  "No aparecen botones de «entrar sin contraseña». Solo correo y contraseña."),
 ("E05", "Roles", "Cada rol ve solo lo suyo", f"{U['rec']}, {U['ger1']}, {U['hk1']}, {U['adm']}",
  ["Ingresa con cada usuario y revisa el menú de la izquierda.", "Compara con la tabla de permisos del instructivo."],
  "Recepción no ve Reportes, Configuración ni Auditoría. Housekeeping solo ve Housekeeping y Bloqueos y no ve precios. Gerencia ve Reportes. Administrador ve Configuración."),
 ("E06", "Roles", "Un hotel no ve datos de otro", U["rec"],
  ["Ingresa con recepción de un hotel.", "Revisa el selector de hotel."],
  "Solo aparece su hotel. Las reservas y huéspedes son solo de ese hotel."),
 ("E07", "Reservas", "Crear una reserva normal", U["rec"],
  ["Reservas → Nueva reserva.", "Elige un huésped con consentimiento, tipo Doble matrimonial, 3 noches desde la semana próxima.", "Revisa el desglose y guarda."],
  "Se crea con código, habitación asignada, 3 noches con precio, impuestos del hotel y total. Aparece en la Lista y en el Calendario."),
 ("E08", "Reservas", "No se puede vender dos veces la misma habitación", U["rec"],
  ["Reserva todas las habitaciones de un tipo para unas fechas (hay 9 Dobles matrimoniales por hotel: 3 por planta).", "Intenta una más para las mismas fechas."],
  "Al agotarse el tipo, el sistema avisa «no hay disponibilidad» y no guarda. Nunca hay dos reservas en la misma habitación y noche."),
 ("E09", "Reservas", "Precio congelado por noche", f"{U['rec']} y {U['ger1']}",
  ["Con recepción, crea una reserva y anota el precio por noche.", "Con gerencia, cambia la tarifa de ese tipo (Tarifas).", "Vuelve a la reserva (Gestionar → Noches y precio congelado).", "Crea otra reserva igual."],
  "La primera reserva conserva su precio. La segunda usa el precio nuevo."),
 ("E10", "Reservas", "Modificar fechas de una reserva", U["rec"],
  ["Gestionar una reserva → Cambiar fechas → agrega una noche.", "Intenta mover a fechas sin disponibilidad."],
  "Las noches antiguas conservan precio y la nueva usa la tarifa vigente. Si no hay habitación, avisa y no cambia nada."),
 ("E11", "Reservas", "Falta el consentimiento (Ley 1581)", U["rec"],
  ["Crea un huésped nuevo sin registrar consentimiento.", "Intenta reservarle."],
  "Avisa que falta el consentimiento. Con el consentimiento registrado, deja continuar."),
 ("E12", "Impuestos", "Impuestos distintos por hotel", "recepcion1.col@pms-demo.test, recepcion1.rd@pms-demo.test, recepcion1.pe@pms-demo.test",
  ["Con la recepción de cada uno de los 3 hoteles, crea una reserva igual (mismo tipo y 2 noches).", "Compara las líneas de impuestos y la moneda."],
  "Colombia en COP con su impuesto de ejemplo; República Dominicana en DOP con dos cargos; el tercer país en PEN. Cada total usa el % de su hotel."),
 ("E13", "Estancia", "Check-in y check-out", U["rec"],
  ["Toma una reserva confirmada para hoy y pulsa Hacer check-in.", "Intenta check-in de una reserva de otra fecha.", "Con saldo pendiente, pulsa Hacer check-out.", "Registra el pago y vuelve a pulsar check-out."],
  "El check-in de otra fecha se rechaza. Con saldo pendiente el check-out se rechaza. Pagado, el check-out funciona y la habitación queda Sucia."),
 ("E14", "Estancia", "Salida forzada con saldo (solo gerencia)", U["ger1"],
  ["Con una reserva alojada con saldo, ingresa como gerencia.", "Pulsa Forzar salida con saldo."],
  "La salida se hace y queda registrada en Auditoría. Recepción no tiene ese botón."),
 ("E15", "Estancia", "Marcar no-show", U["rec"],
  ["Toma una reserva confirmada cuya entrada ya pasó.", "Pulsa Marcar no-show."],
  "Pasa a «No se presentó» y la habitación queda libre en el calendario."),
 ("E16", "Aprobaciones", "Cancelar requiere gerencia", f"{U['rec']}, {U['ger1']}, {U['ger2']}",
  ["Recepción solicita la cancelación con un motivo.", "Gerencia 1 revisa en Cancelaciones pendientes y aprueba.", "Repite: Gerencia 1 solicita una cancelación e intenta aprobarla él mismo.", "Aprueba con Gerencia 2."],
  "Recepción no puede cancelar sola. Quien pide la cancelación no puede aprobarla; otra persona de gerencia sí. Todo queda en Auditoría."),
 ("E17", "Aprobaciones", "Descuento requiere gerencia", f"{U['rec']}, {U['ger1']}",
  ["Recepción solicita un descuento del 10 % con motivo.", "Mira el total (no debe cambiar).", "Gerencia aprueba en Descuentos pendientes."],
  "El descuento pendiente no cambia el total. Al aprobar, el total baja. Un descuento mayor que los cargos se rechaza."),
 ("E18", "Facturación", "Extras, pagos y anulaciones", U["rec"],
  ["Agrega un extra con cantidad y precio.", "Registra un pago parcial en efectivo.", "Anula el pago con motivo."],
  "El saldo cambia en cada paso. Las líneas anuladas quedan visibles como anuladas, no se borran."),
 ("E19", "Facturación", "Comprobante PDF", U["rec"],
  ["Abre la cuenta de una reserva con cargos y pagos.", "Descarga el comprobante en PDF."],
  "El PDF muestra cargos, impuestos, pagos y saldo en la moneda del hotel, y dice claramente que NO es una factura legal."),
 ("E20", "Housekeeping", "Flujo de limpieza", U["hk1"],
  ["Entra a Housekeeping y filtra las Sucias.", "Pasa una a En limpieza y luego a En inspección.", "Intenta darla por Lista con el mismo usuario.", "Hazlo con Housekeeping 2."],
  "El mismo usuario no puede dar por lista la habitación que pasó a inspección. Otro usuario sí."),
 ("E21", "Housekeeping", "Housekeeping no ve precios ni pagos", U["hk1"],
  ["Revisa todas las pantallas del menú de housekeeping."],
  "No hay precios, pagos ni datos personales de huéspedes en ninguna pantalla."),
 ("E22", "Housekeeping", "Fuera de servicio pide nota y check-in exige habitación lista", f"{U['hk1']} y {U['rec']}",
  ["Pasa una habitación a Fuera de servicio sin escribir nota.", "Repite con nota.", "Intenta hacer check-in en una habitación que no esté Lista."],
  "Sin nota no deja. Con nota queda fuera de servicio. El check-in en habitación no lista se rechaza."),
 ("E23", "Bloqueos", "Bloquear una habitación", U["ger1"],
  ["Bloqueos → Nuevo bloqueo con motivo y fechas.", "Intenta reservar ese tipo en esas fechas.", "Intenta bloquear una habitación con noches ya vendidas."],
  "La habitación bloqueada no se vende. Bloquear noches vendidas se rechaza con un mensaje que cita la reserva."),
 ("E24", "Calendario", "Calendario de solo lectura", U["rec"],
  ["Abre Calendario.", "Intenta arrastrar o hacer clic en una barra de reserva."],
  "Muestra habitaciones por días con colores por estado. No permite cambiar nada; los cambios se hacen en Reservas."),
 ("E25", "Resultados", "Dashboard del día", U["rec"],
  ["Abre el Dashboard del día.", "Haz clic en los enlaces de una llegada y de una habitación sucia."],
  "Muestra llegadas, salidas, ocupación y limpieza del día. Los enlaces llevan directo a la reserva o a Housekeeping."),
 ("E26", "Resultados", "Reportes de ocupación e ingresos", f"{U['ger1']} y {U['adm']}",
  ["Abre Reportes con un rango de fechas.", "Descarga el CSV.", "Repite con admin@pms-demo.test y cambia de hotel en el menú."],
  "Gráficos y tabla por mes en la moneda del hotel. El CSV abre en Excel. Al cambiar de hotel cambian cifras y moneda."),
 ("E27", "Datos", "Huésped: consentimiento y anonimizar", U["rec"],
  ["Registra y luego revoca un consentimiento.", "Anonimiza un huésped de prueba marcando la casilla de confirmación."],
  "Se registra cada cambio. Tras anonimizar, el nombre y los datos personales desaparecen y las reservas se conservan."),
 ("E28", "Administración", "Configurar hotel, impuestos y habitaciones", U["adm"],
  ["Crea un hotel nuevo con otra moneda.", "Agrega un impuesto con nombre y %.", "Crea un tipo de habitación y una habitación con camas."],
  "El hotel nuevo aparece en el selector, con su moneda. La habitación se puede reservar."),
 ("E29", "Administración", "Usuarios", U["adm"],
  ["Crea un usuario de recepción.", "Desactívalo e intenta ingresar con él.", "Cambia su contraseña."],
  "El usuario desactivado no entra. La contraseña nueva funciona. Nunca se muestra ninguna contraseña guardada."),
 ("E30", "Seguridad", "Auditoría", U["ger1"],
  ["Haz varias acciones (reserva, cancelación, descuento).", "Abre Auditoría."],
  "Cada acción aparece con quién, cuándo y qué. No hay botones para editar ni borrar."),
 ("E31", "Avisos", "Avisos de datos ficticios y simulaciones", U["rec"],
  ["Recorre todas las pantallas.", "Usa «Simular envío de confirmación» y registra un pago."],
  "Siempre hay un aviso visible de datos ficticios. Correos, pagos e integraciones dicen claramente que son simulados. Abajo aparece «Prototipo diseñado para ATm Consulting» con el logo."),
 ("E32", "Aspecto", "Fondo blanco y uso en pantalla pequeña", U["rec"],
  ["Mira varias pantallas en computador.", "Repite en el celular o con la ventana angosta."],
  "Fondo blanco y limpio, textos legibles, sin elementos cortados."),
]

# ---------- Word ----------
d = nuevo_documento("Guía de pruebas por escenarios", "PMS hotelero (piloto) · qué probar, cómo y qué debe pasar")
parrafo(d, "Versión 1.0 · 28 de octubre de 2026 · Preparado para ATm Consulting, Colombia", color=GRIS, tam=10)
nota(d, "Todo es ficticio y las confirmaciones, los pagos y las integraciones están simuladas. Marca los resultados en el archivo Excel «checklist-pruebas-pms.xlsx».", "Importante")
salto(d)
d.add_heading("Cómo probar", 1)
lista(d, ["Pide a ATm Consulting el enlace de la aplicación y las contraseñas de los usuarios de prueba (se entregan aparte).",
          "Hay 3 hoteles ficticios: Colombia (COP), República Dominicana (DOP) y otro país (PEN). Cada uno tiene 18 habitaciones y usuarios de recepción, gerencia y housekeeping.",
          "Los correos de los usuarios tienen esta forma: recepcion1.col@pms-demo.test, gerencia2.rd@pms-demo.test, housekeeping1.pe@pms-demo.test. El administrador es admin@pms-demo.test.",
          "Haz los escenarios en orden. Para cada uno, marca en el Excel «Pasó», «Falló» o «No aplica» y escribe lo que viste si falló.",
          "Si algo falla, anota: escenario, usuario, hotel, qué hiciste, qué esperabas y qué pasó (si puedes, una captura de pantalla)."], numerada=True)
d.add_heading("Usuarios de prueba", 2)
tabla(d, ["Rol", "Correo de ejemplo (hotel Colombia)", "Para qué sirve"], [
    ["Recepción", "recepcion1.col@pms-demo.test / recepcion2.col@pms-demo.test", "Reservas, check-in/out, cobros, huéspedes"],
    ["Gerencia", "gerencia1.col@pms-demo.test / gerencia2.col@pms-demo.test", "Aprobar cancelaciones y descuentos, tarifas, reportes (dos personas para probar la separación de funciones)"],
    ["Housekeeping", "housekeeping1.col@pms-demo.test / housekeeping2.col@pms-demo.test", "Tablero de limpieza"],
    ["Administrador", "admin@pms-demo.test", "Configuración de hoteles, impuestos, habitaciones y usuarios"]], anchos=[3, 7.5, 6])
d.add_heading("Mapa de escenarios", 2)
tabla(d, ["Grupo", "Escenarios"], [[g, ", ".join(e[0] for e in E if e[1] == g)] for g in dict.fromkeys(e[1] for e in E)], anchos=[4, 12])
imagen(d, diagrama("flujo_prueba", ["Probar\nel escenario", "¿Pasó lo\nesperado?", "Marcar en\nel Excel", "Si falló:\nanotar y\nreportar"], colores={2: "#e6f4ea", 3: "#fff3e0"}, cols=4, alto=1.3, ancho=10), 14)
salto(d)
grupo = None
for (i, g, t, u, pasos, esp) in E:
    if g != grupo:
        d.add_heading(lim(g), 1); grupo = g
    d.add_heading(f"{i} · {lim(t)}", 3)
    parrafo(d, f"Usuario: {u}", cursiva=True, color=GRIS, tam=10)
    parrafo(d, "Pasos:", negrita=True)
    lista(d, pasos, numerada=True)
    nota(d, esp, "Debe pasar")
ruta, pdf = guardar_y_pdf(d, "guia-de-pruebas-pms")
print(ruta, pdf)

# ---------- Excel ----------
wb = Workbook(); ws = wb.active; ws.title = "Checklist"
cab = ["ID", "Grupo", "Escenario", "Usuario(s)", "Pasos", "Resultado esperado", "Resultado", "Observaciones", "Fecha", "Responsable"]
ws.append(["PMS hotelero (piloto) · Checklist de pruebas · Prototipo diseñado para ATm Consulting · datos 100 % ficticios"])
ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(cab)); ws["A1"].font = Font(bold=True, size=13, color="1F3A5F")
ws.append([]); ws.append(cab)
borde = Border(*(Side(style="thin", color="BBBBBB"),) * 4)
for c in range(1, len(cab) + 1):
    x = ws.cell(row=3, column=c); x.font = Font(bold=True); x.fill = PatternFill("solid", fgColor="E8F0FE"); x.border = borde
    x.alignment = Alignment(wrap_text=True, vertical="center")
for (i, g, t, u, pasos, esp) in E:
    ws.append([i, lim(g), lim(t), u, "\n".join(f"{n}. {lim(p)}" for n, p in enumerate(pasos, 1)), esp, "Pendiente", "", "", ""])
for r in range(4, 4 + len(E)):
    for c in range(1, len(cab) + 1):
        x = ws.cell(row=r, column=c); x.alignment = Alignment(wrap_text=True, vertical="top"); x.border = borde
for c, a in enumerate([7, 14, 30, 30, 55, 50, 12, 35, 12, 18], 1):
    ws.column_dimensions[get_column_letter(c)].width = a
dv = DataValidation(type="list", formula1='"Pendiente,Pasó,Falló,No aplica"', allow_blank=False); ws.add_data_validation(dv)
dv.add(f"G4:G{3 + len(E)}")
from openpyxl.formatting.rule import CellIsRule
rango = f"G4:G{3 + len(E)}"
ws.conditional_formatting.add(rango, CellIsRule(operator="equal", formula=['"Pasó"'], fill=PatternFill("solid", bgColor="C8E6C9")))
ws.conditional_formatting.add(rango, CellIsRule(operator="equal", formula=['"Falló"'], fill=PatternFill("solid", bgColor="FFCDD2")))
ws.conditional_formatting.add(rango, CellIsRule(operator="equal", formula=['"Pendiente"'], fill=PatternFill("solid", bgColor="FFF9C4")))
ws.freeze_panes = "D4"; ws.auto_filter.ref = f"A3:{get_column_letter(len(cab))}{3 + len(E)}"
res = wb.create_sheet("Resumen")
res.append(["Resumen automático"]); res["A1"].font = Font(bold=True, size=13, color="1F3A5F"); res.append([])
n = 3 + len(E)
for k in ("Pendiente", "Pasó", "Falló", "No aplica"):
    res.append([k, f'=COUNTIF(Checklist!G4:G{n},"{k}")'])
res.append(["Total", f"=COUNTA(Checklist!A4:A{n})"]); res.append(["% que pasó", f'=IFERROR(COUNTIF(Checklist!G4:G{n},"Pasó")/(COUNTA(Checklist!A4:A{n})-COUNTIF(Checklist!G4:G{n},"No aplica")),0)'])
res["B9"].number_format = "0%"; res.column_dimensions["A"].width = 18
lee = wb.create_sheet("Cómo usar")
for l in ["1. Pide a ATm Consulting el enlace y las contraseñas de prueba (se entregan aparte).",
          "2. Haz cada escenario siguiendo la guía de pruebas (Word/PDF) o la columna Pasos.",
          "3. En la columna Resultado elige Pasó, Falló o No aplica.",
          "4. Si falló, escribe en Observaciones qué viste. Anota fecha y tu nombre.",
          "5. La hoja Resumen cuenta los resultados sola.",
          "Recuerda: todos los datos son ficticios; correos, pagos e integraciones son simulados."]:
    lee.append([l])
lee.column_dimensions["A"].width = 100
wb.save(DOCS / "checklist-pruebas-pms.xlsx")
print("xlsx ok", len(E), "escenarios")

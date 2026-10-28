import streamlit as st

import ui
from pms import reservas, vistas
from pms.util import hoy_hotel

A, H = ui.actor(), ui.hotel()
ui.encabezado("🗓️ Calendario de ocupación", "Rejilla de solo lectura. Las reservas se crean o cambian desde el formulario de Reservas.")
c1, c2, _ = st.columns([1, 1, 2])
desde = c1.date_input("Desde", value=hoy_hotel(None, H["id"]), key="pms_cal_desde", format="DD/MM/YYYY")
dias = c2.selectbox("Días a mostrar", [7, 14, 21, 30], index=1, key="pms_cal_dias")
cal = vistas.calendario(A, H["id"], desde, dias)

leyenda = " ".join(ui.chip(n, k) for k, n in {"opcion": "Opción", "confirmada": "Confirmada", "alojado": "Alojado",
                                               "salida": "Salida hecha", "bloqueo": "Bloqueo"}.items())
st.markdown(f"**Leyenda:** {leyenda} <span class='pms-chip' style='background:#fff;color:#52606d;border-color:#d9e2ec'>Libre</span>",
            unsafe_allow_html=True)

DIAS = ["lu", "ma", "mi", "ju", "vi", "sá", "do"]
h = "<div style='overflow-x:auto'><table class='pms-cal'><tr><th>Hab.</th><th>Tipo</th>"
for f in cal["fechas"]:
    h += f"<th>{DIAS[f.weekday()]}<br>{f:%d/%m}</th>"
h += "</tr>"
planta = None
for hab in cal["habitaciones"]:
    if hab["planta"] != planta:
        planta = hab["planta"]
        h += f"<tr><td colspan='{len(cal['fechas']) + 2}' style='background:#f4f6f8;text-align:left'><b>Piso {planta}</b></td></tr>"
    h += f"<tr><td class='hab'>{hab['numero']}</td><td style='text-align:left'>{hab['tipo']}</td>"
    for f in cal["fechas"]:
        c = cal["celdas"].get((hab["id"], f))
        if c:
            fondo, tinta = ui.COLOR_RESERVA[c["estado"]]
            nombre = reservas.ESTADOS_NOMBRE.get(c["estado"], "Bloqueo")
            h += f"<td style='background:{fondo};color:{tinta}' title='{c['codigo']} · {nombre}'>{c['texto'][:9]}</td>"
        else:
            h += "<td></td>"
    h += "</tr>"
h += "</table></div>"
st.markdown(h, unsafe_allow_html=True)
st.caption("Pasa el cursor sobre una celda para ver el código de la reserva.")
if ui.puede("reservas"):
    ui.enlace("reservas", "Crear o cambiar una reserva →")

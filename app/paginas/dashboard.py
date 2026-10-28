import datetime as dt

import streamlit as st

import ui
from pms import reservas, vistas
from pms.housekeeping import NOMBRE as HK_NOMBRE
from pms.util import hoy_hotel

A, H = ui.actor(), ui.hotel()
ui.encabezado("📊 Dashboard del día", f"{H['nombre']} · hoy es {ui.f_fecha(hoy_hotel(None, H['id']))}")
d = vistas.dashboard(A, H["id"])

# alertas con enlace directo
if d["cancelaciones_pendientes"] or d["descuentos_pendientes"]:
    with st.container(border=True):
        st.markdown(f"⏳ **Pendientes de aprobación de gerencia:** {d['cancelaciones_pendientes']} cancelación(es) · "
                    f"{d['descuentos_pendientes']} descuento(s).")
        c1, c2 = st.columns(2)
        with c1:
            if d["cancelaciones_pendientes"] and ui.puede("reservas"):
                ui.enlace("reservas", "Ir a cancelaciones pendientes →")
        with c2:
            if d["descuentos_pendientes"] and ui.puede("facturacion"):
                ui.enlace("facturacion", "Ir a descuentos pendientes →")
sucias = d["hk"].get("sucia", 0)
if sucias and ui.puede("housekeeping"):
    ui.enlace("housekeeping", f"{sucias} habitación(es) sucia(s) por limpiar →")

c = st.columns(5)
c[0].metric("Ocupación hoy", f"{d['ocupacion_pct']} %")
c[1].metric("Habitaciones ocupadas", d["ocupadas_hoy"])
c[2].metric("Reservas alojadas", d["en_casa"])
c[3].metric("Alojamiento hoy", ui.dinero(d["ingresos_dia"]))
c[4].metric("Cobros de hoy", ui.dinero(d["cobros_dia"]))
st.caption("Alojamiento: noches del día sin impuestos. Cobros: pagos registrados hoy (simulados).")

l, s = st.columns(2)
with l:
    st.subheader(f"Llegadas de hoy ({len(d['llegadas'])})")
    if d["llegadas"]:
        st.dataframe([{"Reserva": x["codigo"], "Huésped": x["huesped"], "Tipo": x["tipo"], "Habitación": x["habitacion"] or "—",
                       "Estado": reservas.ESTADOS_NOMBRE[x["estado"]], "Salida": ui.f_fecha(x["fecha_salida"])} for x in d["llegadas"]],
                     hide_index=True, width="stretch")
        if ui.puede("reservas"):
            ui.enlace("reservas", "Hacer check-in en Reservas →")
    else:
        st.info("No hay llegadas hoy.")
with s:
    st.subheader(f"Salidas de hoy ({len(d['salidas'])})")
    if d["salidas"]:
        st.dataframe([{"Reserva": x["codigo"], "Huésped": x["huesped"], "Tipo": x["tipo"], "Estado": reservas.ESTADOS_NOMBRE[x["estado"]],
                       "Salida": ui.f_fecha(x["fecha_salida"])} for x in d["salidas"]], hide_index=True, width="stretch")
        if ui.puede("reservas"):
            ui.enlace("reservas", "Hacer check-out en Reservas →")
    else:
        st.info("No hay salidas hoy.")

if ui.puede("housekeeping"):
    st.subheader("Estado de limpieza")
    for col, (k, n) in zip(st.columns(5), HK_NOMBRE.items()):
        col.metric(n, d["hk"].get(k, 0))

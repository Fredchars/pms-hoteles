import datetime as dt

import streamlit as st

import ui
from pms import bloqueos, config
from pms.util import hoy_hotel

A, H = ui.actor(), ui.hotel()
ui.encabezado("🚧 Bloqueos", "Saca una habitación de la venta por mantenimiento u otro motivo. No se puede bloquear una noche ya vendida.")
EDITA = ui.puede("bloqueos", True)
hoy = hoy_hotel(None, H["id"])

lista = bloqueos.listar(A, H["id"])
st.subheader(f"Bloqueos activos ({len(lista)})")
if not lista:
    st.info("No hay bloqueos activos.")
for b in lista:
    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"**Hab. {b['numero']}** · {ui.f_fecha(b['fecha_desde'])} → {ui.f_fecha(b['fecha_hasta'])} · {b['motivo']}")
        if EDITA and c2.button("Liberar", key=f"pms_bl_lib_{b['id']}"):
            ui.correr(bloqueos.liberar, A, b["id"], ok="Habitación liberada.")

if EDITA:
    st.subheader("Nuevo bloqueo")
    habs = config.habitaciones(H["id"])
    hab = st.selectbox("Habitación", habs, key="pms_bl_hab", format_func=lambda h: f"{h['numero']} · {h['tipo']}")
    c1, c2 = st.columns(2)
    d1 = c1.date_input("Desde", value=hoy, key="pms_bl_desde", format="DD/MM/YYYY")
    d2 = c2.date_input("Hasta (incluida)", value=hoy + dt.timedelta(days=2), key="pms_bl_hasta", format="DD/MM/YYYY")
    mot = st.text_input("Motivo", key="pms_bl_motivo")
    if st.button("Crear bloqueo", type="primary", key="pms_bl_crear"):
        ui.correr(bloqueos.crear, A, H["id"], hab["id"], d1, d2, mot, ok="Bloqueo creado.")
else:
    st.caption("Tu rol solo puede consultar los bloqueos.")

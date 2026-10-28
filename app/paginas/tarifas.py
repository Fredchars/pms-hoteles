import datetime as dt

import streamlit as st

import ui
from pms import config, tarifas
from pms.util import hoy_hotel

A, H = ui.actor(), ui.hotel()
ui.encabezado("💲 Tarifas", f"Precio por noche y tipo de habitación, en {H['moneda']} (moneda del hotel). Cambiar una tarifa no altera reservas ya hechas: sus precios están congelados.")
EDITA = ui.puede("tarifas", True)
if not EDITA:
    st.info("Tu rol solo puede consultar las tarifas.")

lista = tarifas.listar(H["id"])
st.dataframe([{"Tipo": t["tipo"], "Temporada": t["temporada"], "Desde": ui.f_fecha(t["fecha_desde"]), "Hasta": ui.f_fecha(t["fecha_hasta"]),
               "Precio por noche": ui.dinero(t["precio_noche"]), "Estancia mínima": t["estancia_minima"],
               "Venta cerrada": "Sí" if t["cierre_ventas"] else "No", "Activa": "Sí" if t["activo"] else "No"} for t in lista],
             hide_index=True, width="stretch")

if EDITA:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Editar una tarifa")
        t = st.selectbox("Tarifa", lista, key="pms_tf_sel", index=None, placeholder="Elige una tarifa",
                         format_func=lambda t: f"{t['tipo']} · {t['temporada']} · {ui.f_fecha(t['fecha_desde'])}→{ui.f_fecha(t['fecha_hasta'])}")
        if t:
            precio = st.number_input("Precio por noche", min_value=0.0, value=float(t["precio_noche"]), step=1000.0, key=f"pms_tf_p_{t['id']}")
            minimo = st.number_input("Estancia mínima (noches)", 1, 30, int(t["estancia_minima"]), key=f"pms_tf_m_{t['id']}")
            cierre = st.checkbox("Cerrar la venta", value=bool(t["cierre_ventas"]), key=f"pms_tf_c_{t['id']}")
            if st.button("Guardar tarifa", key=f"pms_tf_g_{t['id']}", type="primary"):
                ui.correr(tarifas.actualizar, A, t["id"], precio=precio, estancia_minima=int(minimo), cierre_ventas=cierre, ok="Tarifa actualizada.")
    with c2:
        st.subheader("Nueva tarifa")
        tipo = st.selectbox("Tipo de habitación", config.tipos(H["id"]), key="pms_tn_tipo", format_func=lambda x: x["nombre"])
        temp = st.text_input("Temporada (ej. alta)", key="pms_tn_temp")
        hoy = hoy_hotel(None, H["id"])
        d1 = st.date_input("Desde", value=hoy, key="pms_tn_desde", format="DD/MM/YYYY")
        d2 = st.date_input("Hasta (incluida)", value=hoy + dt.timedelta(days=90), key="pms_tn_hasta", format="DD/MM/YYYY")
        pr = st.number_input("Precio por noche", min_value=0.0, step=1000.0, key="pms_tn_precio")
        mn = st.number_input("Estancia mínima", 1, 30, 1, key="pms_tn_min")
        if st.button("Crear tarifa", key="pms_tn_crear"):
            ui.correr(tarifas.crear, A, H["id"], tipo["id"], temp, d1, d2, pr, int(mn), ok="Tarifa creada.")

import streamlit as st

import ui
from pms import housekeeping as hk

A, H = ui.actor(), ui.hotel()
ui.encabezado("🧹 Housekeeping", "Tablero de limpieza por estado. Cada habitación avanza con un botón; esta pantalla no muestra precios ni pagos.")
EDITA = ui.puede("housekeeping", True)
if not EDITA:
    st.info("Tu rol solo puede consultar el tablero.")

tab = hk.tablero(A, H["id"])
cols = st.columns(5)
for c, (k, n) in zip(cols, hk.NOMBRE.items()):
    c.metric(n, sum(1 for x in tab if x["estado_limpieza"] == k))

SIGUIENTE = {"sucia": ("en_limpieza", "▶ Empezar limpieza"), "en_limpieza": ("inspeccion", "✔ Pasar a inspección"),
             "inspeccion": ("lista", "✅ Aprobar: lista"), "lista": ("sucia", "↩ Marcar sucia"),
             "fuera_de_servicio": ("sucia", "↩ Volver a servicio (sucia)")}
filtro = st.multiselect("Mostrar estados", hk.ESTADOS, default=hk.ESTADOS, format_func=lambda e: hk.NOMBRE[e], key="pms_hk_filtro")
for planta in sorted({x["planta"] for x in tab}):
    st.markdown(f"#### Piso {planta}")
    hs = [x for x in tab if x["planta"] == planta and x["estado_limpieza"] in filtro]
    cols = st.columns(3)
    for i, x in enumerate(hs):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**Hab. {x['numero']}** · {x['tipo']} &nbsp; {ui.chip(hk.NOMBRE[x['estado_limpieza']], x['estado_limpieza'], ui.COLOR_HK)}",
                            unsafe_allow_html=True)
                st.caption(("🧳 Con huésped alojado · " if x["ocupada"] else "") + (f"Último: {x['ultima']}" if x["ultima"] else "Sin movimientos"))
                if EDITA:
                    nuevo, etiqueta = SIGUIENTE[x["estado_limpieza"]]
                    if st.button(etiqueta, key=f"pms_hk_n_{x['id']}"):
                        ui.correr(hk.mover, A, x["id"], nuevo, ok=f"Habitación {x['numero']}: {hk.NOMBRE[nuevo]}.")
                    with st.popover("Más opciones"):
                        opciones = sorted(hk.TRANSICIONES[x["estado_limpieza"]])
                        destino = st.selectbox("Cambiar a", opciones, key=f"pms_hk_d_{x['id']}", format_func=lambda e: hk.NOMBRE[e])
                        nota = st.text_input("Nota (obligatoria si queda fuera de servicio)", key=f"pms_hk_t_{x['id']}")
                        if st.button("Aplicar cambio", key=f"pms_hk_a_{x['id']}"):
                            ui.correr(hk.mover, A, x["id"], destino, nota, ok=f"Habitación {x['numero']}: {hk.NOMBRE[destino]}.")

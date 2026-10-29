import datetime as dt

import streamlit as st

import ui
from pms import config, disponibilidad, plano
from pms.errores import ErrorNegocio
from pms.util import hoy_hotel

A, H = ui.actor(), ui.hotel()
ui.encabezado("🗺️ Plano de habitaciones", "Elige una habitación en el plano de cada planta. Los colores muestran su estado en las fechas escogidas.")
PUEDE_RESERVAR = ui.puede("reservas", True)
hoy = hoy_hotel(None, H["id"])
NOMBRES = disponibilidad.NOMBRE_ESTADO_PLANO


def _cambiar_hotel():
    st.session_state["pms_w_hotel"] = st.session_state["pms_pl_hotel"]      # el selector de la barra lateral manda; se sincroniza


def _elegir(hab_id: int):
    st.session_state["pms_pl_sel"] = hab_id


# ---------------- filtros ----------------
hoteles = config.hoteles_visibles(A)
st.session_state["pms_pl_hotel"] = H["id"]
for k, v in (("pms_pl_entrada", hoy), ("pms_pl_salida", hoy + dt.timedelta(days=2))):
    if st.session_state.get(k, v) < hoy:
        st.session_state[k] = v
f1, f2, f3, f4 = st.columns([3, 1.4, 1.4, 1.4])
f1.selectbox("Hotel", [h["id"] for h in hoteles], key="pms_pl_hotel", on_change=_cambiar_hotel, disabled=len(hoteles) <= 1,
             format_func=lambda i: ui.nombre_hotel(next(h for h in hoteles if h["id"] == i)))
entrada = f2.date_input("Entrada", value=hoy, min_value=hoy, key="pms_pl_entrada", format="DD/MM/YYYY")
salida = f3.date_input("Salida", value=hoy + dt.timedelta(days=2), min_value=hoy, key="pms_pl_salida", format="DD/MM/YYYY")
adultos = f4.number_input("Adultos", 1, 10, 2, key="pms_pl_adultos")
g1, g2, g3, g4, g5 = st.columns([1.1, 2.6, 2.2, 2.4, 1.6])
ninos = g1.number_input("Niños", 0, 10, 0, key="pms_pl_ninos")
if salida <= entrada:
    st.warning("La fecha de salida debe ser posterior a la de entrada.")
    st.stop()
try:
    datos = plano.consultar(A, H["id"], entrada, salida, int(adultos), int(ninos))
except ErrorNegocio as e:
    st.error(str(e))
    st.stop()
tipos = datos["tipos"]
tipo_id = g2.selectbox("Tipo de habitación", [None] + [t["id"] for t in tipos], key="pms_pl_tipo",
                       format_func=lambda i: "Todos los tipos" if i is None else next(f"{t['nombre']} (hasta {t['capacidad']})" for t in tipos if t["id"] == i))
solo_mar = g3.toggle("🌊 Solo vista al mar", key="pms_pl_mar")
ocultar = g4.toggle("Ocultar no disponibles", key="pms_pl_ocultar")
if not datos["plantas"]:
    st.info("Este hotel no tiene habitaciones activas. Se crean en Configuración.")
    st.stop()
if st.session_state.get("pms_pl_planta") not in datos["plantas"]:
    st.session_state.pop("pms_pl_planta", None)
planta = g5.selectbox("Planta", datos["plantas"], key="pms_pl_planta", format_func=lambda p: f"Planta {p}")

habs = datos["habitaciones"]
libres = {h["id"] for h in habs if h["disponible"]}
if st.session_state.get("pms_pl_sel") not in libres:        # cambió el estado o las fechas: la selección anterior ya no vale
    st.session_state.pop("pms_pl_sel", None)
sel = st.session_state.get("pms_pl_sel")

# ---------------- resumen y leyenda ----------------
r = plano.resumen(habs)
m = st.columns(5)
m[0].metric("Disponibles", r["disponible"])
m[1].metric("Ocupadas", r["ocupada"])
m[2].metric("En opción", r["opcion"])
m[3].metric("No operativas", r["bloqueada"] + r["fuera_de_servicio"], help="Habitaciones bloqueadas o fuera de servicio en esas fechas.")
m[4].metric("Capacidad insuficiente", r["capacidad"])
st.caption(f"Resumen de todo el hotel · {len(datos['noches'])} noche(s) del {ui.f_fecha(entrada)} al {ui.f_fecha(salida)} · {int(adultos)} adulto(s), {int(ninos)} niño(s).")
colores = {"disponible": "#2f9e60", "ocupada": "#e08a8a", "opcion": "#e0b84a", "bloqueada": "#b97a7a", "fuera_de_servicio": "#7b8794",
           "seleccionada": "#1a56a8", "capacidad": "#d9dee3"}
fondos = {"disponible": "#e8f7ee", "ocupada": "#fdeaea", "opcion": "#fff6d6", "bloqueada": "#f4e3e3", "fuera_de_servicio": "#e4e7eb",
          "seleccionada": "#dbeafe", "capacidad": "#f1f3f5"}
st.markdown('<div class="pms-leyenda">' + "".join(f'<span><i style="background:{fondos[k]};border-color:{colores[k]}"></i>{NOMBRES[k]}</span>'
                                                  for k in ("disponible", "ocupada", "opcion", "bloqueada", "fuera_de_servicio", "seleccionada", "capacidad"))
            + "</div>", unsafe_allow_html=True)

# ---------------- plano de la planta + detalle ----------------
c_plano, c_det = st.columns([5, 3], gap="large")
with c_plano:
    visibles = plano.filtrar(habs, planta, tipo_id, solo_mar, ocultar, sel)
    st.markdown(f"##### Planta {planta}")
    if not visibles:
        st.info("Ninguna habitación de esta planta cumple los filtros.")

    def _fila(lista):
        for i in range(0, len(lista), 3):
            trozo = lista[i:i + 3]
            cols = st.columns(3)
            for col, h in zip(cols, trozo):
                with col:
                    pr = datos["precios"].get(h["tipo_id"], {})
                    precio = f"{ui.dinero(pr['promedio_noche'])} / noche" if pr.get("promedio_noche") is not None else "Sin tarifa"
                    mar = "🌊 vista al mar · " if h["vista_mar"] else ""
                    st.markdown(f'<div class="pms-room pms-room-{h["visual"]}"><div class="n">{h["numero"]}</div>'
                                f'<div class="t">{h["tipo"]} · hasta {h["capacidad"]}</div>'
                                f'<div class="m">{mar}{h["metros"] or "—"} m²</div><div class="p">{precio}</div>'
                                f'<div class="e">{NOMBRES[h["visual"]]}</div></div>', unsafe_allow_html=True)
                    if h["disponible"]:
                        st.button("✓ Elegida" if h["visual"] == "seleccionada" else "Elegir", key=f"pms_pl_b_{h['id']}", width="stretch",
                                  on_click=_elegir, args=(h["id"],), type="primary" if h["visual"] == "seleccionada" else "secondary")

    frente = [h for h in visibles if h["vista_mar"]]
    fondo = [h for h in visibles if not h["vista_mar"]]
    if frente:
        st.markdown('<div class="pms-mar">🌊 &nbsp; M A R</div>', unsafe_allow_html=True)
        _fila(frente)
    if frente and fondo:
        st.markdown('<div class="pms-pasillo">PASILLO</div>', unsafe_allow_html=True)
    _fila(fondo)

with c_det:
    with st.container(border=True):
        if sel is None:
            st.markdown("#### 🛏️ Detalle de la habitación")
            st.info("Elige una habitación **disponible** en el plano para ver camas, capacidad y el desglose del precio.")
        else:
            try:
                d = plano.detalle(A, H["id"], sel, entrada, salida, int(adultos), int(ninos))
            except ErrorNegocio as e:
                st.error(str(e))
                st.stop()
            hb = d["habitacion"]
            st.markdown(f"#### Habitación {hb['numero']} · {hb['tipo']}")
            st.markdown(ui.chip("Disponible", "alojado") + (" &nbsp; 🌊 Vista al mar" if hb["vista_mar"] else ""), unsafe_allow_html=True)
            st.write(f"**Planta {hb['planta']}** · {hb['metros'] or '—'} m² · capacidad **{hb['capacidad']}** personas · vista: {hb['vista'] or '—'}")
            st.write("**Camas:** " + (", ".join(d["camas_texto"]) or "sin datos"))
            st.caption("Las camas son información: se vende la habitación completa.")
            st.markdown(f"**Estancia:** {ui.f_fecha(entrada)} → {ui.f_fecha(salida)} · {len(d['noches'])} noche(s) · {d['personas']} persona(s)")
            c = d["cotizacion"]
            if c is None:
                st.warning(d["error"])
            else:
                st.dataframe([{"Noche": ui.f_fecha(n), "Precio": ui.dinero(p)} for n, p in c["noches"]], hide_index=True, width="stretch")
                st.write(f"Subtotal alojamiento: **{ui.dinero(c['subtotal'])}**")
                for i in c["impuestos"]:
                    st.write(f"{i['nombre']} ({i['porcentaje']} %): **{ui.dinero(i['monto'])}**")
                st.write(f"**Total estimado: {ui.dinero(c['total'])}** ({H['moneda']})")
                st.caption(f"≈ {ui.dinero(c['por_persona_noche'])} por persona y noche (total ÷ {d['personas']} persona(s) ÷ {len(d['noches'])} noche(s)). "
                           "La tarifa es por habitación y noche: no cambia con el número de personas dentro de la capacidad.")
            if not PUEDE_RESERVAR:
                st.caption("Tu rol solo puede consultar el plano.")
            elif st.button("Continuar con la reserva →", key="pms_pl_continuar", type="primary", width="stretch", disabled=not d["reservable"]):
                try:
                    st.session_state["pms_prellenado_reserva"] = plano.prellenado(A, H["id"], sel, entrada, salida, int(adultos), int(ninos))
                except ErrorNegocio as e:
                    st.error(str(e))
                else:
                    st.switch_page(ui.PAGINAS["reservas"])

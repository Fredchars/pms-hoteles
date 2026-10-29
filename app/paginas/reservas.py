import datetime as dt
from decimal import Decimal

import streamlit as st

import ui
from pms import config, db, facturacion, huespedes, reservas, tarifas, vistas
from pms.auditoria import registrar
from pms.errores import ErrorNegocio
from pms.util import dinero, hoy_hotel, noches_entre

A, H = ui.actor(), ui.hotel()
ui.encabezado("📝 Reservas", "Crear, cambiar y cancelar reservas; check-in y check-out. El precio de cada noche se congela al reservar.")
EDITA = ui.puede("reservas", True)
hoy = hoy_hotel(None, H["id"])
COM_SUGERIDA = {"booking": 15, "airbnb": 3, "agencia": 10}

if not EDITA:
    st.info("Tu rol solo puede consultar reservas.")

# --- datos que llegan del Plano de habitaciones («Continuar con la reserva»): se aplican UNA vez, antes de crear los campos ---
PRE = st.session_state.pop("pms_prellenado_reserva", None)
if PRE and PRE.get("hotel_id") == H["id"] and EDITA:
    _tipo = next((t for t in config.tipos(H["id"]) if t["id"] == PRE["tipo_id"]), None)
    if _tipo:
        st.session_state.update({"pms_rn_tipo": _tipo, "pms_rn_entrada": PRE["entrada"], "pms_rn_salida": PRE["salida"],
                                 "pms_rn_adultos": int(PRE["adultos"]), "pms_rn_ninos": int(PRE["ninos"]), "pms_rn_hab": PRE["habitacion_id"],
                                 "pms_rn_pre": {k: PRE[k] for k in ("habitacion_id", "numero", "tipo")}, "pms_rn_abrir_nueva": True})
t_lista, t_nueva, t_gest, t_aprob = st.tabs(["📋 Lista", "➕ Nueva reserva", "🛠️ Gestionar una reserva", "⏳ Cancelaciones pendientes"],
                                             default="➕ Nueva reserva" if st.session_state.get("pms_rn_abrir_nueva") else None)

# ---------------- Lista ----------------
with t_lista:
    c1, c2, c3 = st.columns([2, 2, 2])
    estados = c1.multiselect("Estado", reservas.ESTADOS, default=["opcion", "confirmada", "alojado"], key="pms_rl_estados",
                             format_func=lambda e: reservas.ESTADOS_NOMBRE[e])
    texto = c2.text_input("Buscar por código o nombre", key="pms_rl_texto")
    desde = c3.date_input("Que terminen después de", value=hoy - dt.timedelta(days=30), key="pms_rl_desde", format="DD/MM/YYYY")
    filas = reservas.listar(A, H["id"], estados or None, desde, None, texto)
    st.caption(f"{len(filas)} reserva(s).")
    st.dataframe([{"Código": r["codigo"], "Huésped": r["huesped"], "Tipo": r["tipo"], "Habitación": r["habitaciones"] or "—",
                   "Entrada": ui.f_fecha(r["fecha_entrada"]), "Salida": ui.f_fecha(r["fecha_salida"]),
                   "Estado": reservas.ESTADOS_NOMBRE[r["estado"]], "Canal": r["canal"],
                   "Vence": (r["opcion_vence_en"].astimezone().strftime("%d/%m %H:%M") if r["estado"] == "opcion" and r.get("opcion_vence_en") else ""),
                   "Cancelación": "Pendiente" if r["cancelacion_estado"] == "solicitada" else ""} for r in filas],
                 hide_index=True, width="stretch")

# ---------------- Nueva ----------------
with t_nueva:
    if not EDITA:
        st.warning("Tu rol no puede crear reservas.")
    else:
        st.subheader("1. Huésped")
        q = st.text_input("Buscar huésped (nombre, documento o correo)", key="pms_rn_buscar")
        encontrados = huespedes.buscar(A, H["id"], q)
        hs = st.selectbox("Huésped", encontrados, key="pms_rn_huesped", index=None, placeholder="Elige un huésped",
                          format_func=lambda h: f"{h['nombres']} {h['apellidos']} · {h['numero_documento'] or 'sin documento'}")
        if hs:
            with db.tx() as cx:
                con = huespedes.consentimiento_vigente(cx, hs["id"])
            if con:
                st.success("✅ Tiene consentimiento de tratamiento de datos vigente.")
            else:
                st.warning("Falta el consentimiento (Ley 1581). Regístralo en la ficha del huésped antes de reservar.")
        ui.enlace("huespedes", "¿No existe? Crear huésped y registrar su consentimiento →")

        st.subheader("2. Estancia")
        pre = st.session_state.get("pms_rn_pre")
        if pre:
            st.info(f"🗺️ Datos traídos del Plano de habitaciones: habitación **{pre['numero']}** ({pre['tipo']}), fechas y huéspedes. "
                    "Elige el huésped arriba y revisa el precio. Puedes cambiar cualquier dato.")
        tipos = config.tipos(H["id"])
        c1, c2, c3 = st.columns(3)
        tipo = c1.selectbox("Tipo de habitación", tipos, key="pms_rn_tipo", format_func=lambda t: f"{t['nombre']} (hasta {t['capacidad']})")
        entrada = c2.date_input("Entrada", value=hoy, key="pms_rn_entrada", format="DD/MM/YYYY")
        salida = c3.date_input("Salida", value=hoy + dt.timedelta(days=2), key="pms_rn_salida", format="DD/MM/YYYY")
        habs_tipo = [h for h in config.habitaciones(H["id"]) if h["tipo_id"] == tipo["id"]]
        if st.session_state.get("pms_rn_hab") not in [h["id"] for h in habs_tipo]:
            st.session_state.pop("pms_rn_hab", None)         # el tipo cambió: la habitación elegida ya no corresponde
        hab_sel = st.selectbox("Habitación (opcional)", [None] + [h["id"] for h in habs_tipo], key="pms_rn_hab",
                               format_func=lambda i: "Asignar automáticamente" if i is None else
                               next(f"{h['numero']} · piso {h['planta']}" for h in habs_tipo if h["id"] == i),
                               help="Si eliges una habitación, debe estar libre todas las noches. También puedes elegirla desde el Plano de habitaciones.")
        c4, c5, c6 = st.columns(3)
        adultos = c4.number_input("Adultos", 1, 10, 2, key="pms_rn_adultos")
        ninos = c5.number_input("Niños", 0, 10, 0, key="pms_rn_ninos")
        estado = c6.selectbox("Estado inicial", list(reservas.ESTADOS_NUEVOS), index=2, key="pms_rn_estado",
                              format_func=lambda e: reservas.ESTADOS_NOMBRE[e])
        c7, c8, c9 = st.columns(3)
        canal = c7.selectbox("Canal", reservas.CANALES, key="pms_rn_canal")
        com = c8.number_input("Comisión %", 0.0, 100.0, float(COM_SUGERIDA.get(canal, 0)), step=0.5, key=f"pms_rn_com_{canal}")
        ref = c9.text_input("Referencia externa (opcional)", key="pms_rn_ref")
        if canal in ("booking", "airbnb", "agencia"):
            st.caption("🧪 No hay conexión real con este canal: la reserva se digita a mano y la comisión es un dato de prueba (integración simulada).")
        notas = st.text_area("Notas", key="pms_rn_notas", height=70)

        st.subheader("3. Desglose por noche")
        try:
            noches = noches_entre(entrada, salida)
            with db.tx() as cx:
                cot = tarifas.cotizar(cx, H["id"], tipo["id"], noches)
            sub, total = cot["subtotal"], cot["total"]
            st.dataframe([{"Noche": ui.f_fecha(n), "Precio": ui.dinero(p)} for n, p in cot["noches"]], hide_index=True, width="stretch")
            lineas = [("Subtotal alojamiento", sub)] + [(f"{i['nombre']} ({i['porcentaje']} %)", i["monto"]) for i in cot["impuestos"]]
            for k, v in lineas:
                st.write(f"{k}: **{ui.dinero(v)}**")
            st.write(f"**Total estimado: {ui.dinero(total)}** ({H['moneda']}) · el precio de cada noche queda congelado al guardar.")
            if canal != "directo" and com:
                st.caption(f"Comisión estimada: {ui.dinero(dinero(sub * Decimal(str(com)) / 100))} · neto del hotel: {ui.dinero(sub - dinero(sub * Decimal(str(com)) / 100))}")
        except ErrorNegocio as e:
            st.warning(str(e))
        if st.button("Guardar reserva", type="primary", key="pms_rn_guardar", disabled=hs is None):
            r = ui.correr(reservas.crear, A, H["id"], hs["id"], tipo["id"], entrada, salida, int(adultos), int(ninos), estado, canal, com,
                          ref or None, notas, habitacion_id=hab_sel, ok="Reserva creada. Puedes gestionarla en la pestaña «Gestionar una reserva».", recargar=False)
            if r:
                st.session_state.pop("pms_rn_pre", None)
                st.session_state.pop("pms_rn_abrir_nueva", None)
                st.session_state["pms_gest_reserva"] = r["id"]
                st.rerun()

# ---------------- Gestionar ----------------
with t_gest:
    lista = reservas.listar(A, H["id"], ["consulta", "opcion", "confirmada", "alojado"], hoy - dt.timedelta(days=7), None, "")
    if not lista:
        st.info("No hay reservas vigentes.")
    else:
        ids = [r["id"] for r in lista]
        if st.session_state.get("pms_gest_reserva") not in ids:
            st.session_state.pop("pms_gest_reserva", None)
        sel = st.selectbox("Reserva", ids, key="pms_gest_reserva",
                           format_func=lambda i: next(f"{r['codigo']} · {r['huesped']} · {ui.f_fecha(r['fecha_entrada'])}→{ui.f_fecha(r['fecha_salida'])} · "
                                                      f"{reservas.ESTADOS_NOMBRE[r['estado']]}" for r in lista if r["id"] == i))
        r = next(x for x in lista if x["id"] == sel)
        res = facturacion.resumen(A, sel) if ui.puede("facturacion") else None
        st.markdown(f"### {r['codigo']} · {r['huesped']} &nbsp; {ui.chip(reservas.ESTADOS_NOMBRE[r['estado']], r['estado'])}",
                    unsafe_allow_html=True)
        st.write(f"**{r['tipo']}** · hab. **{r['habitaciones'] or 'sin asignar'}** · {ui.f_fecha(r['fecha_entrada'])} → {ui.f_fecha(r['fecha_salida'])} · "
                 f"{r['adultos']} adulto(s), {r['ninos']} niño(s) · canal {r['canal']}")
        if res:
            c = st.columns(3)
            c[0].metric("Total con impuestos", ui.dinero(res["total"]))
            c[1].metric("Pagado", ui.dinero(res["pagado"]))
            c[2].metric("Saldo", ui.dinero(res["saldo"]))
            ui.enlace("facturacion", "Ir a cargos, pagos y comprobante →")
        with st.expander("Noches y precio congelado"):
            st.dataframe([{"Noche": ui.f_fecha(n["noche"]), "Habitación": n["numero"], "Precio congelado": ui.dinero(n["precio"]),
                           "Activa": "Sí" if n["activa"] else "No"} for n in reservas.noches_de(sel)], hide_index=True, width="stretch")
        if r["cancelacion_estado"] == "solicitada":
            st.warning(f"⏳ Cancelación solicitada: «{r['cancelacion_motivo']}». Espera la aprobación de gerencia.")
        if not EDITA:
            st.stop()

        st.markdown("#### Acciones")
        a1, a2, a3 = st.columns(3)
        if r["estado"] == "confirmada":
            with a1:
                with st.container(border=True):
                    st.markdown("**Check-in**")
                    st.caption("Solo desde el día de entrada, con la habitación lista y sin cancelación pendiente.")
                    if st.button("Hacer check-in", key=f"pms_ci_{sel}", type="primary"):
                        ui.correr(reservas.checkin, A, sel, ok="Check-in realizado.")
        if r["estado"] == "alojado":
            with a1:
                with st.container(border=True):
                    st.markdown("**Check-out**")
                    st.caption("Con saldo pendiente solo gerencia puede forzar la salida.")
                    if st.button("Hacer check-out", key=f"pms_co_{sel}", type="primary"):
                        ui.correr(reservas.checkout, A, sel, ok="Check-out realizado: la habitación quedó sucia.")
                    if A["rol"] == "gerencia" and st.button("Forzar salida con saldo (gerencia)", key=f"pms_cof_{sel}"):
                        ui.correr(reservas.checkout, A, sel, permitir_saldo=True, ok="Salida forzada registrada en auditoría.")
        if r["estado"] in reservas.ESTADOS_EDITABLES:
            with a2:
                with st.container(border=True):
                    st.markdown("**Cancelar (requiere gerencia)**")
                    mot = st.text_input("Motivo", key=f"pms_cm_{sel}")
                    if st.button("Solicitar cancelación", key=f"pms_cs_{sel}", disabled=r["cancelacion_estado"] == "solicitada"):
                        ui.correr(reservas.solicitar_cancelacion, A, sel, mot, ok="Solicitud enviada a gerencia.")
        if r["estado"] == "confirmada" and r["fecha_entrada"] < hoy:
            with a3:
                with st.container(border=True):
                    st.markdown("**No-show**")
                    st.caption("El huésped no llegó: libera la habitación.")
                    if st.button("Marcar no-show", key=f"pms_ns_{sel}"):
                        ui.correr(reservas.no_show, A, sel, ok="Marcada como no-show.")

        if r["estado"] in reservas.ESTADOS_EDITABLES:
            with st.expander("✏️ Cambiar fechas, personas o notas"):
                e1, e2 = st.columns(2)
                ne = e1.date_input("Nueva entrada", value=r["fecha_entrada"], key=f"pms_me_{sel}", format="DD/MM/YYYY")
                ns = e2.date_input("Nueva salida", value=r["fecha_salida"], key=f"pms_ms_{sel}", format="DD/MM/YYYY")
                e3, e4 = st.columns(2)
                na = e3.number_input("Adultos", 1, 10, int(r["adultos"]), key=f"pms_ma_{sel}")
                nn = e4.number_input("Niños", 0, 10, int(r["ninos"]), key=f"pms_mn_{sel}")
                nt = st.text_area("Notas", value=r["notas"] or "", key=f"pms_mt_{sel}", height=60)
                st.caption("Las noches que ya tenía conservan su precio; solo las nuevas usan la tarifa vigente.")
                if st.button("Guardar cambios", key=f"pms_mg_{sel}"):
                    ui.correr(reservas.modificar, A, sel, entrada=ne, salida=ns, adultos=int(na), ninos=int(nn), notas=nt, ok="Reserva actualizada.")
        if r["estado"] in ("confirmada", "alojado"):
            with st.expander("🛏️ Cambiar de habitación (mismo tipo)"):
                habs = [h for h in config.habitaciones(H["id"]) if h["tipo_id"] == r["tipo_id"]]
                destino = st.selectbox("Habitación", habs, key=f"pms_rh_{sel}", format_func=lambda h: f"{h['numero']} · piso {h['planta']}")
                if st.button("Cambiar habitación", key=f"pms_rhb_{sel}"):
                    ui.correr(reservas.reasignar_habitacion, A, sel, destino["id"], ok="Habitación cambiada.")
        with st.expander("✉️ Confirmación al huésped (simulada)"):
            st.info("🧪 Simulación: en este prototipo no se envía ningún correo ni mensaje real.")
            if st.button("Simular envío de confirmación", key=f"pms_em_{sel}"):
                with db.tx() as cx:
                    registrar(cx, A, "confirmacion_simulada", "reserva", sel, hotel_id=H["id"])
                st.success("Simulado: se registró el intento en la auditoría, pero no se envió nada.")

# ---------------- Aprobaciones ----------------
with t_aprob:
    pend = vistas.pendientes_aprobacion(A, H["id"])["cancelaciones"]
    if not pend:
        st.success("No hay cancelaciones pendientes.")
    for p in pend:
        with st.container(border=True):
            st.markdown(f"**{p['codigo']}** · entrada {ui.f_fecha(p['fecha_entrada'])} · pedida por {p['solicitante'] or '—'}")
            st.write(f"Motivo: {p['motivo']}")
            if A["rol"] != "gerencia":
                st.caption("Solo gerencia puede aprobar o rechazar.")
            elif p["cancelacion_solicitada_por"] == A["id"]:
                st.caption("Tú pediste esta cancelación: debe aprobarla otra persona de gerencia.")
            else:
                com = st.text_input("Comentario (opcional)", key=f"pms_ac_{p['id']}")
                b1, b2 = st.columns(2)
                if b1.button("Aprobar cancelación", key=f"pms_apa_{p['id']}", type="primary"):
                    ui.correr(reservas.resolver_cancelacion, A, p["id"], True, com, ok="Cancelación aprobada.")
                if b2.button("Rechazar", key=f"pms_apr_{p['id']}"):
                    ui.correr(reservas.resolver_cancelacion, A, p["id"], False, com, ok="Cancelación rechazada.")

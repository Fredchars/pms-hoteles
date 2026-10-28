import datetime as dt

import streamlit as st

import ui
from pms import facturacion, reservas
from pms.util import hoy_hotel

A, H = ui.actor(), ui.hotel()
ui.encabezado("🧾 Facturación simple", "Cargos, pagos y comprobante PDF. El comprobante es interno: NO es una factura legal ni electrónica.")
EDITA = ui.puede("facturacion", True)
hoy = hoy_hotel(None, H["id"])
if not EDITA:
    st.info("Tu rol solo puede consultar la facturación.")
st.info("🧪 Los pagos son registros manuales de prueba (efectivo, datáfono, transferencia): no se procesa ningún cobro real.")

t_res, t_desc = st.tabs(["🧾 Cuenta de una reserva", "⏳ Descuentos pendientes"])

with t_res:
    lista = reservas.listar(A, H["id"], ["opcion", "confirmada", "alojado", "salida"], hoy - dt.timedelta(days=60), None, "")
    if not lista:
        st.info("No hay reservas para facturar.")
    else:
        ids = [r["id"] for r in lista]
        if st.session_state.get("pms_fa_reserva") not in ids:
            st.session_state.pop("pms_fa_reserva", None)
        sel = st.selectbox("Reserva", ids, key="pms_fa_reserva", format_func=lambda i: next(
            f"{r['codigo']} · {r['huesped']} · {reservas.ESTADOS_NOMBRE[r['estado']]}" for r in lista if r["id"] == i))
        res = facturacion.resumen(A, sel)
        ESTADO_CARGO = {"aprobado": "Aprobado", "pendiente": "Pendiente de gerencia", "rechazado": "Rechazado"}
        st.dataframe([{"Concepto": c["descripcion"], "Cant.": c["cantidad"], "Valor": ui.dinero(c["monto"]),
                       "Estado": "Anulado" if c["anulado"] else ESTADO_CARGO[c["estado"]]} for c in res["cargos"]],
                     hide_index=True, width="stretch")
        c = st.columns(4)
        c[0].metric("Subtotal", ui.dinero(res["subtotal"]))
        c[1].metric("Impuestos", ui.dinero(sum(i["monto"] for i in res["impuestos"])))
        c[2].metric("Total", ui.dinero(res["total"]))
        c[3].metric("Saldo", ui.dinero(res["saldo"]))
        if res["impuestos"]:
            st.caption(" · ".join(f"{i['nombre']} {i['porcentaje']} %: {ui.dinero(i['monto'])}" for i in res["impuestos"]))
        if res["pagos"]:
            st.markdown("**Pagos**")
            st.dataframe([{"Fecha": p["creado"].strftime("%d/%m/%Y %H:%M"), "Método": p["metodo"], "Monto": ui.dinero(p["monto"]),
                           "Referencia": p["referencia"] or "", "Anulado": "Sí" if p["anulado"] else ""} for p in res["pagos"]],
                         hide_index=True, width="stretch")
        st.download_button("⬇️ Descargar comprobante PDF (no es factura legal)", data=facturacion.comprobante_pdf(A, sel),
                           file_name=f"comprobante_{res['reserva']['codigo']}.pdf", mime="application/pdf", key=f"pms_fa_pdf_{sel}")
        if EDITA:
            a, b, d = st.columns(3)
            with a:
                with st.container(border=True):
                    st.markdown("**Agregar un extra**")
                    desc = st.text_input("Descripción", key=f"pms_fa_xd_{sel}")
                    cant = st.number_input("Cantidad", 1, 100, 1, key=f"pms_fa_xc_{sel}")
                    pr = st.number_input("Precio unitario", 0.0, step=1000.0, key=f"pms_fa_xp_{sel}")
                    if st.button("Agregar extra", key=f"pms_fa_xb_{sel}"):
                        ui.correr(facturacion.agregar_extra, A, sel, desc, cant, pr, ok="Extra agregado.")
            with b:
                with st.container(border=True):
                    st.markdown("**Registrar pago (simulado)**")
                    met = st.selectbox("Método", ["efectivo", "datafono", "transferencia", "otro"], key=f"pms_fa_pm_{sel}")
                    mo = st.number_input("Monto", 0.0, step=1000.0, key=f"pms_fa_pa_{sel}")
                    rf = st.text_input("Referencia", key=f"pms_fa_pr_{sel}")
                    if st.button("Registrar pago", key=f"pms_fa_pb_{sel}"):
                        ui.correr(facturacion.registrar_pago, A, sel, met, mo, rf, ok="Pago registrado.")
            with d:
                with st.container(border=True):
                    st.markdown("**Pedir un descuento (aprueba gerencia)**")
                    pc = st.number_input("Porcentaje %", 0.0, 100.0, step=1.0, key=f"pms_fa_dp_{sel}")
                    mt = st.text_input("Motivo", key=f"pms_fa_dm_{sel}")
                    if st.button("Solicitar descuento", key=f"pms_fa_db_{sel}"):
                        ui.correr(facturacion.solicitar_descuento, A, sel, pc, mt, ok="Descuento solicitado: queda pendiente de gerencia.")
            if A["rol"] == "gerencia":
                with st.expander("Anular un extra o un pago (gerencia)"):
                    extras = [x for x in res["cargos"] if x["tipo"] == "extra" and not x["anulado"]]
                    if extras:
                        x = st.selectbox("Extra", extras, key=f"pms_fa_ax_{sel}", format_func=lambda x: f"{x['descripcion']} · {ui.dinero(x['monto'])}")
                        mx = st.text_input("Motivo de la anulación", key=f"pms_fa_am_{sel}")
                        if st.button("Anular extra", key=f"pms_fa_ab_{sel}"):
                            ui.correr(facturacion.anular_cargo, A, x["id"], mx, ok="Extra anulado.")
                    pagos = [p for p in res["pagos"] if not p["anulado"]]
                    if pagos:
                        p = st.selectbox("Pago", pagos, key=f"pms_fa_ap_{sel}", format_func=lambda p: f"{p['metodo']} · {ui.dinero(p['monto'])}")
                        mp = st.text_input("Motivo de la anulación del pago", key=f"pms_fa_apm_{sel}")
                        if st.button("Anular pago", key=f"pms_fa_apb_{sel}"):
                            ui.correr(facturacion.anular_pago, A, p["id"], mp, ok="Pago anulado.")

with t_desc:
    pend = facturacion.descuentos_pendientes(H["id"])
    if not pend:
        st.success("No hay descuentos pendientes.")
    for c in pend:
        with st.container(border=True):
            st.markdown(f"**{c['codigo']}** · {c['descripcion']} · {ui.dinero(c['monto'])} · pedido por {c['solicitante'] or '—'}")
            st.write(f"Motivo: {c['motivo']}")
            if A["rol"] != "gerencia":
                st.caption("Solo gerencia puede aprobar o rechazar.")
            elif c["solicitado_por"] == A["id"]:
                st.caption("Tú pediste este descuento: debe aprobarlo otra persona de gerencia.")
            else:
                com = st.text_input("Comentario (opcional)", key=f"pms_fd_c_{c['id']}")
                b1, b2 = st.columns(2)
                if b1.button("Aprobar descuento", key=f"pms_fd_a_{c['id']}", type="primary"):
                    ui.correr(facturacion.resolver_descuento, A, c["id"], True, com, ok="Descuento aprobado.")
                if b2.button("Rechazar", key=f"pms_fd_r_{c['id']}"):
                    ui.correr(facturacion.resolver_descuento, A, c["id"], False, com, ok="Descuento rechazado.")

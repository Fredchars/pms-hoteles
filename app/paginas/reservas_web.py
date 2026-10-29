import datetime as dt

import streamlit as st

import ui
from pms import reserva_web
from pms.vencimientos import MINUTOS_BLOQUEO_WEB

A, H = ui.actor(), ui.hotel()
ui.encabezado("🌐 Reservas web", "Reservas hechas por los clientes en la mini web pública: estado, pago y correo. La habitación queda bloqueada mientras corre el tiempo.")
EDITA = ui.puede("reservas", True)

c1, c2 = st.columns([4, 1])
c1.caption(f"El bloqueo web dura {MINUTOS_BLOQUEO_WEB} minutos; si no se paga, la habitación se libera sola (también desde una tarea programada cada 5 min).")
if EDITA and c2.button("Liberar vencidas ahora", key="pms_rw_liberar"):
    n = ui.correr(reserva_web.liberar_vencidas_ahora, A, H["id"], ok="Revisadas las reservas con tiempo vencido.", recargar=False)
    if n is not None:
        st.success(f"Se liberaron {0 if n is True else n} reserva(s) vencida(s).")

filas = reserva_web.listar_web(A, H["id"])
ahora = dt.datetime.now(dt.timezone.utc)
abiertas = [f for f in filas if f["estado"] in reserva_web.ABIERTOS]
st.metric("Bloqueos en curso", len(abiertas))
if any((f["pago_estado"] == "requiere_revision") for f in filas):
    st.warning("Hay pagos que requieren revisión manual (llegaron cuando la habitación ya no estaba libre). Revisa la columna «Pago».")
if not filas:
    st.info("Todavía no hay reservas hechas desde la web.")
else:
    PAGO = {"pendiente": "Pendiente", "aprobada": "Aprobada", "rechazada": "Rechazada", "vencida": "Vencida", "requiere_revision": "⚠️ Requiere revisión", None: "—"}
    CORREO = {"simulado": "Simulado (no se envió)", "enviado": "Enviado", "error": "Error", None: "—"}
    st.dataframe([{
        "Número": f["numero_publico"], "Estado web": reserva_web.ESTADO_TEXTO.get(f["estado"], f["estado"]), "Reserva PMS": f["codigo"],
        "Huésped": f["huesped"], "Tipo": f["tipo"], "Habitación": f["habitacion"] or "—",
        "Entrada": ui.f_fecha(f["fecha_entrada"]), "Salida": ui.f_fecha(f["fecha_salida"]), "Total": ui.dinero(f["monto_total"]),
        "Pagado": ui.dinero(f["pagado"]), "Pago": PAGO.get(f["pago_estado"], f["pago_estado"]), "Referencia": f["pago_referencia"] or "—",
        "Vence": (f["vence_en"].astimezone().strftime("%d/%m %H:%M") if f["estado"] in reserva_web.ABIERTOS and f["vence_en"] else ""),
        "Correo": CORREO.get(f["correo_estado"], f["correo_estado"]),
    } for f in filas], hide_index=True, width="stretch")
    st.caption("Estas reservas también aparecen en Reservas, Calendario y Plano con canal «web».")

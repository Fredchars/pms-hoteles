"""Vencimiento automático de la «opción» (bloqueo temporal) y de los bloqueos de la reserva web.

Una reserva en estado `opcion` aparta habitaciones (filas activas en pms_reserva_noches). Antes nada la liberaba: la «opción 48 h»
no vencía nunca. Ahora cada opción nueva lleva `opcion_vence_en` y, pasada esa hora, se libera sola:
  · la reserva pasa a «cancelada» (motivo «Opción vencida…»), sus noches quedan libres y sus cargos anulados;
  · si era una reserva web, su estado pasa a «expirada» y sus intentos de pago pendientes a «vencida».
Se ejecuta de DOS formas, para que la disponibilidad nunca dependa de un reloj externo:
  1. «perezosa»: `liberar_vencidas(cx)` se llama al consultar disponibilidad/plano y al crear o confirmar reservas;
  2. programada: `scripts/liberar_vencidos.py` desde GitHub Actions cada 5 minutos (limpieza + correo/estado al día).
Las opciones sin fecha de vencimiento (las que existían antes de esta mejora) NO se tocan."""
from __future__ import annotations

import os

from .auditoria import registrar

HORAS_OPCION_PMS = float(os.environ.get("PMS_HORAS_OPCION", "48"))      # opción creada por recepción
MINUTOS_BLOQUEO_WEB = int(os.environ.get("PMS_WEB_HOLD_MINUTOS", "15"))   # bloqueo temporal de la reserva web
MOTIVO = "Opción vencida: se liberó automáticamente"


def _candidatas(cx, hotel_id):
    return cx.execute("select id, hotel_id from pms_reservas where estado='opcion' and opcion_vence_en is not null "
                      "and opcion_vence_en <= now() and (%s::bigint is null or hotel_id=%s) order by id",
                      (hotel_id, hotel_id)).fetchall()


def liberar_vencidas(cx, hotel_id: int | None = None) -> list[dict]:
    """Libera todas las opciones vencidas (de un hotel o de todos). Idempotente y segura con concurrencia: toma el mismo cerrojo por
    hotel que las ventas, y vuelve a comprobar cada reserva con la fila bloqueada (si alguien la confirmó justo antes, no se toca).
    Devuelve [{reserva_id, hotel_id, web}] de lo liberado."""
    cand = _candidatas(cx, hotel_id)
    if not cand:                                               # camino rápido (casi siempre): no hay nada que liberar, no se bloquea
        return []
    liberadas = []
    for h in sorted({c["hotel_id"] for c in cand}):
        cx.execute("select pg_advisory_xact_lock(%s)", (7_000_000 + h,))
        for r in cx.execute("select * from pms_reservas where hotel_id=%s and estado='opcion' and opcion_vence_en is not null "
                            "and opcion_vence_en <= now() order by id for update", (h,)).fetchall():
            cx.execute("update pms_reserva_noches set activa=false where reserva_id=%s and activa", (r["id"],))
            cx.execute("update pms_cargos set anulado=true, motivo=coalesce(motivo,'') || %s where reserva_id=%s and not anulado "
                       "and tipo in ('noche','extra')", (f" · {MOTIVO}", r["id"]))
            cx.execute("update pms_reservas set estado='cancelada', cancelacion_motivo=%s, opcion_vence_en=null where id=%s",
                       (MOTIVO, r["id"]))
            w = cx.execute("update pms_reservas_web set estado='expirada', actualizado=now() where reserva_id=%s "
                           "and estado in ('bloqueada','pago_pendiente') returning id", (r["id"],)).fetchone()
            if w:
                cx.execute("update pms_pagos_pasarela set estado='vencida', actualizado=now() where reserva_web_id=%s "
                           "and estado='pendiente'", (w["id"],))
            registrar(cx, None, "vencer_opcion", "reserva", r["id"], antes={"estado": "opcion"},
                      despues={"estado": "cancelada", "web": bool(w)}, hotel_id=h, email="sistema@pms")
            liberadas.append({"reserva_id": r["id"], "hotel_id": h, "web": bool(w)})
    return liberadas

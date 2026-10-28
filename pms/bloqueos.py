"""Bloqueos por mantenimiento: la habitación no se puede vender mientras dure el bloqueo."""
from __future__ import annotations

import datetime as dt

from . import db, seguridad
from .auditoria import registrar
from .errores import ErrorNegocio


def listar(actor, hotel_id: int, solo_activos=True) -> list[dict]:
    seguridad.exigir(actor, "bloqueos", editar=False)
    seguridad.exigir_hotel(actor, hotel_id)
    return db.todos("select b.*, h.numero from pms_bloqueos b join pms_habitaciones h on h.id=b.habitacion_id where b.hotel_id=%s"
                    + (" and b.activo" if solo_activos else "") + " order by b.fecha_desde desc", (hotel_id,))


def crear(actor, hotel_id: int, habitacion_id: int, desde: dt.date, hasta: dt.date, motivo: str) -> int:
    seguridad.exigir(actor, "bloqueos")
    seguridad.exigir_hotel(actor, hotel_id)
    if hasta < desde:
        raise ErrorNegocio("La fecha final no puede ser anterior a la inicial.")
    if not motivo.strip():
        raise ErrorNegocio("Escribe el motivo del bloqueo.")
    with db.tx() as cx:
        cx.execute("select pg_advisory_xact_lock(%s)", (7_000_000 + hotel_id,))
        h = cx.execute("select * from pms_habitaciones where id=%s and hotel_id=%s", (habitacion_id, hotel_id)).fetchone()
        if not h:
            raise ErrorNegocio("La habitación no existe en este hotel.")
        choques = cx.execute("select r.codigo, n.noche from pms_reserva_noches n join pms_reservas r on r.id=n.reserva_id "
                             "where n.habitacion_id=%s and n.activa and n.noche between %s and %s order by n.noche",
                             (habitacion_id, desde, hasta)).fetchall()
        if choques:
            c = choques[0]
            raise ErrorNegocio(f"La habitación {h['numero']} tiene noches vendidas en ese rango (por ejemplo la reserva "
                               f"{c['codigo']} el {c['noche']:%d/%m/%Y}). Cambia esas reservas de habitación primero.")
        b = cx.execute("insert into pms_bloqueos (hotel_id, habitacion_id, fecha_desde, fecha_hasta, motivo, creado_por) "
                       "values (%s,%s,%s,%s,%s,%s) returning id", (hotel_id, habitacion_id, desde, hasta, motivo.strip(), actor["id"])).fetchone()
        registrar(cx, actor, "crear", "bloqueo", b["id"], despues={"habitacion": h["numero"], "desde": desde, "hasta": hasta,
                                                                    "motivo": motivo}, hotel_id=hotel_id)
        return b["id"]


def liberar(actor, bloqueo_id: int):
    seguridad.exigir(actor, "bloqueos")
    with db.tx() as cx:
        b = cx.execute("select * from pms_bloqueos where id=%s", (bloqueo_id,)).fetchone()
        if not b or not b["activo"]:
            raise ErrorNegocio("Bloqueo no encontrado o ya liberado.")
        seguridad.exigir_hotel(actor, b["hotel_id"])
        cx.execute("update pms_bloqueos set activo=false, liberado_por=%s, liberado_en=now() where id=%s", (actor["id"], bloqueo_id))
        registrar(cx, actor, "liberar", "bloqueo", bloqueo_id, antes={"activo": True}, despues={"activo": False}, hotel_id=b["hotel_id"])

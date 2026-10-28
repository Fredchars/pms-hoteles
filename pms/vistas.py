"""Consultas de lectura para el dashboard del día, el calendario y los reportes."""
from __future__ import annotations

import datetime as dt

import pandas as pd

from . import db, facturacion, seguridad
from .util import hoy_hotel


def dashboard(actor, hotel_id: int, hoy: dt.date | None = None) -> dict:
    seguridad.exigir(actor, "dashboard", editar=False)
    seguridad.exigir_hotel(actor, hotel_id)
    with db.tx() as cx:
        hoy = hoy or hoy_hotel(cx, hotel_id)
        base = ("select r.id, r.codigo, r.estado, r.fecha_entrada, r.fecha_salida, h.nombres || ' ' || h.apellidos huesped, "
                "tp.nombre tipo, (select string_agg(distinct hb.numero, ', ') from pms_reserva_noches n join pms_habitaciones hb "
                "on hb.id=n.habitacion_id where n.reserva_id=r.id and n.activa and n.noche = %s) habitacion "
                "from pms_reservas r join pms_huespedes h on h.id=r.huesped_id join pms_tipos_habitacion tp on tp.id=r.tipo_id ")
        llegadas = cx.execute(base + "where r.hotel_id=%s and r.fecha_entrada=%s and r.estado in ('opcion','confirmada','alojado') "
                              "order by r.codigo", (hoy, hotel_id, hoy)).fetchall()
        salidas = cx.execute(base + "where r.hotel_id=%s and r.fecha_salida=%s and r.estado in ('alojado','salida') order by r.codigo",
                             (hoy - dt.timedelta(days=1), hotel_id, hoy)).fetchall()
        total_hab = cx.execute("select count(*) n from pms_habitaciones where hotel_id=%s and activo", (hotel_id,)).fetchone()["n"]
        bloq = cx.execute("select count(distinct habitacion_id) n from pms_bloqueos where hotel_id=%s and activo and fecha_desde<=%s "
                          "and fecha_hasta>=%s", (hotel_id, hoy, hoy)).fetchone()["n"]
        ocupadas = cx.execute("select count(*) n from pms_reserva_noches n join pms_reservas r on r.id=n.reserva_id where n.hotel_id=%s "
                              "and n.activa and n.noche=%s and r.estado in ('confirmada','alojado','salida')", (hotel_id, hoy)).fetchone()["n"]
        en_casa = cx.execute("select count(*) n from pms_reservas where hotel_id=%s and estado='alojado'", (hotel_id,)).fetchone()["n"]
        ingresos = cx.execute("select coalesce(sum(monto),0) m from pms_cargos where hotel_id=%s and tipo='noche' and noche=%s "
                              "and estado='aprobado' and not anulado", (hotel_id, hoy)).fetchone()["m"]
        cobros = cx.execute("select coalesce(sum(monto),0) m from pms_pagos p where hotel_id=%s and not anulado and "
                            "(p.creado at time zone (select zona_horaria from pms_hoteles where id=%s))::date = %s",
                            (hotel_id, hotel_id, hoy)).fetchone()["m"]
        hk = cx.execute("select estado_limpieza, count(*) n from pms_habitaciones where hotel_id=%s and activo group by 1",
                        (hotel_id,)).fetchall()
        canc = cx.execute("select count(*) n from pms_reservas where hotel_id=%s and cancelacion_estado='solicitada'", (hotel_id,)).fetchone()["n"]
        desc = cx.execute("select count(*) n from pms_cargos where hotel_id=%s and tipo='descuento' and estado='pendiente' and not anulado",
                          (hotel_id,)).fetchone()["n"]
        moneda = cx.execute("select moneda from pms_hoteles where id=%s", (hotel_id,)).fetchone()["moneda"]
    vendibles = max(total_hab - bloq, 0)
    return {"hoy": hoy, "llegadas": llegadas, "salidas": salidas, "habitaciones": total_hab, "bloqueadas": bloq,
            "ocupadas_hoy": ocupadas, "en_casa": en_casa, "ocupacion_pct": round(100 * ocupadas / vendibles, 1) if vendibles else 0.0,
            "ingresos_dia": ingresos, "cobros_dia": cobros, "hk": {x["estado_limpieza"]: x["n"] for x in hk},
            "cancelaciones_pendientes": canc, "descuentos_pendientes": desc, "moneda": moneda}


def calendario(actor, hotel_id: int, desde: dt.date, dias: int = 14) -> dict:
    """Rejilla habitación × día de solo lectura. Cada celda: libre, opcion, confirmada, alojado, salida o bloqueo."""
    seguridad.exigir(actor, "calendario", editar=False)
    seguridad.exigir_hotel(actor, hotel_id)
    fechas = [desde + dt.timedelta(days=i) for i in range(dias)]
    with db.tx() as cx:
        habs = cx.execute("select h.id, h.numero, h.planta, t.nombre tipo from pms_habitaciones h join pms_tipos_habitacion t on t.id=h.tipo_id "
                          "where h.hotel_id=%s and h.activo order by h.planta, h.numero", (hotel_id,)).fetchall()
        noches = cx.execute("select n.habitacion_id, n.noche, r.estado, r.codigo, hu.apellidos from pms_reserva_noches n "
                            "join pms_reservas r on r.id=n.reserva_id join pms_huespedes hu on hu.id=r.huesped_id "
                            "where n.hotel_id=%s and n.activa and n.noche between %s and %s and r.estado in "
                            "('consulta','opcion','confirmada','alojado','salida')", (hotel_id, fechas[0], fechas[-1])).fetchall()
        bloqs = cx.execute("select habitacion_id, fecha_desde, fecha_hasta, motivo from pms_bloqueos where hotel_id=%s and activo and "
                           "fecha_desde<=%s and fecha_hasta>=%s", (hotel_id, fechas[-1], fechas[0])).fetchall()
    celdas = {}
    for n in noches:
        celdas[(n["habitacion_id"], n["noche"])] = {"estado": n["estado"], "texto": n["apellidos"], "codigo": n["codigo"]}
    for b in bloqs:
        for f in fechas:
            if b["fecha_desde"] <= f <= b["fecha_hasta"]:
                celdas[(b["habitacion_id"], f)] = {"estado": "bloqueo", "texto": "Bloqueo", "codigo": b["motivo"]}
    return {"habitaciones": habs, "fechas": fechas, "celdas": celdas}


def reporte_diario(actor, hotel_id: int, desde: dt.date, hasta: dt.date) -> pd.DataFrame:
    """Por día: habitaciones vendibles, noches vendidas, ocupación %, ingresos de alojamiento y de extras (sin impuestos)."""
    seguridad.exigir(actor, "reportes", editar=False)
    seguridad.exigir_hotel(actor, hotel_id)
    if hasta < desde:
        raise ValueError("Rango de fechas no válido")
    with db.tx() as cx:
        filas = cx.execute("""
            with dias as (select d::date dia from generate_series(%(d)s::date, %(h)s::date, interval '1 day') d),
            total as (select count(*) n from pms_habitaciones where hotel_id=%(hid)s and activo)
            select dias.dia as fecha,
              (select n from total) - (select count(distinct habitacion_id) from pms_bloqueos b where b.hotel_id=%(hid)s and b.activo
                                       and b.fecha_desde<=dias.dia and b.fecha_hasta>=dias.dia) as vendibles,
              (select count(*) from pms_reserva_noches n join pms_reservas r on r.id=n.reserva_id where n.hotel_id=%(hid)s and n.activa
               and n.noche=dias.dia and r.estado in ('confirmada','alojado','salida')) as vendidas,
              (select coalesce(sum(monto),0) from pms_cargos c where c.hotel_id=%(hid)s and c.tipo='noche' and c.noche=dias.dia
               and c.estado='aprobado' and not c.anulado) as ingreso_alojamiento,
              (select coalesce(sum(monto),0) from pms_cargos c where c.hotel_id=%(hid)s and c.tipo='extra' and not c.anulado
               and (c.creado at time zone (select zona_horaria from pms_hoteles where id=%(hid)s))::date=dias.dia) as ingreso_extras,
              (select coalesce(sum(monto),0) from pms_cargos c where c.hotel_id=%(hid)s and c.tipo='descuento' and c.estado='aprobado'
               and not c.anulado and (coalesce(c.resuelto_en, c.creado) at time zone (select zona_horaria from pms_hoteles where id=%(hid)s))::date=dias.dia) as descuentos
            from dias order by dias.dia""", {"d": desde, "h": hasta, "hid": hotel_id}).fetchall()
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    for c in ("ingreso_alojamiento", "ingreso_extras", "descuentos"):
        df[c] = df[c].astype(float)
    df["vendibles"] = df["vendibles"].astype(int)
    df["vendidas"] = df["vendidas"].astype(int)
    df["ocupacion_pct"] = (100 * df["vendidas"] / df["vendibles"].where(df["vendibles"] > 0)).fillna(0).round(1)
    df["ingreso_neto"] = df["ingreso_alojamiento"] + df["ingreso_extras"] + df["descuentos"]
    return df


def resumen_periodo(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"ocupacion_pct": 0.0, "vendidas": 0, "vendibles": 0, "ingreso_neto": 0.0}
    v, d = int(df["vendidas"].sum()), int(df["vendibles"].sum())
    return {"ocupacion_pct": round(100 * v / d, 1) if d else 0.0, "vendidas": v, "vendibles": d,
            "ingreso_neto": float(df["ingreso_neto"].sum()), "alojamiento": float(df["ingreso_alojamiento"].sum()),
            "extras": float(df["ingreso_extras"].sum()), "descuentos": float(df["descuentos"].sum())}


def ingresos_por_mes(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    m = df.copy()
    m["mes"] = pd.to_datetime(m["fecha"]).dt.strftime("%Y-%m")
    g = m.groupby("mes").agg(vendidas=("vendidas", "sum"), vendibles=("vendibles", "sum"), ingreso_neto=("ingreso_neto", "sum")).reset_index()
    g["ocupacion_pct"] = (100 * g["vendidas"] / g["vendibles"].where(g["vendibles"] > 0)).fillna(0).round(1)
    return g


def pendientes_aprobacion(actor, hotel_id: int) -> dict:
    """Solicitudes que espera gerencia: cancelaciones y descuentos."""
    seguridad.exigir(actor, "reservas", editar=False)
    seguridad.exigir_hotel(actor, hotel_id)
    canc = db.todos("select r.id, r.codigo, r.cancelacion_motivo motivo, r.fecha_entrada, u.nombre solicitante, r.cancelacion_solicitada_por "
                    "from pms_reservas r left join pms_usuarios u on u.id=r.cancelacion_solicitada_por where r.hotel_id=%s and "
                    "r.cancelacion_estado='solicitada' order by r.id", (hotel_id,))
    return {"cancelaciones": canc, "descuentos": facturacion.descuentos_pendientes(hotel_id)}


def auditoria(actor, hotel_id: int, limite: int = 300, accion: str = "", usuario: str = "") -> list[dict]:
    seguridad.exigir(actor, "auditoria", editar=False)
    seguridad.exigir_hotel(actor, hotel_id)
    return db.todos("select * from pms_auditoria where (hotel_id=%s or hotel_id is null) and (%s='' or accion ilike %s) and "
                    "(%s='' or coalesce(usuario_email,'') ilike %s) order by id desc limit %s",
                    (hotel_id, accion, f"%{accion}%", usuario, f"%{usuario}%", limite))

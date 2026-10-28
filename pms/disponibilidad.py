"""Qué habitaciones están libres. La base de datos garantiza lo mismo con la restricción única habitación+noche."""
from __future__ import annotations

import datetime as dt

from .errores import ErrorNegocio


def bloqueada(cx, habitacion_id: int, noches: list[dt.date]) -> bool:
    """True si la habitación tiene un bloqueo activo que cubra alguna de las noches."""
    bs = cx.execute("select fecha_desde, fecha_hasta from pms_bloqueos where habitacion_id=%s and activo "
                    "and fecha_desde<=%s and fecha_hasta>=%s", (habitacion_id, max(noches), min(noches))).fetchall()
    return any(b["fecha_desde"] <= n <= b["fecha_hasta"] for b in bs for n in noches)


def libres_por_noche(cx, hotel_id: int, tipo_id: int | None, noches: list[dt.date],
                     excluir_reserva: int | None = None) -> dict[dt.date, list[dict]]:
    """Para cada noche, las habitaciones activas (del tipo, si se indica) sin noche vendida ni bloqueo."""
    filtro = "and h.tipo_id=%s" if tipo_id else ""
    base = (hotel_id, tipo_id) if tipo_id else (hotel_id,)
    habs = cx.execute(f"select h.*, t.capacidad from pms_habitaciones h join pms_tipos_habitacion t on t.id=h.tipo_id "
                      f"where h.hotel_id=%s and h.activo {filtro} order by h.numero", base).fetchall()
    ids = [h["id"] for h in habs]
    if not ids:
        return {n: [] for n in noches}
    ocup = cx.execute("select habitacion_id, noche from pms_reserva_noches where activa and habitacion_id = any(%s) "
                      "and noche = any(%s) and (%s::bigint is null or reserva_id <> %s)",
                      (ids, noches, excluir_reserva, excluir_reserva)).fetchall()
    bloq = cx.execute("select habitacion_id, fecha_desde, fecha_hasta from pms_bloqueos where activo and habitacion_id = any(%s) "
                      "and fecha_desde <= %s and fecha_hasta >= %s", (ids, max(noches), min(noches))).fetchall()
    ocupadas = {(o["habitacion_id"], o["noche"]) for o in ocup}
    res = {}
    for n in noches:
        res[n] = [h for h in habs if (h["id"], n) not in ocupadas
                  and not any(b["habitacion_id"] == h["id"] and b["fecha_desde"] <= n <= b["fecha_hasta"] for b in bloq)]
    return res


def asignar(cx, hotel_id: int, tipo_id: int, noches: list[dt.date], preferida: int | None = None,
            excluir_reserva: int | None = None, habitacion_previa: dict[dt.date, int] | None = None) -> dict[dt.date, int]:
    """Elige una habitación por noche. Prefiere la misma para toda la estancia; si no se puede, cambia de habitación
    solo en las noches necesarias. Lanza ErrorNegocio si alguna noche está agotada."""
    libres = libres_por_noche(cx, hotel_id, tipo_id, noches, excluir_reserva)
    for n in noches:
        if not libres[n]:
            raise ErrorNegocio(f"No hay disponibilidad de este tipo de habitación la noche del {n:%d/%m/%Y}.")
    ids_por_noche = {n: {h["id"] for h in libres[n]} for n in noches}
    comunes = set.intersection(*ids_por_noche.values())
    if preferida is not None:
        if preferida not in comunes:
            raise ErrorNegocio("La habitación elegida no está libre en todas las noches de la estancia.")
        return {n: preferida for n in noches}
    orden = [h["id"] for h in sorted((h for n in noches for h in libres[n]), key=lambda h: h["numero"])]
    if comunes:
        elegido = next(i for i in dict.fromkeys(orden) if i in comunes)
        return {n: elegido for n in noches}
    res, previa = {}, None
    for n in noches:
        cand = [h["id"] for h in libres[n]]
        res[n] = previa if previa in cand else cand[0]
        previa = res[n]
    return res

"""Qué habitaciones están libres. La base de datos garantiza lo mismo con la restricción única habitación+noche."""
from __future__ import annotations

import datetime as dt

from .errores import ErrorNegocio


ESTADOS_PLANO = ("disponible", "ocupada", "opcion", "bloqueada", "fuera_de_servicio", "capacidad")
NOMBRE_ESTADO_PLANO = {"disponible": "Disponible", "ocupada": "Ocupada", "opcion": "En opción", "bloqueada": "Bloqueada",
                       "fuera_de_servicio": "Fuera de servicio", "capacidad": "Capacidad insuficiente", "seleccionada": "Seleccionada"}


def cabe(capacidad: int, adultos: int, ninos: int) -> bool:
    """Regla única de capacidad (la usa la reserva y el plano)."""
    return adultos >= 1 and ninos >= 0 and adultos + ninos <= capacidad


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


def estado_habitaciones(cx, hotel_id: int, noches: list[dt.date], adultos: int = 1, ninos: int = 0,
                        excluir_reserva: int | None = None) -> list[dict]:
    """Estado de CADA habitación activa para esas noches (plano de habitaciones). «Disponible» significa exactamente lo mismo que
    en la reserva: sin noche vendida ni bloqueo en ninguna de las noches (misma consulta que `libres_por_noche`, por tanto
    misma regla de unicidad habitación+noche), con capacidad suficiente y no fuera de servicio.
    Prioridad cuando hay varias causas: fuera de servicio > ocupada > bloqueada > en opción > capacidad insuficiente."""
    libres = libres_por_noche(cx, hotel_id, None, noches, excluir_reserva)
    libres_ids = set.intersection(*({h["id"] for h in libres[n]} for n in noches))
    habs = cx.execute("select h.id, h.numero, h.planta, h.tipo_id, h.metros, h.vista, h.vista_mar, h.estado_limpieza, "
                      "t.nombre tipo, t.capacidad from pms_habitaciones h join pms_tipos_habitacion t on t.id=h.tipo_id "
                      "where h.hotel_id=%s and h.activo order by h.planta, h.numero", (hotel_id,)).fetchall()
    ids = [h["id"] for h in habs]
    ocup = cx.execute("select n.habitacion_id, r.estado from pms_reserva_noches n join pms_reservas r on r.id=n.reserva_id "
                      "where n.activa and n.habitacion_id = any(%s) and n.noche = any(%s) and (%s::bigint is null or n.reserva_id <> %s)",
                      (ids, noches, excluir_reserva, excluir_reserva)).fetchall() if ids else []
    bloq = cx.execute("select habitacion_id, fecha_desde, fecha_hasta from pms_bloqueos where activo and habitacion_id = any(%s) "
                      "and fecha_desde <= %s and fecha_hasta >= %s", (ids, max(noches), min(noches))).fetchall() if ids else []
    bloqueadas = {b["habitacion_id"] for b in bloq if any(b["fecha_desde"] <= n <= b["fecha_hasta"] for n in noches)}
    firmes = {o["habitacion_id"] for o in ocup if o["estado"] not in ("consulta", "opcion")}
    blandas = {o["habitacion_id"] for o in ocup if o["estado"] in ("consulta", "opcion")}
    out = []
    for h in habs:
        i = h["id"]
        if h["estado_limpieza"] == "fuera_de_servicio":
            est = "fuera_de_servicio"
        elif i in libres_ids:
            est = "disponible" if cabe(h["capacidad"], adultos, ninos) else "capacidad"
        elif i in firmes:
            est = "ocupada"
        elif i in bloqueadas:
            est = "bloqueada"
        else:
            est = "opcion" if i in blandas else "ocupada"
        out.append({**h, "estado": est, "disponible": est == "disponible"})
    return out

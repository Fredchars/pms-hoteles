"""Plano de habitaciones: estado de cada habitación en unas fechas, filtros, detalle con precio y datos para prellenar la reserva.
No tiene reglas propias de disponibilidad ni de precio: usa `disponibilidad.estado_habitaciones` (misma unicidad habitación+noche
que la reserva) y `tarifas.cotizar` (mismas tarifas e impuestos que Reservas)."""
from __future__ import annotations

import datetime as dt

from . import db, dibujo, disponibilidad, seguridad, tarifas
from .errores import ErrorNegocio
from .util import noches_entre

MAX_NOCHES = 60


def _noches(entrada: dt.date, salida: dt.date) -> list[dt.date]:
    noches = noches_entre(entrada, salida)
    if len(noches) > MAX_NOCHES:
        raise ErrorNegocio(f"Para el plano elige una estancia de máximo {MAX_NOCHES} noches.")
    return noches


def _permiso(actor, hotel_id: int):
    seguridad.exigir(actor, "plano", editar=False)
    seguridad.exigir_hotel(actor, hotel_id)


def _texto_camas(camas: list[dict]) -> list[str]:
    return [f"{c['cantidad']} × {c['tipo'].replace('_', ' ')}" + (f" ({c['ancho_cm']} cm)" if c["ancho_cm"] else "") for c in camas]


def consultar(actor, hotel_id: int, entrada: dt.date, salida: dt.date, adultos: int = 2, ninos: int = 0) -> dict:
    """Todas las habitaciones activas del hotel con su estado para esas fechas, más las plantas, los tipos y el precio medio por noche
    de cada tipo (o el motivo por el que no se puede cotizar)."""
    _permiso(actor, hotel_id)
    noches = _noches(entrada, salida)
    with db.tx() as cx:
        habs = disponibilidad.estado_habitaciones(cx, hotel_id, noches, adultos, ninos)
        camas = dibujo.camas_por_habitacion(cx, [h["id"] for h in habs])
        for h in habs:
            h["camas"] = camas.get(h["id"], [])
        tipos = cx.execute("select id, nombre, capacidad from pms_tipos_habitacion where hotel_id=%s and activo order by id",
                           (hotel_id,)).fetchall()
        precios = {}
        for t in tipos:
            try:
                precios[t["id"]] = {"promedio_noche": tarifas.cotizar(cx, hotel_id, t["id"], noches)["promedio_noche"], "error": None}
            except ErrorNegocio as e:
                precios[t["id"]] = {"promedio_noche": None, "error": str(e)}
    return {"habitaciones": habs, "plantas": sorted({h["planta"] for h in habs}), "tipos": tipos, "noches": noches, "precios": precios}


def resumen(habitaciones: list[dict]) -> dict[str, int]:
    r = {e: 0 for e in disponibilidad.ESTADOS_PLANO}
    for h in habitaciones:
        r[h["estado"]] += 1
    return r


def filtrar(habitaciones: list[dict], planta: int | None = None, tipo_id: int | None = None, solo_mar: bool = False,
            ocultar_no_disponibles: bool = False, seleccionada: int | None = None) -> list[dict]:
    """Aplica los filtros del plano. Cada habitación devuelta trae `visual`: su estado, o «seleccionada» si es la elegida y sigue disponible."""
    out = []
    for h in habitaciones:
        if planta is not None and h["planta"] != planta:
            continue
        if tipo_id is not None and h["tipo_id"] != tipo_id:
            continue
        if solo_mar and not h["vista_mar"]:
            continue
        if ocultar_no_disponibles and not h["disponible"]:
            continue
        out.append({**h, "visual": "seleccionada" if h["id"] == seleccionada and h["disponible"] else h["estado"]})
    return out


def detalle(actor, hotel_id: int, habitacion_id: int, entrada: dt.date, salida: dt.date, adultos: int = 2, ninos: int = 0) -> dict:
    """Ficha de una habitación para las fechas: camas, capacidad, estado y cotización con desglose.
    `cotizacion` es None si no se puede cotizar (`error` dice por qué)."""
    _permiso(actor, hotel_id)
    noches = _noches(entrada, salida)
    with db.tx() as cx:
        hab = next((h for h in disponibilidad.estado_habitaciones(cx, hotel_id, noches, adultos, ninos) if h["id"] == habitacion_id), None)
        if hab is None:
            raise ErrorNegocio("La habitación no existe en este hotel.")
        camas = cx.execute("select tipo, ancho_cm, cantidad from pms_camas where habitacion_id=%s order by id", (habitacion_id,)).fetchall()
        cot, err = None, None
        try:
            cot = tarifas.cotizar(cx, hotel_id, hab["tipo_id"], noches, adultos + ninos)
        except ErrorNegocio as e:
            err = str(e)
    return {"habitacion": hab, "camas": camas, "camas_texto": _texto_camas(camas), "cotizacion": cot, "error": err,
            "reservable": hab["disponible"] and cot is not None, "personas": adultos + ninos, "noches": noches}


def prellenado(actor, hotel_id: int, habitacion_id: int, entrada: dt.date, salida: dt.date, adultos: int, ninos: int) -> dict:
    """Datos para abrir Reservas con todo escogido. Vuelve a comprobar la disponibilidad en este momento (por si alguien reservó
    entretanto) y exige permiso de crear reservas. La reserva real la valida otra vez `reservas.crear`."""
    seguridad.exigir(actor, "reservas")
    d = detalle(actor, hotel_id, habitacion_id, entrada, salida, adultos, ninos)
    h = d["habitacion"]
    if not h["disponible"]:
        raise ErrorNegocio(f"La habitación {h['numero']} ya no está disponible para esas fechas ({disponibilidad.NOMBRE_ESTADO_PLANO[h['estado']].lower()}).")
    if d["cotizacion"] is None:
        raise ErrorNegocio(d["error"] or "No se puede cotizar esta habitación.")
    return {"hotel_id": hotel_id, "habitacion_id": habitacion_id, "numero": h["numero"], "tipo_id": h["tipo_id"], "tipo": h["tipo"],
            "entrada": entrada, "salida": salida, "adultos": adultos, "ninos": ninos}

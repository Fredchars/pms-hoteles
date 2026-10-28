"""Tarifas por tipo de habitación y temporada, con estancia mínima y cierre de ventas."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from . import db, seguridad
from .auditoria import registrar
from .errores import ErrorNegocio
from .util import dinero, hotel_de, noches_entre


def listar(hotel_id: int) -> list[dict]:
    return db.todos("select t.*, tp.nombre tipo from pms_tarifas t join pms_tipos_habitacion tp on tp.id=t.tipo_id "
                    "where t.hotel_id=%s order by tp.id, t.fecha_desde", (hotel_id,))


def crear(actor, hotel_id: int, tipo_id: int, temporada: str, desde: dt.date, hasta: dt.date, precio,
          estancia_minima: int = 1, cierre_ventas: bool = False) -> int:
    seguridad.exigir(actor, "tarifas")
    seguridad.exigir_hotel(actor, hotel_id)
    if hasta < desde:
        raise ErrorNegocio("La fecha final de la tarifa no puede ser anterior a la inicial.")
    p = dinero(precio)
    if p < 0:
        raise ErrorNegocio("El precio no puede ser negativo.")
    if estancia_minima < 1:
        raise ErrorNegocio("La estancia mínima es de al menos 1 noche.")
    with db.tx() as cx:
        hotel_de(cx, hotel_id)
        if not cx.execute("select 1 from pms_tipos_habitacion where id=%s and hotel_id=%s", (tipo_id, hotel_id)).fetchone():
            raise ErrorNegocio("El tipo de habitación no pertenece a este hotel.")
        choque = cx.execute("select temporada from pms_tarifas where tipo_id=%s and activo and fecha_desde<=%s and fecha_hasta>=%s",
                            (tipo_id, hasta, desde)).fetchone()
        if choque:
            raise ErrorNegocio(f"Las fechas se cruzan con la tarifa «{choque['temporada']}» de este tipo de habitación.")
        r = cx.execute(
            "insert into pms_tarifas (hotel_id, tipo_id, temporada, fecha_desde, fecha_hasta, precio_noche, estancia_minima, "
            "cierre_ventas) values (%s,%s,%s,%s,%s,%s,%s,%s) returning id",
            (hotel_id, tipo_id, temporada, desde, hasta, p, estancia_minima, cierre_ventas)).fetchone()
        registrar(cx, actor, "crear", "tarifa", r["id"], despues={"tipo_id": tipo_id, "temporada": temporada, "desde": desde,
                  "hasta": hasta, "precio": p, "min": estancia_minima, "cierre": cierre_ventas}, hotel_id=hotel_id)
        return r["id"]


def actualizar(actor, tarifa_id: int, precio=None, estancia_minima=None, cierre_ventas=None, activo=None):
    """Cambiar una tarifa NO modifica reservas ya hechas: cada noche vendida conserva su precio congelado."""
    seguridad.exigir(actor, "tarifas")
    with db.tx() as cx:
        t = cx.execute("select * from pms_tarifas where id=%s", (tarifa_id,)).fetchone()
        if not t:
            raise ErrorNegocio("Tarifa no encontrada.")
        seguridad.exigir_hotel(actor, t["hotel_id"])
        nuevo = {"precio_noche": dinero(precio) if precio is not None else t["precio_noche"],
                 "estancia_minima": estancia_minima if estancia_minima is not None else t["estancia_minima"],
                 "cierre_ventas": cierre_ventas if cierre_ventas is not None else t["cierre_ventas"],
                 "activo": activo if activo is not None else t["activo"]}
        if nuevo["precio_noche"] < 0 or nuevo["estancia_minima"] < 1:
            raise ErrorNegocio("Precio o estancia mínima no válidos.")
        cx.execute("update pms_tarifas set precio_noche=%s, estancia_minima=%s, cierre_ventas=%s, activo=%s where id=%s",
                   (nuevo["precio_noche"], nuevo["estancia_minima"], nuevo["cierre_ventas"], nuevo["activo"], tarifa_id))
        registrar(cx, actor, "actualizar", "tarifa", tarifa_id,
                  antes={k: t[k] for k in nuevo}, despues=nuevo, hotel_id=t["hotel_id"])


def tarifa_de_noche(cx, tipo_id: int, noche: dt.date) -> dict | None:
    return cx.execute("select * from pms_tarifas where tipo_id=%s and activo and fecha_desde<=%s and fecha_hasta>=%s "
                      "order by fecha_desde desc limit 1", (tipo_id, noche, noche)).fetchone()


def precios_para(cx, tipo_id: int, noches: list[dt.date], validar_estancia: bool = True) -> dict[dt.date, Decimal]:
    """Precio de cada noche con la tarifa vigente. Valida: tarifa existente, ventas abiertas y estancia mínima."""
    precios = {}
    for n in noches:
        t = tarifa_de_noche(cx, tipo_id, n)
        if not t:
            raise ErrorNegocio(f"No hay tarifa configurada para la noche del {n:%d/%m/%Y}.")
        if t["cierre_ventas"]:
            raise ErrorNegocio(f"Las ventas están cerradas para la noche del {n:%d/%m/%Y} (cierre de ventas).")
        precios[n] = t["precio_noche"]
    return precios


def validar_estancia_minima(cx, tipo_id: int, entrada: dt.date, total_noches: int):
    t = tarifa_de_noche(cx, tipo_id, entrada)
    if t and total_noches < t["estancia_minima"]:
        raise ErrorNegocio(f"La estancia mínima para entrar el {entrada:%d/%m/%Y} es de {t['estancia_minima']} noches.")

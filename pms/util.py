from __future__ import annotations

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from . import db
from .errores import ErrorNegocio

D2 = Decimal("0.01")


def dinero(x) -> Decimal:
    return Decimal(str(x)).quantize(D2, rounding=ROUND_HALF_UP)


def hoy_hotel(cx_or_none, hotel_id: int) -> dt.date:
    """Fecha de hoy en la zona horaria del hotel."""
    h = (cx_or_none.execute("select zona_horaria from pms_hoteles where id=%s", (hotel_id,)).fetchone()
         if cx_or_none else db.uno("select zona_horaria from pms_hoteles where id=%s", (hotel_id,)))
    tz = ZoneInfo(h["zona_horaria"]) if h else ZoneInfo("UTC")
    return dt.datetime.now(tz).date()


def noches_entre(entrada: dt.date, salida: dt.date) -> list[dt.date]:
    if salida <= entrada:
        raise ErrorNegocio("La fecha de salida debe ser posterior a la de entrada.")
    return [entrada + dt.timedelta(days=i) for i in range((salida - entrada).days)]


def fmt_moneda(valor, moneda: str) -> str:
    v = Decimal(str(valor or 0))
    dec = 0 if moneda in ("COP", "CLP", "PYG", "JPY") else 2
    s = f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{moneda} {s}"


def hotel_de(cx, hotel_id: int) -> dict:
    h = cx.execute("select * from pms_hoteles where id=%s", (hotel_id,)).fetchone()
    if not h:
        raise ErrorNegocio("Hotel no encontrado.")
    return h

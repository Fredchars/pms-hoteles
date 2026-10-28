"""Registro de cambios importantes (quién, cuándo, qué había antes). Solo se agrega; la base impide editar o borrar."""
from __future__ import annotations

import datetime as dt
import decimal
import json

from .db import Jsonb


def _limpio(v):
    if v is None:
        return None
    return json.loads(json.dumps(v, default=_ser))


def _ser(o):
    if isinstance(o, decimal.Decimal):
        return float(o)
    if isinstance(o, (dt.date, dt.datetime)):
        return o.isoformat()
    return str(o)


def registrar(cx, actor: dict | None, accion: str, entidad: str, entidad_id=None, antes=None, despues=None,
              hotel_id: int | None = None, email: str | None = None):
    cx.execute(
        "insert into pms_auditoria (hotel_id, usuario_id, usuario_email, accion, entidad, entidad_id, antes, despues) "
        "values (%s,%s,%s,%s,%s,%s,%s,%s)",
        (hotel_id, actor["id"] if actor else None, (actor or {}).get("email") or email, accion, entidad,
         None if entidad_id is None else str(entidad_id),
         Jsonb(_limpio(antes)) if antes is not None else None,
         Jsonb(_limpio(despues)) if despues is not None else None))

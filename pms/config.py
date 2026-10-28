"""Configuración: hoteles (país, moneda, zona horaria), impuestos genéricos, tipos, habitaciones, camas y usuarios.
Solo el administrador modifica; gerencia consulta."""
from __future__ import annotations

import re
from zoneinfo import ZoneInfo

from . import db, seguridad
from .auditoria import registrar
from .errores import ErrorNegocio
from .util import hotel_de

MONEDA_RE = re.compile(r"^[A-Z]{3}$")
TIPOS_CAMA = ["matrimonial", "individual", "litera", "sofa_cama", "cuna"]


def hoteles_visibles(actor: dict) -> list[dict]:
    if actor.get("hotel_id") is not None:
        return db.todos("select * from pms_hoteles where id=%s and activo order by nombre", (actor["hotel_id"],))
    return db.todos("select * from pms_hoteles where activo order by nombre")


def crear_hotel(actor, nombre: str, pais: str, moneda: str, zona_horaria: str) -> int:
    seguridad.exigir(actor, "configuracion")
    moneda = (moneda or "").upper().strip()
    if not nombre.strip() or not pais.strip():
        raise ErrorNegocio("El nombre y el país son obligatorios.")
    if not MONEDA_RE.match(moneda):
        raise ErrorNegocio("La moneda debe ser un código de 3 letras (por ejemplo COP, DOP, USD).")
    try:
        ZoneInfo(zona_horaria)
    except Exception:
        raise ErrorNegocio("Zona horaria no válida (ejemplo: America/Bogota).")
    with db.tx() as cx:
        h = cx.execute("insert into pms_hoteles (nombre, pais, moneda, zona_horaria) values (%s,%s,%s,%s) returning id",
                       (nombre.strip(), pais.strip(), moneda, zona_horaria)).fetchone()
        registrar(cx, actor, "crear", "hotel", h["id"], despues={"nombre": nombre, "pais": pais, "moneda": moneda},
                  hotel_id=h["id"])
        return h["id"]


def actualizar_hotel(actor, hotel_id: int, **campos):
    seguridad.exigir(actor, "configuracion")
    permitidos = {"nombre", "pais", "moneda", "zona_horaria", "activo"}
    campos = {k: v for k, v in campos.items() if k in permitidos}
    if "moneda" in campos:
        campos["moneda"] = campos["moneda"].upper().strip()
        if not MONEDA_RE.match(campos["moneda"]):
            raise ErrorNegocio("La moneda debe ser un código de 3 letras.")
    if not campos:
        return
    with db.tx() as cx:
        antes = hotel_de(cx, hotel_id)
        sets = ", ".join(f"{k}=%s" for k in campos)
        cx.execute(f"update pms_hoteles set {sets} where id=%s", (*campos.values(), hotel_id))
        registrar(cx, actor, "actualizar", "hotel", hotel_id, antes={k: antes[k] for k in campos}, despues=campos,
                  hotel_id=hotel_id)


# ---------- impuestos ----------
def impuestos(hotel_id: int, solo_activos=True) -> list[dict]:
    return db.todos("select * from pms_impuestos where hotel_id=%s" + (" and activo" if solo_activos else "") +
                    " order by id", (hotel_id,))


def guardar_impuesto(actor, hotel_id: int, nombre: str, porcentaje, activo: bool = True) -> int:
    """Crea o actualiza (por nombre) un impuesto genérico del hotel. Solo afecta a cargos futuros."""
    seguridad.exigir(actor, "configuracion")
    seguridad.exigir_hotel(actor, hotel_id)
    try:
        p = float(porcentaje)
    except (TypeError, ValueError):
        raise ErrorNegocio("El porcentaje debe ser un número.")
    if not nombre.strip():
        raise ErrorNegocio("El impuesto necesita un nombre.")
    if p < 0 or p > 100:
        raise ErrorNegocio("El porcentaje debe estar entre 0 y 100.")
    with db.tx() as cx:
        hotel_de(cx, hotel_id)
        antes = cx.execute("select * from pms_impuestos where hotel_id=%s and nombre=%s",
                           (hotel_id, nombre.strip())).fetchone()
        r = cx.execute(
            "insert into pms_impuestos (hotel_id, nombre, porcentaje, activo) values (%s,%s,%s,%s) "
            "on conflict (hotel_id, nombre) do update set porcentaje=excluded.porcentaje, activo=excluded.activo "
            "returning id", (hotel_id, nombre.strip(), p, activo)).fetchone()
        registrar(cx, actor, "actualizar" if antes else "crear", "impuesto", r["id"],
                  antes={"porcentaje": antes["porcentaje"], "activo": antes["activo"]} if antes else None,
                  despues={"nombre": nombre.strip(), "porcentaje": p, "activo": activo}, hotel_id=hotel_id)
        return r["id"]


def impuestos_congelados(cx, hotel_id: int) -> list[dict]:
    """Impuestos activos del hotel en este momento, listos para guardarse junto a cada cargo."""
    return [{"nombre": i["nombre"], "porcentaje": float(i["porcentaje"])} for i in cx.execute(
        "select nombre, porcentaje from pms_impuestos where hotel_id=%s and activo order by id",
        (hotel_id,)).fetchall()]


# ---------- tipos, habitaciones y camas ----------
def tipos(hotel_id: int, solo_activos=True) -> list[dict]:
    return db.todos("select * from pms_tipos_habitacion where hotel_id=%s" + (" and activo" if solo_activos else "") +
                    " order by id", (hotel_id,))


def crear_tipo(actor, hotel_id: int, nombre: str, capacidad: int, descripcion: str = "") -> int:
    seguridad.exigir(actor, "configuracion")
    seguridad.exigir_hotel(actor, hotel_id)
    if capacidad < 1:
        raise ErrorNegocio("La capacidad debe ser al menos 1 persona.")
    with db.tx() as cx:
        hotel_de(cx, hotel_id)
        if cx.execute("select 1 from pms_tipos_habitacion where hotel_id=%s and nombre=%s",
                      (hotel_id, nombre.strip())).fetchone():
            raise ErrorNegocio("Ya existe un tipo con ese nombre.")
        r = cx.execute("insert into pms_tipos_habitacion (hotel_id, nombre, capacidad, descripcion) "
                       "values (%s,%s,%s,%s) returning id", (hotel_id, nombre.strip(), capacidad, descripcion)).fetchone()
        registrar(cx, actor, "crear", "tipo_habitacion", r["id"], despues={"nombre": nombre, "capacidad": capacidad},
                  hotel_id=hotel_id)
        return r["id"]


def habitaciones(hotel_id: int, solo_activas=True) -> list[dict]:
    return db.todos(
        "select h.*, t.nombre tipo, t.capacidad from pms_habitaciones h join pms_tipos_habitacion t on t.id=h.tipo_id "
        "where h.hotel_id=%s" + (" and h.activo" if solo_activas else "") + " order by h.planta, h.numero", (hotel_id,))


def crear_habitacion(actor, hotel_id: int, numero: str, planta: int, tipo_id: int, metros: int | None = None,
                     vista: str = "", camas: list[tuple[str, int | None, int]] | None = None) -> int:
    """camas = [(tipo, ancho_cm, cantidad)]: información de la habitación; no se vende cama por cama."""
    seguridad.exigir(actor, "configuracion")
    seguridad.exigir_hotel(actor, hotel_id)
    with db.tx() as cx:
        t = cx.execute("select * from pms_tipos_habitacion where id=%s and hotel_id=%s", (tipo_id, hotel_id)).fetchone()
        if not t:
            raise ErrorNegocio("El tipo de habitación no pertenece a este hotel.")
        if cx.execute("select 1 from pms_habitaciones where hotel_id=%s and numero=%s", (hotel_id, numero)).fetchone():
            raise ErrorNegocio(f"Ya existe la habitación {numero}.")
        r = cx.execute("insert into pms_habitaciones (hotel_id, numero, planta, tipo_id, metros, vista) "
                       "values (%s,%s,%s,%s,%s,%s) returning id", (hotel_id, numero, planta, tipo_id, metros, vista)).fetchone()
        for tipo, ancho, cant in camas or []:
            if tipo not in TIPOS_CAMA:
                raise ErrorNegocio(f"Tipo de cama no válido: {tipo}")
            cx.execute("insert into pms_camas (hotel_id, habitacion_id, tipo, ancho_cm, cantidad) values (%s,%s,%s,%s,%s)",
                       (hotel_id, r["id"], tipo, ancho, cant))
        registrar(cx, actor, "crear", "habitacion", r["id"], despues={"numero": numero, "tipo_id": tipo_id}, hotel_id=hotel_id)
        return r["id"]


def camas(hotel_id: int) -> list[dict]:
    return db.todos("select c.*, h.numero from pms_camas c join pms_habitaciones h on h.id=c.habitacion_id "
                    "where c.hotel_id=%s order by h.numero, c.id", (hotel_id,))


# ---------- usuarios ----------
def usuarios(actor) -> list[dict]:
    seguridad.exigir(actor, "configuracion", editar=False)
    q = "select id, hotel_id, email, nombre, rol, activo, ultimo_acceso from pms_usuarios"
    if actor.get("hotel_id") is not None:
        return db.todos(q + " where hotel_id=%s order by rol, email", (actor["hotel_id"],))
    return db.todos(q + " order by hotel_id nulls first, rol, email")


def crear_usuario(actor, email: str, nombre: str, rol: str, clave: str, hotel_id: int | None) -> int:
    seguridad.exigir(actor, "configuracion")
    if rol not in seguridad.ROLES:
        raise ErrorNegocio("Rol no válido.")
    email = email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ErrorNegocio("El correo no es válido.")
    if rol != "administrador" and hotel_id is None:
        raise ErrorNegocio("Este rol necesita un hotel asignado.")
    h = seguridad.hash_clave(clave)
    with db.tx() as cx:
        if cx.execute("select 1 from pms_usuarios where lower(email)=%s", (email,)).fetchone():
            raise ErrorNegocio("Ya existe un usuario con ese correo.")
        r = cx.execute("insert into pms_usuarios (hotel_id, email, nombre, rol, clave_hash) values (%s,%s,%s,%s,%s) returning id",
                       (hotel_id, email, nombre.strip(), rol, h)).fetchone()
        registrar(cx, actor, "crear", "usuario", r["id"], despues={"email": email, "rol": rol, "hotel_id": hotel_id},
                  hotel_id=hotel_id)
        return r["id"]


def activar_usuario(actor, usuario_id: int, activo: bool):
    seguridad.exigir(actor, "configuracion")
    if usuario_id == actor["id"] and not activo:
        raise ErrorNegocio("No puedes desactivar tu propio usuario.")
    with db.tx() as cx:
        cx.execute("update pms_usuarios set activo=%s where id=%s", (activo, usuario_id))
        registrar(cx, actor, "activar" if activo else "desactivar", "usuario", usuario_id)

"""Huéspedes (datos ficticios en el piloto) y consentimientos de tratamiento de datos (Ley 1581 de Colombia)."""
from __future__ import annotations

import re

from . import db, seguridad
from .auditoria import registrar
from .errores import ErrorNegocio

VERSION_TEXTO = "v1.0-2026"
FINALIDADES = {
    "prestacion_servicio": ("Prestación del servicio de alojamiento",
                            "Autorizo el tratamiento de mis datos personales para gestionar mi reserva, mi estancia y la "
                            "comunicación necesaria con el hotel (Ley 1581 de 2012, Colombia)."),
    "facturacion": ("Facturación y cobros",
                    "Autorizo el uso de mis datos para emitir comprobantes y registrar los pagos de mi estancia."),
    "marketing": ("Comunicaciones comerciales (opcional)",
                  "Autorizo recibir información de ofertas del hotel. Puedo revocar esta autorización cuando quiera."),
}


def buscar(actor, hotel_id: int, texto: str = "") -> list[dict]:
    seguridad.exigir(actor, "huespedes", editar=False)
    seguridad.exigir_hotel(actor, hotel_id)
    t = f"%{texto.strip()}%"
    return db.todos("select * from pms_huespedes where hotel_id=%s and (nombres ilike %s or apellidos ilike %s or "
                    "coalesce(email,'') ilike %s or coalesce(numero_documento,'') ilike %s) order by apellidos, nombres limit 200",
                    (hotel_id, t, t, t, t))


def crear(actor, hotel_id: int, nombres: str, apellidos: str, tipo_documento: str = "", numero_documento: str = "",
          email: str = "", telefono: str = "", pais: str = "") -> int:
    seguridad.exigir(actor, "huespedes")
    seguridad.exigir_hotel(actor, hotel_id)
    if not nombres.strip() or not apellidos.strip():
        raise ErrorNegocio("Nombres y apellidos son obligatorios.")
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ErrorNegocio("El correo del huésped no es válido.")
    with db.tx() as cx:
        r = cx.execute("insert into pms_huespedes (hotel_id, nombres, apellidos, tipo_documento, numero_documento, email, "
                       "telefono, pais) values (%s,%s,%s,%s,%s,%s,%s,%s) returning id",
                       (hotel_id, nombres.strip(), apellidos.strip(), tipo_documento or None, numero_documento or None,
                        email or None, telefono or None, pais or None)).fetchone()
        registrar(cx, actor, "crear", "huesped", r["id"], despues={"nombres": nombres, "apellidos": apellidos},
                  hotel_id=hotel_id)
        return r["id"]


def actualizar(actor, huesped_id: int, **campos):
    seguridad.exigir(actor, "huespedes")
    ok = {"nombres", "apellidos", "tipo_documento", "numero_documento", "email", "telefono", "pais"}
    campos = {k: (v or None) for k, v in campos.items() if k in ok}
    with db.tx() as cx:
        h = cx.execute("select * from pms_huespedes where id=%s", (huesped_id,)).fetchone()
        if not h:
            raise ErrorNegocio("Huésped no encontrado.")
        seguridad.exigir_hotel(actor, h["hotel_id"])
        if h["anonimizado"]:
            raise ErrorNegocio("Este huésped fue anonimizado y no se puede editar.")
        if campos:
            cx.execute(f"update pms_huespedes set {', '.join(f'{k}=%s' for k in campos)} where id=%s", (*campos.values(), huesped_id))
            registrar(cx, actor, "actualizar", "huesped", huesped_id, antes={k: h[k] for k in campos}, despues=campos,
                      hotel_id=h["hotel_id"])


def registrar_consentimiento(actor, huesped_id: int, finalidad: str, aceptado: bool = True) -> int:
    """Guarda una fila por finalidad con fecha, texto aceptado y versión (no se sobrescribe: queda el historial)."""
    seguridad.exigir(actor, "huespedes")
    if finalidad not in FINALIDADES:
        raise ErrorNegocio("Finalidad no válida.")
    with db.tx() as cx:
        h = cx.execute("select * from pms_huespedes where id=%s", (huesped_id,)).fetchone()
        if not h:
            raise ErrorNegocio("Huésped no encontrado.")
        seguridad.exigir_hotel(actor, h["hotel_id"])
        r = cx.execute("insert into pms_consentimientos (hotel_id, huesped_id, finalidad, aceptado, texto, version, registrado_por) "
                       "values (%s,%s,%s,%s,%s,%s,%s) returning id",
                       (h["hotel_id"], huesped_id, finalidad, aceptado, FINALIDADES[finalidad][1], VERSION_TEXTO,
                        actor["id"])).fetchone()
        registrar(cx, actor, "consentimiento_aceptado" if aceptado else "consentimiento_rechazado", "huesped", huesped_id,
                  despues={"finalidad": finalidad, "version": VERSION_TEXTO}, hotel_id=h["hotel_id"])
        return r["id"]


def revocar_consentimiento(actor, huesped_id: int, finalidad: str):
    seguridad.exigir(actor, "huespedes")
    with db.tx() as cx:
        h = cx.execute("select * from pms_huespedes where id=%s", (huesped_id,)).fetchone()
        if not h:
            raise ErrorNegocio("Huésped no encontrado.")
        seguridad.exigir_hotel(actor, h["hotel_id"])
        n = cx.execute("update pms_consentimientos set revocado_en=now() where huesped_id=%s and finalidad=%s and aceptado "
                       "and revocado_en is null", (huesped_id, finalidad)).rowcount
        if not n:
            raise ErrorNegocio("No hay un consentimiento vigente para revocar.")
        registrar(cx, actor, "consentimiento_revocado", "huesped", huesped_id, despues={"finalidad": finalidad},
                  hotel_id=h["hotel_id"])


def consentimiento_vigente(cx, huesped_id: int, finalidad: str = "prestacion_servicio") -> bool:
    return bool(cx.execute("select 1 from pms_consentimientos where huesped_id=%s and finalidad=%s and aceptado "
                           "and revocado_en is null limit 1", (huesped_id, finalidad)).fetchone())


def consentimientos(huesped_id: int) -> list[dict]:
    return db.todos("select * from pms_consentimientos where huesped_id=%s order by fecha desc, id desc", (huesped_id,))


def anonimizar(actor, huesped_id: int):
    """Supresión de datos (derecho de supresión, Ley 1581): solo gerencia y solo si no tiene estancias activas o futuras."""
    if actor.get("rol") != "gerencia":
        raise seguridad.PermisoDenegado("Solo gerencia puede anonimizar a un huésped.")
    with db.tx() as cx:
        h = cx.execute("select * from pms_huespedes where id=%s", (huesped_id,)).fetchone()
        if not h:
            raise ErrorNegocio("Huésped no encontrado.")
        seguridad.exigir_hotel(actor, h["hotel_id"])
        if cx.execute("select 1 from pms_reservas where huesped_id=%s and estado in ('consulta','opcion','confirmada','alojado')",
                      (huesped_id,)).fetchone():
            raise ErrorNegocio("El huésped tiene reservas vigentes: cancélalas o termina la estancia antes de anonimizar.")
        cx.execute("update pms_huespedes set nombres='ANONIMIZADO', apellidos=%s, tipo_documento=null, numero_documento=null, "
                   "email=null, telefono=null, pais=null, anonimizado=true where id=%s", (f"#{huesped_id}", huesped_id))
        cx.execute("update pms_consentimientos set revocado_en=coalesce(revocado_en, now()) where huesped_id=%s", (huesped_id,))
        registrar(cx, actor, "anonimizar", "huesped", huesped_id, hotel_id=h["hotel_id"])

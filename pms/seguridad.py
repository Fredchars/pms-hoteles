"""Roles, permisos por pantalla, contraseñas con hash, sesión firmada (persiste al recargar) y control del modo demo."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time

import bcrypt

from . import db
from .auditoria import registrar
from .errores import ErrorNegocio, PermisoDenegado

ROLES = ["recepcion", "gerencia", "housekeeping", "administrador"]
ROL_NOMBRE = {"recepcion": "Recepción", "gerencia": "Gerencia", "housekeeping": "Housekeeping",
              "administrador": "Administrador del sistema"}

# x = puede usar y modificar · ver = solo consultar · ausente = sin acceso (sección 5 del diseño aprobado)
PERMISOS: dict[str, dict[str, str]] = {
    "dashboard":     {"recepcion": "x", "gerencia": "x", "administrador": "ver"},
    "calendario":    {"recepcion": "x", "gerencia": "x", "administrador": "ver"},
    "reservas":      {"recepcion": "x", "gerencia": "x", "administrador": "ver"},
    "huespedes":     {"recepcion": "x", "gerencia": "x", "administrador": "ver"},
    "housekeeping":  {"recepcion": "ver", "gerencia": "x", "housekeeping": "x", "administrador": "ver"},
    "bloqueos":      {"recepcion": "ver", "gerencia": "x", "housekeeping": "ver", "administrador": "x"},
    "tarifas":       {"recepcion": "ver", "gerencia": "x", "administrador": "x"},
    "facturacion":   {"recepcion": "x", "gerencia": "x", "administrador": "ver"},
    "reportes":      {"gerencia": "x", "administrador": "x"},
    "configuracion": {"gerencia": "ver", "administrador": "x"},
    "auditoria":     {"gerencia": "ver", "administrador": "ver"},
}
MAX_FALLOS = 5
VENTANA_FALLOS_MIN = 15
DURACION_SESION_S = 8 * 3600
MIN_CLAVE_NUEVA = 10          # la contraseña que cada persona crea en su primer ingreso
ALFABETO_TEMPORAL = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"   # sin caracteres que se confunden (0/O, 1/l/I)


def nivel(rol: str, pantalla: str) -> str | None:
    return PERMISOS.get(pantalla, {}).get(rol)


def puede(actor: dict, pantalla: str, editar: bool = False) -> bool:
    n = nivel(actor["rol"], pantalla)
    return n == "x" if editar else n in ("x", "ver")


def exigir(actor: dict, pantalla: str, editar: bool = True):
    """Lanza PermisoDenegado si el rol no puede usar la pantalla (o modificarla si editar=True)."""
    if not actor or not puede(actor, pantalla, editar):
        accion = "modificar" if editar else "ver"
        raise PermisoDenegado(f"Tu rol no tiene permiso para {accion} «{pantalla}».")


def exigir_hotel(actor: dict, hotel_id: int):
    """Un usuario con hotel asignado solo trabaja en su hotel; hotel_id vacío = todos los hoteles."""
    if actor.get("hotel_id") is not None and actor["hotel_id"] != hotel_id:
        raise PermisoDenegado("Este usuario no tiene acceso a ese hotel.")


def exigir_aprobador(actor: dict, solicitante_id: int | None):
    """Solo gerencia aprueba, y nunca quien solicitó (separación de funciones)."""
    if actor.get("rol") != "gerencia":
        raise PermisoDenegado("Solo gerencia puede aprobar o rechazar.")
    if solicitante_id is not None and actor["id"] == solicitante_id:
        raise PermisoDenegado("Quien registra la solicitud no puede aprobarla: pídelo a otra persona de gerencia.")


# ---------- contraseñas ----------
def hash_clave(clave: str) -> str:
    if len(clave) < 8:
        raise ErrorNegocio("La contraseña debe tener al menos 8 caracteres.")
    return bcrypt.hashpw(clave.encode(), bcrypt.gensalt(rounds=10)).decode()


def verificar_clave(clave: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(clave.encode(), h.encode())
    except ValueError:
        return False


def actor_de(u: dict) -> dict:
    """Actor de la sesión. `debe_cambiar_clave` bloquea toda la aplicación hasta crear la contraseña propia (no aplica en modo demo);
    `huella` identifica la contraseña vigente: si cambia, la sesión se cierra."""
    return {"id": u["id"], "email": u["email"], "nombre": u["nombre"], "rol": u["rol"], "hotel_id": u["hotel_id"],
            "debe_cambiar_clave": bool(u.get("debe_cambiar_clave")) and not demo_permitido(),
            "huella": _huella_clave(u["clave_hash"]) if u.get("clave_hash") else None}


def iniciar_sesion(email: str, clave: str) -> dict:
    """Valida correo y contraseña (hash bcrypt). Bloquea 15 min tras 5 fallos. Devuelve el actor."""
    email = (email or "").strip().lower()
    error = None
    actor = None
    with db.tx() as cx:
        fallos = cx.execute(
            "select count(*) n from pms_auditoria where accion='login_fallido' and usuario_email=%s "
            "and creado > now() - make_interval(mins => %s)", (email, VENTANA_FALLOS_MIN)).fetchone()["n"]
        if fallos >= MAX_FALLOS:
            return _fallo("Demasiados intentos fallidos. Espera 15 minutos e intenta de nuevo.")
        u = cx.execute("select * from pms_usuarios where lower(email)=%s", (email,)).fetchone()
        if not u or not u["activo"] or not verificar_clave(clave or "", u["clave_hash"]):
            # el fallo se guarda (la transacción se confirma) y el error se lanza después
            registrar(cx, None, "login_fallido", "usuario", email, hotel_id=u["hotel_id"] if u else None, email=email)
            error = "Correo o contraseña incorrectos."
        else:
            cx.execute("update pms_usuarios set ultimo_acceso=now() where id=%s", (u["id"],))
            registrar(cx, actor_de(u), "login", "usuario", str(u["id"]), hotel_id=u["hotel_id"])
            actor = actor_de(u)
    if error:
        raise ErrorNegocio(error)
    return actor


def _fallo(msg: str):
    raise ErrorNegocio(msg)


def cambiar_clave(actor: dict, usuario_id: int, nueva: str):
    """Cada persona cambia la suya; el administrador puede cambiar la de cualquiera.
    Si la cambia el administrador a otra persona, esa persona debe crear la suya al ingresar (el administrador la conoce)."""
    if actor["id"] != usuario_id and actor["rol"] != "administrador":
        raise PermisoDenegado("Solo el administrador puede cambiar la contraseña de otra persona.")
    h = hash_clave(nueva)
    propia = actor["id"] == usuario_id
    with db.tx() as cx:
        cx.execute("update pms_usuarios set clave_hash=%s, debe_cambiar_clave=%s where id=%s", (h, not propia, usuario_id))
        registrar(cx, actor, "cambio_clave", "usuario", str(usuario_id))


def clave_temporal_nueva() -> str:
    """Contraseña aleatoria segura (14 caracteres) sin caracteres ambiguos."""
    return "".join(secrets.choice(ALFABETO_TEMPORAL) for _ in range(14))


def generar_clave_temporal(actor: dict, usuario_id: int) -> str:
    """Solo administrador. Crea una contraseña aleatoria, exige cambiarla al ingresar y cierra las sesiones anteriores
    (cambia la huella). Devuelve la clave en claro UNA vez: no se guarda ni se audita."""
    exigir(actor, "configuracion")
    if actor["id"] == usuario_id:
        raise ErrorNegocio("No generes una contraseña temporal para ti mismo: usa «Cambiar contraseña».")
    nueva = clave_temporal_nueva()
    h = hash_clave(nueva)
    with db.tx() as cx:
        u = cx.execute("select id, hotel_id, email from pms_usuarios where id=%s", (usuario_id,)).fetchone()
        if not u:
            raise ErrorNegocio("Usuario no encontrado.")
        cx.execute("update pms_usuarios set clave_hash=%s, debe_cambiar_clave=true where id=%s", (h, usuario_id))
        registrar(cx, actor, "clave_temporal", "usuario", str(usuario_id), despues={"debe_cambiar_clave": True, "usuario": u["email"]},
                  hotel_id=u["hotel_id"])
    return nueva


def validar_clave_nueva(actual_hash: str, nueva: str, confirmacion: str):
    if len(nueva or "") < MIN_CLAVE_NUEVA:
        raise ErrorNegocio(f"La contraseña nueva debe tener al menos {MIN_CLAVE_NUEVA} caracteres.")
    if nueva != confirmacion:
        raise ErrorNegocio("La confirmación no coincide con la contraseña nueva.")
    if verificar_clave(nueva, actual_hash):
        raise ErrorNegocio("La contraseña nueva no puede ser igual a la temporal.")


def crear_clave_propia(actor: dict, nueva: str, confirmacion: str) -> dict:
    """Primer ingreso: la persona reemplaza la contraseña temporal por la suya. Baja la bandera, audita y devuelve el actor ya habilitado."""
    u = db.uno("select * from pms_usuarios where id=%s", (actor["id"],))
    if not u or not u["activo"]:
        raise ErrorNegocio("Usuario no disponible.")
    if not u["debe_cambiar_clave"]:
        return actor_de(u)
    validar_clave_nueva(u["clave_hash"], nueva, confirmacion)
    cambiar_clave(actor, actor["id"], nueva)            # misma regla de siempre (hash bcrypt, auditoría, baja la bandera)
    with db.tx() as cx:
        registrar(cx, actor, "clave_inicial_creada", "usuario", str(actor["id"]), hotel_id=u["hotel_id"])
    return actor_de(db.uno("select * from pms_usuarios where id=%s", (actor["id"],)))


def refrescar_actor(actor: dict) -> dict | None:
    """Se llama en cada ejecución: confirma que el usuario sigue activo y que su contraseña no cambió (si cambió, la sesión se cierra)
    y trae la bandera `debe_cambiar_clave` actual. Devuelve None si la sesión ya no vale."""
    u = db.uno("select * from pms_usuarios where id=%s", (actor["id"],))
    if not u or not u["activo"]:
        return None
    nuevo = actor_de(u)
    if actor.get("huella") and actor["huella"] != nuevo["huella"]:
        return None
    return nuevo


# ---------- sesión firmada (se guarda en la dirección de la página: recargar no cierra la sesión) ----------
def _secreto() -> bytes:
    s = os.environ.get("PMS_SESION_SECRETO", "")
    if not s:
        try:
            import streamlit as st
            s = str(st.secrets.get("PMS_SESION_SECRETO", ""))
        except Exception:
            s = ""
    if not s:
        base = os.environ.get("DATABASE_URL", "")
        s = hashlib.sha256(("pms-sesion|" + base).encode()).hexdigest() if base else "pms-desarrollo-local"
    return s.encode()


def _huella_clave(clave_hash: str) -> str:
    return hashlib.sha256(clave_hash.encode()).hexdigest()[:10]


def emitir_token(usuario_id: int, clave_hash: str, ahora: float | None = None) -> str:
    return _emitir(usuario_id, _huella_clave(clave_hash), ahora)


def _emitir(usuario_id: int, huella: str, ahora: float | None = None) -> str:
    exp = int((ahora or time.time()) + DURACION_SESION_S)
    cuerpo = f"{usuario_id}.{exp}.{huella}"
    firma = hmac.new(_secreto(), cuerpo.encode(), hashlib.sha256).hexdigest()[:32]
    return base64.urlsafe_b64encode(f"{cuerpo}.{firma}".encode()).decode().rstrip("=")


def validar_token(token: str | None, ahora: float | None = None) -> dict | None:
    """Devuelve el actor si el token es auténtico, no venció y la contraseña no cambió; si no, None."""
    if not token:
        return None
    try:
        crudo = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
        uid, exp, huella, firma = crudo.split(".")
        esperada = hmac.new(_secreto(), f"{uid}.{exp}.{huella}".encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(firma, esperada) or int(exp) < (ahora or time.time()):
            return None
        u = db.uno("select * from pms_usuarios where id=%s", (int(uid),))
    except Exception:
        return None
    if not u or not u["activo"] or _huella_clave(u["clave_hash"]) != huella:
        return None
    return actor_de(u)


def token_para(actor: dict) -> str:
    if actor.get("huella"):
        return _emitir(actor["id"], actor["huella"])
    u = db.uno("select clave_hash from pms_usuarios where id=%s", (actor["id"],))
    return emitir_token(actor["id"], u["clave_hash"])


# ---------- modo demo ----------
def demo_permitido(entorno: dict | None = None) -> bool:
    """El acceso rápido de demostración solo existe si PMS_MODO_DEMO=si y el entorno NO es producción."""
    e = entorno if entorno is not None else os.environ
    if str(e.get("PMS_ENTORNO", "")).lower() in ("produccion", "producción", "prod"):
        return False
    return str(e.get("PMS_MODO_DEMO", "")).strip().lower() in ("si", "sí", "1", "true")


def entrar_demo(usuario_id: int, entorno: dict | None = None) -> dict:
    if not demo_permitido(entorno):
        raise PermisoDenegado("El acceso de demostración está apagado.")
    u = db.uno("select * from pms_usuarios where id=%s and activo", (usuario_id,))
    if not u:
        raise ErrorNegocio("Usuario no encontrado.")
    with db.tx() as cx:
        registrar(cx, actor_de(u), "login_demo", "usuario", str(u["id"]), hotel_id=u["hotel_id"])
    return actor_de(u)

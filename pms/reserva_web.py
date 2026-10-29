"""Reserva web (prototipo, fase 1): lo que el público puede hacer, y lo que el PMS interno ve de ello.

Principios de seguridad:
  · Solo este módulo se usa desde la web pública; nunca devuelve datos internos (otros huéspedes, auditoría, usuarios, motivos de bloqueo).
  · Cada reserva web se identifica por un número legible PMS-AAAA-XXXXXX (no adivinable) y se opera con un token secreto del enlace
    (en la base solo está su hash). Un número sin token válido no muestra nada.
  · Las ventas usan el mismo cerrojo por hotel y la misma restricción única habitación+noche del PMS: no hay doble venta.
  · Entradas validadas (fechas, personas, nombres, correo) y límites de abuso por IP y por correo (solo hashes, nunca el dato en claro).
Flujo y estados: bloqueada (15 min) → pago_pendiente → pagada → confirmada · o expirada / fallida / cancelada."""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import re
import secrets
from decimal import Decimal

import psycopg.errors as pge

from . import correo, db, dibujo, disponibilidad, facturacion, huespedes, pasarela, tarifas, vencimientos
from .auditoria import registrar
from .errores import ErrorNegocio
from .reservas import _insertar_noches, _lock_hotel, _recalcular, _traducir, _validar_ocupacion
from .util import dinero, fmt_moneda, hoy_hotel, noches_entre

CANAL = "web"
ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"                 # sin 0/O/1/I/L para que se pueda dictar por teléfono
RE_NUMERO = re.compile(r"^PMS-\d{4}-[A-Z2-9]{6}$")
MAX_NOCHES, MAX_ANTICIPACION_DIAS, MAX_PERSONAS = 30, 365, 8
LIMITE_IP_POR_HORA, LIMITE_ACTIVAS_POR_IP, LIMITE_ACTIVAS_POR_CORREO = 8, 3, 2
GRACIA_PAGO_MIN = 5                                          # al pasar a pagar, el bloqueo dura al menos 5 min más
PLACEHOLDER = ("Cliente web", "(datos pendientes)")
ESTADO_TEXTO = {"bloqueada": "Habitación bloqueada (falta tu pago)", "pago_pendiente": "Pago en curso", "pagada": "Pago recibido",
                "confirmada": "Reserva confirmada", "expirada": "El bloqueo venció", "fallida": "Pago rechazado: puedes reintentar",
                "cancelada": "Cancelada"}
ABIERTOS = ("bloqueada", "pago_pendiente", "fallida")        # estados en los que todavía hay un bloqueo vigente


# ---------- utilidades ----------
def _h(valor: str) -> str:
    return hashlib.sha256(valor.encode()).hexdigest()


def _hmac(valor: str) -> str:
    return hmac.new(pasarela.secreto_publico(), valor.strip().lower().encode(), hashlib.sha256).hexdigest()[:32]


def _limpio(texto: str, maximo: int, campo: str, obligatorio=True) -> str:
    t = re.sub(r"\s+", " ", (texto or "")).strip()
    if obligatorio and not t:
        raise ErrorNegocio(f"{campo} es obligatorio.")
    if len(t) > maximo or re.search(r"[<>\x00-\x1f]", t):
        raise ErrorNegocio(f"{campo} no es válido.")
    return t


def token_de(numero: str) -> str:
    """Token secreto del enlace «ver mi reserva»: HMAC del número con el secreto del servidor (no se puede deducir del número y
    permite armar el enlace del correo aunque la confirmación llegue por un webhook, sin guardar el token en claro)."""
    return hmac.new(pasarela.secreto_publico(), ("token|" + numero).encode(), hashlib.sha256).hexdigest()[:32]


def _nuevo_numero(cx, hotel_id: int) -> str:
    anio = hoy_hotel(cx, hotel_id).year
    for _ in range(20):
        n = f"PMS-{anio}-" + "".join(secrets.choice(ALFABETO) for _ in range(6))
        if not cx.execute("select 1 from pms_reservas_web where numero_publico=%s", (n,)).fetchone():
            return n
    raise ErrorNegocio("No se pudo generar el número de reserva. Intenta de nuevo.")


def _validar_busqueda(cx, hotel_id, entrada, salida, adultos, ninos):
    hotel = cx.execute("select * from pms_hoteles where id=%s and activo", (hotel_id,)).fetchone()
    if not hotel:
        raise ErrorNegocio("Hotel no disponible.")
    if not isinstance(entrada, dt.date) or not isinstance(salida, dt.date):
        raise ErrorNegocio("Fechas no válidas.")
    hoy = hoy_hotel(cx, hotel_id)
    if entrada < hoy:
        raise ErrorNegocio("La fecha de entrada no puede ser anterior a hoy.")
    if entrada > hoy + dt.timedelta(days=MAX_ANTICIPACION_DIAS):
        raise ErrorNegocio("Solo se pueden reservar fechas dentro del próximo año.")
    noches = noches_entre(entrada, salida)
    if len(noches) > MAX_NOCHES:
        raise ErrorNegocio(f"Máximo {MAX_NOCHES} noches por reserva web.")
    if not (isinstance(adultos, int) and isinstance(ninos, int)) or not (1 <= adultos <= MAX_PERSONAS) or not (0 <= ninos <= MAX_PERSONAS):
        raise ErrorNegocio("Número de huéspedes no válido.")
    return hotel, noches


def _huesped_placeholder(cx, hotel_id: int) -> int:
    r = cx.execute("select id from pms_huespedes where hotel_id=%s and nombres=%s and apellidos=%s order by id limit 1",
                   (hotel_id, *PLACEHOLDER)).fetchone()
    if r:
        return r["id"]
    return cx.execute("insert into pms_huespedes (hotel_id, nombres, apellidos, pais) values (%s,%s,%s,'WEB') returning id",
                      (hotel_id, *PLACEHOLDER)).fetchone()["id"]


def _cargar(cx, numero: str, token: str, bloquear: bool = False) -> dict:
    """Reserva web por número + token. Mismo mensaje si no existe o el token no coincide (no revela cuál falló)."""
    malo = ErrorNegocio("No encontramos esa reserva o el enlace no es válido.")
    if not RE_NUMERO.match(numero or "") or not token:
        raise malo
    w = cx.execute("select * from pms_reservas_web where numero_publico=%s" + (" for update" if bloquear else ""), (numero,)).fetchone()
    if not w or not hmac.compare_digest(w["token_hash"], _h(str(token))):
        raise malo
    return w


def _en_hotel(numero: str, token: str) -> int:
    with db.tx() as cx:
        return _cargar(cx, numero, token)["hotel_id"]


def _vigente(w: dict, cx) -> bool:
    return cx.execute("select %s > now() v", (w["vence_en"],)).fetchone()["v"]


# ---------- consulta pública de disponibilidad ----------
def hoteles_publicos() -> list[dict]:
    return db.todos("select id, nombre, pais, moneda from pms_hoteles where activo order by nombre")


def buscar(hotel_id: int, entrada: dt.date, salida: dt.date, adultos: int = 2, ninos: int = 0) -> dict:
    """Tipos de habitación con precio y habitaciones del plano (solo número, planta, tipo, vista y si está libre; sin motivos internos)."""
    with db.tx() as cx:
        hotel, noches = _validar_busqueda(cx, hotel_id, entrada, salida, adultos, ninos)
        estado = disponibilidad.estado_habitaciones(cx, hotel_id, noches, adultos, ninos)
        tipos = []
        for t in cx.execute("select * from pms_tipos_habitacion where hotel_id=%s and activo order by capacidad desc, nombre",
                            (hotel_id,)).fetchall():
            libres = [h for h in estado if h["tipo_id"] == t["id"] and h["disponible"]]
            item = {"tipo_id": t["id"], "nombre": t["nombre"], "descripcion": t.get("descripcion") or "", "capacidad": t["capacidad"],
                    "libres": len(libres), "cotizacion": None, "motivo": None}
            if adultos + ninos > t["capacidad"]:
                item["motivo"] = f"Admite máximo {t['capacidad']} persona(s)."
            elif not libres:
                item["motivo"] = "Sin habitaciones libres en esas fechas."
            else:
                try:
                    item["cotizacion"] = tarifas.cotizar(cx, hotel_id, t["id"], noches, adultos + ninos)
                except ErrorNegocio as e:
                    item["motivo"] = str(e)
            tipos.append(item)
        cot = {t["tipo_id"]: t["cotizacion"] for t in tipos}
        camas = dibujo.camas_por_habitacion(cx, [h["id"] for h in estado])
        plano = [{"habitacion_id": h["id"], "numero": h["numero"], "planta": h["planta"], "tipo_id": h["tipo_id"], "tipo": h["tipo"],
                  "metros": h["metros"], "vista": h["vista"], "vista_mar": bool(h["vista_mar"]),
                  "capacidad": h["capacidad"], "camas": [{k: c[k] for k in ("tipo", "ancho_cm", "cantidad")} for c in camas.get(h["id"], [])], "libre": bool(h["disponible"] and cot.get(h["tipo_id"])),
                  "total": cot[h["tipo_id"]]["total"] if cot.get(h["tipo_id"]) else None}
                 for h in estado if h["estado"] != "fuera_de_servicio"]
        return {"hotel": {"id": hotel["id"], "nombre": hotel["nombre"], "moneda": hotel["moneda"]}, "noches": len(noches),
                "tipos": tipos, "plano": plano}


# ---------- bloqueo temporal ----------
def crear_bloqueo(hotel_id: int, tipo_id: int, entrada: dt.date, salida: dt.date, adultos: int, ninos: int = 0,
                  habitacion_id: int | None = None, ip: str = "") -> dict:
    """Aparta la habitación MINUTOS_BLOQUEO_WEB minutos. Devuelve el número, el token secreto del enlace y la hora de vencimiento."""
    ip_h = _hmac(ip) if ip else None
    try:
        with db.tx() as cx:
            _lock_hotel(cx, hotel_id)
            vencimientos.liberar_vencidas(cx, hotel_id)
            hotel, noches = _validar_busqueda(cx, hotel_id, entrada, salida, adultos, ninos)
            tipo = cx.execute("select * from pms_tipos_habitacion where id=%s and hotel_id=%s and activo", (tipo_id, hotel_id)).fetchone()
            if not tipo:
                raise ErrorNegocio("Tipo de habitación no válido.")
            _validar_ocupacion(tipo, adultos, ninos)
            if ip_h:
                n_h = cx.execute("select count(*) n from pms_reservas_web where ip_hash=%s and creado > now() - interval '1 hour'",
                                 (ip_h,)).fetchone()["n"]
                n_a = cx.execute("select count(*) n from pms_reservas_web where ip_hash=%s and estado in ('bloqueada','pago_pendiente','fallida')",
                                 (ip_h,)).fetchone()["n"]
                if n_h >= LIMITE_IP_POR_HORA or n_a >= LIMITE_ACTIVAS_POR_IP:
                    raise ErrorNegocio("Has hecho demasiados bloqueos seguidos. Termina o cancela el que tienes y vuelve a intentarlo en un rato.")
            precios = tarifas.precios_para(cx, tipo_id, noches)
            tarifas.validar_estancia_minima(cx, tipo_id, noches[0], len(noches))
            if habitacion_id is None:                         # la web siempre vende UNA habitación para toda la estancia (nunca «fuera de servicio»)
                est = disponibilidad.estado_habitaciones(cx, hotel_id, noches, adultos, ninos)
                habitacion_id = next((h["id"] for h in est if h["tipo_id"] == tipo_id and h["disponible"]), None)
                if habitacion_id is None:
                    raise ErrorNegocio("Ya no hay habitaciones libres de ese tipo en esas fechas.")
            else:
                h = cx.execute("select h.id, h.estado_limpieza from pms_habitaciones h where h.id=%s and h.hotel_id=%s and h.activo and h.tipo_id=%s",
                               (habitacion_id, hotel_id, tipo_id)).fetchone()
                if not h or h["estado_limpieza"] == "fuera_de_servicio":
                    raise ErrorNegocio("Esa habitación no está disponible.")
            rooms = disponibilidad.asignar(cx, hotel_id, tipo_id, noches, preferida=habitacion_id)
            numero = _nuevo_numero(cx, hotel_id)
            token = token_de(numero)
            seq = cx.execute("select count(*) n from pms_reservas where hotel_id=%s", (hotel_id,)).fetchone()["n"] + 1
            r = cx.execute(
                "insert into pms_reservas (hotel_id, codigo, huesped_id, tipo_id, fecha_entrada, fecha_salida, adultos, ninos, estado, "
                "canal, referencia_externa, notas, opcion_vence_en) values (%s,%s,%s,%s,%s,%s,%s,%s,'opcion',%s,%s,%s, "
                "now() + %s * interval '1 minute') returning *",
                (hotel_id, f"R{hotel_id}-{entrada:%y%m}-{seq:04d}", _huesped_placeholder(cx, hotel_id), tipo_id, entrada, salida,
                 adultos, ninos, CANAL, numero, "Reserva web (bloqueo temporal)", vencimientos.MINUTOS_BLOQUEO_WEB)).fetchone()
            _insertar_noches(cx, hotel_id, r["id"], tipo_id, rooms, precios)
            _recalcular(cx, r["id"])
            total = facturacion.resumen_cx(cx, r["id"])["total"]
            w = cx.execute("insert into pms_reservas_web (hotel_id, reserva_id, numero_publico, token_hash, estado, vence_en, monto_total, "
                           "moneda, ip_hash) values (%s,%s,%s,%s,'bloqueada',%s,%s,%s,%s) returning *",
                           (hotel_id, r["id"], numero, _h(token), r["opcion_vence_en"], total, hotel["moneda"], ip_h)).fetchone()
            registrar(cx, None, "bloqueo_web", "reserva", r["id"], despues={"numero": numero, "habitacion_id": habitacion_id,
                      "entrada": entrada, "salida": salida, "vence": r["opcion_vence_en"]}, hotel_id=hotel_id, email="web@publico")
            return {"numero": numero, "token": token, "vence_en": w["vence_en"], "total": total, "moneda": hotel["moneda"],
                    "reserva_id": r["id"], "habitacion_id": habitacion_id}
    except (pge.UniqueViolation, pge.ExclusionViolation) as e:
        raise (_traducir(e) or ErrorNegocio("No se pudo guardar el bloqueo: dato duplicado.")) from e


def _exigir_abierto(cx, w: dict):
    if w["estado"] not in ABIERTOS or not _vigente(w, cx):
        if w["estado"] == "confirmada":
            raise ErrorNegocio("Esta reserva ya está confirmada.")
        raise ErrorNegocio("Tu bloqueo venció o ya no está activo. Vuelve a elegir tu habitación.")


# ---------- datos del huésped + consentimiento (Ley 1581) ----------
def completar_datos(numero: str, token: str, nombres: str, apellidos: str, email: str, telefono: str = "",
                    tipo_documento: str = "", numero_documento: str = "", acepta_tratamiento: bool = False,
                    acepta_marketing: bool = False) -> dict:
    nombres, apellidos = _limpio(nombres, 60, "El nombre"), _limpio(apellidos, 60, "El apellido")
    email = _limpio(email, 120, "El correo").lower()
    if not correo.correo_valido(email):
        raise ErrorNegocio("El correo no es válido.")
    telefono = _limpio(telefono, 25, "El teléfono", obligatorio=False)
    if telefono and not re.match(r"^[0-9+()\- ]{6,25}$", telefono):
        raise ErrorNegocio("El teléfono no es válido.")
    tipo_documento = _limpio(tipo_documento, 10, "El tipo de documento", obligatorio=False)
    numero_documento = _limpio(numero_documento, 25, "El documento", obligatorio=False)
    if not acepta_tratamiento:
        raise ErrorNegocio("Debes autorizar el tratamiento de tus datos personales (Ley 1581 de 2012) para continuar.")
    hotel_id = _en_hotel(numero, token)
    with db.tx() as cx:
        _lock_hotel(cx, hotel_id)
        vencimientos.liberar_vencidas(cx, hotel_id)
        w = _cargar(cx, numero, token, bloquear=True)
        _exigir_abierto(cx, w)
        eh = _hmac(email)
        if cx.execute("select count(*) n from pms_reservas_web where email_hash=%s and estado in ('bloqueada','pago_pendiente','fallida') and id<>%s",
                      (eh, w["id"])).fetchone()["n"] >= LIMITE_ACTIVAS_POR_CORREO:
            raise ErrorNegocio("Ese correo ya tiene bloqueos activos. Termina o cancela uno antes de continuar.")
        r = cx.execute("select * from pms_reservas where id=%s for update", (w["reserva_id"],)).fetchone()
        g = cx.execute("select * from pms_huespedes where id=%s", (r["huesped_id"],)).fetchone()
        if (g["nombres"], g["apellidos"]) == PLACEHOLDER:
            gid = cx.execute("insert into pms_huespedes (hotel_id, nombres, apellidos, tipo_documento, numero_documento, email, telefono) "
                             "values (%s,%s,%s,%s,%s,%s,%s) returning id",
                             (hotel_id, nombres, apellidos, tipo_documento or None, numero_documento or None, email, telefono or None)).fetchone()["id"]
            cx.execute("update pms_reservas set huesped_id=%s where id=%s", (gid, r["id"]))
        else:
            gid = g["id"]
            cx.execute("update pms_huespedes set nombres=%s, apellidos=%s, tipo_documento=%s, numero_documento=%s, email=%s, telefono=%s "
                       "where id=%s", (nombres, apellidos, tipo_documento or None, numero_documento or None, email, telefono or None, gid))
        finalidades = ["prestacion_servicio", "facturacion"] + (["marketing"] if acepta_marketing else [])
        for f in finalidades:
            if not huespedes.consentimiento_vigente(cx, gid, f):
                cx.execute("insert into pms_consentimientos (hotel_id, huesped_id, finalidad, aceptado, texto, version) values (%s,%s,%s,true,%s,%s)",
                           (hotel_id, gid, f, huespedes.FINALIDADES[f][1] + " [aceptado en la reserva web]", huespedes.VERSION_TEXTO))
        cx.execute("update pms_reservas_web set email_hash=%s, consentimiento_version=%s, actualizado=now() where id=%s",
                   (eh, huespedes.VERSION_TEXTO, w["id"]))
        registrar(cx, None, "datos_web", "huesped", gid, despues={"consentimientos": finalidades, "version": huespedes.VERSION_TEXTO},
                  hotel_id=hotel_id, email="web@publico")
    return {"ok": True}


# ---------- pago ----------
def iniciar_pago(numero: str, token: str, proveedor: str | None = None) -> dict:
    """Crea (o reutiliza) el intento de pago pendiente y devuelve la referencia que usa la pasarela. No cobra nada por sí mismo."""
    hotel_id = _en_hotel(numero, token)
    pas = pasarela.obtener(proveedor)
    with db.tx() as cx:
        _lock_hotel(cx, hotel_id)
        vencimientos.liberar_vencidas(cx, hotel_id)
        w = _cargar(cx, numero, token, bloquear=True)
        _exigir_abierto(cx, w)
        r = cx.execute("select * from pms_reservas where id=%s for update", (w["reserva_id"],)).fetchone()
        g = cx.execute("select * from pms_huespedes where id=%s", (r["huesped_id"],)).fetchone()
        if (g["nombres"], g["apellidos"]) == PLACEHOLDER or not huespedes.consentimiento_vigente(cx, g["id"], "prestacion_servicio"):
            raise ErrorNegocio("Faltan tus datos y la autorización de tratamiento de datos antes de pagar.")
        cx.execute("update pms_reservas set opcion_vence_en = greatest(opcion_vence_en, now() + %s * interval '1 minute') where id=%s",
                   (GRACIA_PAGO_MIN, r["id"]))
        i = cx.execute("select * from pms_pagos_pasarela where reserva_web_id=%s and estado='pendiente' and proveedor=%s order by id desc limit 1",
                       (w["id"], pas.nombre)).fetchone()
        if not i:
            i = cx.execute("insert into pms_pagos_pasarela (hotel_id, reserva_web_id, proveedor, referencia, monto, moneda) "
                           "values (%s,%s,%s,%s,%s,%s) returning *",
                           (hotel_id, w["id"], pas.nombre, pas.nueva_referencia(), w["monto_total"], w["moneda"])).fetchone()
        nuevo = cx.execute("update pms_reservas_web set estado='pago_pendiente', actualizado=now(), "
                           "vence_en=(select opcion_vence_en from pms_reservas where id=%s) where id=%s returning vence_en",
                           (r["id"], w["id"])).fetchone()
        registrar(cx, None, "iniciar_pago_web", "reserva", r["id"], despues={"referencia": i["referencia"], "proveedor": pas.nombre},
                  hotel_id=hotel_id, email="web@publico")
        return {"referencia": i["referencia"], "monto": i["monto"], "moneda": i["moneda"], "proveedor": pas.nombre,
                "vence_en": nuevo["vence_en"], "leyenda": getattr(pas, "leyenda", "")}


def procesar_evento(evento: dict, firma: str, proveedor: str = "simulada") -> dict:
    """Receptor del «webhook» de la pasarela. Idempotente: el mismo evento dos veces se procesa una sola vez.
    Comprueba firma, referencia, monto y moneda. Resultados: confirmada · rechazada · duplicado · firma_invalida ·
    referencia_desconocida · monto_invalido · ya_procesado · pago_tardio_reubicado · pago_tardio_sin_reserva."""
    pas = pasarela.obtener(proveedor)
    valida = pas.verificar_evento(evento, firma)
    if not valida:
        with db.tx() as cx:
            cx.execute("insert into pms_eventos_pasarela (proveedor, evento_id, referencia, tipo, firma_valida, resultado) values (%s,%s,%s,%s,false,'firma_invalida')",
                       (proveedor, "invalido-" + secrets.token_hex(6), str(evento.get("referencia"))[:60], str(evento.get("tipo"))[:30]))
        return {"resultado": "firma_invalida"}
    ev = pas.normalizar(evento)
    if ev.get("tipo") not in pasarela.TIPOS or not ev.get("referencia") or not ev.get("id"):
        return {"resultado": "evento_invalido"}
    with db.tx() as cx:
        nuevo = cx.execute("insert into pms_eventos_pasarela (proveedor, evento_id, referencia, tipo, firma_valida, payload) "
                           "values (%s,%s,%s,%s,true,%s) on conflict (proveedor, evento_id) do nothing returning id",
                           (proveedor, str(ev["id"])[:80], str(ev["referencia"])[:60], ev["tipo"], db.Jsonb(ev))).fetchone()
        if not nuevo:
            return {"resultado": "duplicado"}
        i0 = cx.execute("select hotel_id from pms_pagos_pasarela where proveedor=%s and referencia=%s", (proveedor, ev["referencia"])).fetchone()
        if not i0:
            cx.execute("update pms_eventos_pasarela set resultado='referencia_desconocida' where id=%s", (nuevo["id"],))
            return {"resultado": "referencia_desconocida"}
        hotel_id = i0["hotel_id"]
        _lock_hotel(cx, hotel_id)
        vencimientos.liberar_vencidas(cx, hotel_id)
        i = cx.execute("select * from pms_pagos_pasarela where proveedor=%s and referencia=%s for update", (proveedor, ev["referencia"])).fetchone()
        w = cx.execute("select * from pms_reservas_web where id=%s for update", (i["reserva_web_id"],)).fetchone()
        r = cx.execute("select * from pms_reservas where id=%s for update", (w["reserva_id"],)).fetchone()
        res = _aplicar_evento(cx, ev, i, w, r)
        cx.execute("update pms_eventos_pasarela set resultado=%s where id=%s", (res["resultado"], nuevo["id"]))
        registrar(cx, None, "evento_pasarela", "reserva", r["id"], despues={"resultado": res["resultado"], "referencia": ev["referencia"],
                  "tipo": ev["tipo"]}, hotel_id=hotel_id, email=f"pasarela:{proveedor}")
    if res["resultado"] in ("confirmada", "pago_tardio_reubicado"):
        _enviar_confirmacion(res["web_id"])
    return {k: v for k, v in res.items() if k != "web_id"}


def _aplicar_evento(cx, ev: dict, i: dict, w: dict, r: dict) -> dict:
    base = {"numero": w["numero_publico"], "web_id": w["id"]}
    if i["estado"] in ("aprobada", "rechazada", "requiere_revision"):
        return {**base, "resultado": "ya_procesado"}
    if ev["tipo"] == "pago.rechazado":
        cx.execute("update pms_pagos_pasarela set estado='rechazada', detalle='Pago rechazado por la pasarela', actualizado=now() where id=%s", (i["id"],))
        if w["estado"] in ("bloqueada", "pago_pendiente"):
            cx.execute("update pms_reservas_web set estado='fallida', actualizado=now() where id=%s", (w["id"],))
        return {**base, "resultado": "rechazada"}
    if Decimal(str(ev["monto"])) != i["monto"] or str(ev["moneda"]).upper() != i["moneda"]:
        cx.execute("update pms_pagos_pasarela set estado='requiere_revision', detalle=%s, actualizado=now() where id=%s",
                   (f"El evento trae {ev['monto']} {ev['moneda']} y el cobro era {i['monto']} {i['moneda']}", i["id"]))
        return {**base, "resultado": "monto_invalido"}
    if w["estado"] in ABIERTOS and r["estado"] == "opcion":
        return {**base, **_confirmar(cx, i, w, r, "confirmada")}
    if w["estado"] == "expirada":                                  # el dinero llegó cuando el bloqueo ya había vencido
        ult = {}
        for x in cx.execute("select * from pms_reserva_noches where reserva_id=%s and not activa order by noche, id", (r["id"],)).fetchall():
            ult[x["noche"]] = x                                    # la última fila de cada noche (la del bloqueo)
        noches = sorted(ult)
        libres = disponibilidad.libres_por_noche(cx, w["hotel_id"], r["tipo_id"], noches) if noches else {}
        if noches and all(any(h["id"] == ult[n]["habitacion_id"] for h in libres[n]) for n in noches):
            cx.execute("update pms_reserva_noches set activa=true where id = any(%s)", ([ult[n]["id"] for n in noches],))
            cx.execute("update pms_cargos set anulado=false, anulado_por=null where reserva_id=%s and anulado and tipo='noche'", (r["id"],))
            cx.execute("update pms_reservas set estado='opcion', cancelacion_motivo=null where id=%s", (r["id"],))
            return {**base, **_confirmar(cx, i, w, {**r, "estado": "opcion"}, "pago_tardio_reubicado")}
        cx.execute("update pms_pagos_pasarela set estado='requiere_revision', detalle=%s, actualizado=now() where id=%s",
                   ("Pago aprobado DESPUÉS de vencer el bloqueo y la habitación ya no está libre: reembolsar o reubicar al cliente", i["id"]))
        return {**base, "resultado": "pago_tardio_sin_reserva"}
    cx.execute("update pms_pagos_pasarela set estado='requiere_revision', detalle=%s, actualizado=now() where id=%s",
               (f"Pago aprobado para una reserva web en estado «{w['estado']}»: revisar y reembolsar si corresponde", i["id"]))
    return {**base, "resultado": "pago_tardio_sin_reserva"}


def _confirmar(cx, i: dict, w: dict, r: dict, resultado: str) -> dict:
    """pendiente → pagada → confirmada, en una sola transacción: registra el pago en la reserva y quita el vencimiento."""
    pago = cx.execute("insert into pms_pagos (hotel_id, reserva_id, metodo, monto, referencia) values (%s,%s,'pasarela',%s,%s) returning id",
                      (w["hotel_id"], r["id"], i["monto"], f"{i['proveedor']}:{i['referencia']}")).fetchone()
    cx.execute("update pms_pagos_pasarela set estado='aprobada', pago_id=%s, actualizado=now() where id=%s", (pago["id"], i["id"]))
    registrar(cx, None, "pago_web_recibido", "reserva", r["id"], antes={"web": w["estado"]}, despues={"web": "pagada", "monto": i["monto"]},
              hotel_id=w["hotel_id"], email="web@publico")
    cx.execute("update pms_reservas set estado='confirmada', opcion_vence_en=null where id=%s", (r["id"],))
    cx.execute("update pms_reservas_web set estado='confirmada', confirmada_en=now(), actualizado=now() where id=%s", (w["id"],))
    registrar(cx, None, "confirmar_web", "reserva", r["id"], antes={"web": "pagada"}, despues={"web": "confirmada"},
              hotel_id=w["hotel_id"], email="web@publico")
    return {"resultado": resultado}


# ---------- correo de confirmación ----------
def _enviar_confirmacion(web_id: int) -> dict | None:
    """Arma, registra (una sola vez) y envía —o simula— el correo de confirmación. Nunca deshace la reserva si falla."""
    import os
    with db.tx() as cx:
        w = cx.execute("select * from pms_reservas_web where id=%s", (web_id,)).fetchone()
        if not w or w["estado"] != "confirmada":
            return None
        if cx.execute("select 1 from pms_correos where reserva_id=%s and estado in ('simulado','enviado')", (w["reserva_id"],)).fetchone():
            return None                                           # idempotente: un solo correo por reserva
        d = cx.execute("select r.fecha_entrada, r.fecha_salida, r.adultos, r.ninos, h.nombre hotel, g.nombres, g.email from pms_reservas r "
                       "join pms_hoteles h on h.id=r.hotel_id join pms_huespedes g on g.id=r.huesped_id where r.id=%s", (w["reserva_id"],)).fetchone()
        hab = cx.execute("select hb.numero, t.nombre tipo from pms_reserva_noches n join pms_habitaciones hb on hb.id=n.habitacion_id "
                         "join pms_tipos_habitacion t on t.id=n.tipo_id where n.reserva_id=%s and n.activa order by n.noche limit 1",
                         (w["reserva_id"],)).fetchone()
    if not d["email"]:
        return None
    base = os.environ.get("PMS_WEB_URL", "https://pms-reservas-atm.streamlit.app").rstrip("/")
    asunto, cuerpo, texto = correo.construir({
        "hotel": d["hotel"], "nombre": d["nombres"], "numero": w["numero_publico"], "entrada": f"{d['fecha_entrada']:%d/%m/%Y}",
        "salida": f"{d['fecha_salida']:%d/%m/%Y}", "habitacion": f"{hab['numero']} · {hab['tipo']}" if hab else "",
        "personas": f"{d['adultos']} adulto(s)" + (f", {d['ninos']} niño(s)" if d["ninos"] else ""),
        "total": fmt_moneda(w["monto_total"], w["moneda"]), "enlace": f"{base}/?r={w['numero_publico']}&k={token_de(w['numero_publico'])}",
        "pruebas": True})
    out = correo.enviar(d["email"], asunto, cuerpo, texto)
    with db.tx() as cx:
        return cx.execute("insert into pms_correos (hotel_id, reserva_id, destinatario, asunto, cuerpo_html, proveedor, estado, detalle) "
                          "values (%s,%s,%s,%s,%s,%s,%s,%s) returning *",
                          (w["hotel_id"], w["reserva_id"], d["email"], asunto, cuerpo, out["proveedor"], out["estado"], out["detalle"])).fetchone()


def correo_enviado(numero: str, token: str) -> dict | None:
    """El último correo de confirmación de ESTA reserva (para mostrarlo en pantalla cuando es simulado)."""
    with db.tx() as cx:
        w = _cargar(cx, numero, token)
        return cx.execute("select asunto, cuerpo_html, proveedor, estado, detalle, creado from pms_correos where reserva_id=%s order by id desc limit 1",
                          (w["reserva_id"],)).fetchone()


# ---------- consulta y cancelación por el cliente ----------
def consultar(numero: str, token: str) -> dict:
    """Vista pública de UNA reserva (la del enlace). Solo datos de esa reserva; el correo va enmascarado."""
    hotel_id = _en_hotel(numero, token)
    with db.tx() as cx:
        vencimientos.liberar_vencidas(cx, hotel_id)
        w = _cargar(cx, numero, token)
        d = cx.execute("select r.fecha_entrada, r.fecha_salida, r.adultos, r.ninos, r.estado res_estado, h.nombre hotel, g.nombres, g.apellidos, "
                       "g.email, t.nombre tipo, extract(epoch from (%s - now())) seg from pms_reservas r join pms_hoteles h on h.id=r.hotel_id "
                       "join pms_huespedes g on g.id=r.huesped_id join pms_tipos_habitacion t on t.id=r.tipo_id where r.id=%s",
                       (w["vence_en"], w["reserva_id"])).fetchone()
        hab = cx.execute("select hb.numero from pms_reserva_noches n join pms_habitaciones hb on hb.id=n.habitacion_id where n.reserva_id=%s "
                         "order by n.activa desc, n.noche, n.id limit 1", (w["reserva_id"],)).fetchone()
        pagado = cx.execute("select coalesce(sum(monto),0) m from pms_pagos where reserva_id=%s and not anulado", (w["reserva_id"],)).fetchone()["m"]
        ultimo = cx.execute("select estado, detalle from pms_pagos_pasarela where reserva_web_id=%s order by id desc limit 1", (w["id"],)).fetchone()
        placeholder = (d["nombres"], d["apellidos"]) == PLACEHOLDER
        return {"numero": numero, "estado": w["estado"], "estado_texto": ESTADO_TEXTO[w["estado"]], "hotel": d["hotel"],
                "hotel_id": w["hotel_id"], "entrada": d["fecha_entrada"], "salida": d["fecha_salida"], "adultos": d["adultos"],
                "ninos": d["ninos"], "tipo": d["tipo"], "habitacion": hab["numero"] if hab else None, "total": w["monto_total"],
                "moneda": w["moneda"], "pagado": pagado, "vence_en": w["vence_en"],
                "segundos": max(0, int(d["seg"])) if w["estado"] in ABIERTOS else 0,
                "con_datos": not placeholder, "huesped": None if placeholder else f"{d['nombres']} {d['apellidos']}",
                "correo": None if placeholder else correo.enmascarar(d["email"] or ""), "ultimo_pago": ultimo["estado"] if ultimo else None}


def cancelar_bloqueo(numero: str, token: str):
    """El cliente suelta su bloqueo antes de pagar (libera la habitación al instante)."""
    hotel_id = _en_hotel(numero, token)
    with db.tx() as cx:
        _lock_hotel(cx, hotel_id)
        w = _cargar(cx, numero, token, bloquear=True)
        if w["estado"] not in ABIERTOS:
            raise ErrorNegocio("Esta reserva ya no tiene un bloqueo activo.")
        cx.execute("update pms_reserva_noches set activa=false where reserva_id=%s and activa", (w["reserva_id"],))
        cx.execute("update pms_cargos set anulado=true, motivo=coalesce(motivo,'') || ' · Cancelado por el cliente (web)' "
                   "where reserva_id=%s and not anulado and tipo in ('noche','extra')", (w["reserva_id"],))
        cx.execute("update pms_reservas set estado='cancelada', cancelacion_motivo='Cancelada por el cliente en la web', opcion_vence_en=null where id=%s",
                   (w["reserva_id"],))
        cx.execute("update pms_pagos_pasarela set estado='vencida', detalle='Cancelado por el cliente', actualizado=now() where reserva_web_id=%s and estado='pendiente'", (w["id"],))
        cx.execute("update pms_reservas_web set estado='cancelada', actualizado=now() where id=%s", (w["id"],))
        registrar(cx, None, "cancelar_bloqueo_web", "reserva", w["reserva_id"], hotel_id=hotel_id, email="web@publico")


# ---------- lo que ve el PMS interno (recepción/gerencia) ----------
def listar_web(actor, hotel_id: int, limite: int = 200) -> list[dict]:
    from . import seguridad
    seguridad.exigir(actor, "reservas", editar=False)
    seguridad.exigir_hotel(actor, hotel_id)
    return db.todos(
        "select w.id, w.numero_publico, w.estado, w.vence_en, w.monto_total, w.moneda, w.creado, w.confirmada_en, r.id reserva_id, r.codigo, "
        "r.estado reserva_estado, r.fecha_entrada, r.fecha_salida, g.nombres || ' ' || g.apellidos huesped, t.nombre tipo, "
        "(select hb.numero from pms_reserva_noches n join pms_habitaciones hb on hb.id=n.habitacion_id where n.reserva_id=r.id "
        " order by n.activa desc, n.noche, n.id limit 1) habitacion, "
        "(select coalesce(sum(p.monto),0) from pms_pagos p where p.reserva_id=r.id and not p.anulado) pagado, "
        "(select pp.estado from pms_pagos_pasarela pp where pp.reserva_web_id=w.id order by pp.id desc limit 1) pago_estado, "
        "(select pp.referencia from pms_pagos_pasarela pp where pp.reserva_web_id=w.id order by pp.id desc limit 1) pago_referencia, "
        "(select pp.detalle from pms_pagos_pasarela pp where pp.reserva_web_id=w.id order by pp.id desc limit 1) pago_detalle, "
        "(select c.estado from pms_correos c where c.reserva_id=r.id order by c.id desc limit 1) correo_estado "
        "from pms_reservas_web w join pms_reservas r on r.id=w.reserva_id join pms_huespedes g on g.id=r.huesped_id "
        "join pms_tipos_habitacion t on t.id=r.tipo_id where w.hotel_id=%s order by w.creado desc limit %s", (hotel_id, limite))


def liberar_vencidas_ahora(actor, hotel_id: int) -> int:
    from . import seguridad
    seguridad.exigir(actor, "reservas")
    seguridad.exigir_hotel(actor, hotel_id)
    with db.tx() as cx:
        return len(vencimientos.liberar_vencidas(cx, hotel_id))

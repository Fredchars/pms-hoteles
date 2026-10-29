"""Reservas: crear, modificar, cancelar (con aprobación de gerencia), no-show, check-in y check-out.
Reglas clave: precio congelado por noche, una fila por noche con habitación asignada (restricción única en la base),
consentimiento Ley 1581 obligatorio, y todo queda en la auditoría."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import psycopg.errors as pge

from . import config, db, disponibilidad, facturacion, huespedes, seguridad, tarifas, vencimientos
from .auditoria import registrar
from .errores import ErrorNegocio
from .util import dinero, hotel_de, hoy_hotel, noches_entre

ESTADOS = ["consulta", "opcion", "confirmada", "alojado", "salida", "cancelada", "no_show"]
ESTADOS_NOMBRE = {"consulta": "Consulta", "opcion": "Opción", "confirmada": "Confirmada", "alojado": "Alojado",
                  "salida": "Salida", "cancelada": "Cancelada", "no_show": "No se presentó"}
ESTADOS_NUEVOS = ("consulta", "opcion", "confirmada")
ESTADOS_EDITABLES = ("consulta", "opcion", "confirmada")
CANALES = ["directo", "telefono", "whatsapp", "booking", "airbnb", "agencia", "otro"]


def _lock_hotel(cx, hotel_id: int):
    """Serializa las ventas de un mismo hotel: dos recepcionistas no pueden vender la misma noche a la vez."""
    cx.execute("select pg_advisory_xact_lock(%s)", (7_000_000 + hotel_id,))


def _reserva(cx, reserva_id: int, actor: dict, bloquear=True) -> dict:
    r = cx.execute("select * from pms_reservas where id=%s" + (" for update" if bloquear else ""), (reserva_id,)).fetchone()
    if not r:
        raise ErrorNegocio("Reserva no encontrada.")
    seguridad.exigir_hotel(actor, r["hotel_id"])
    return r


def _traducir(e: Exception):
    n = getattr(getattr(e, "diag", None), "constraint_name", "") or ""
    if "ux_pms_noche_habitacion" in n:
        return ErrorNegocio("Esa habitación ya está vendida para una de esas noches (otra reserva se adelantó). Intenta de nuevo.")
    if "ux_pms_reservas_ref_externa" in n:
        return ErrorNegocio("Ya existe una reserva con esa referencia externa en ese canal.")
    return None


def _recalcular(cx, reserva_id: int):
    r = cx.execute("select comision_pct from pms_reservas where id=%s", (reserva_id,)).fetchone()
    total = cx.execute("select coalesce(sum(precio),0) t from pms_reserva_noches where reserva_id=%s and activa",
                       (reserva_id,)).fetchone()["t"]
    com = dinero(Decimal(total) * r["comision_pct"] / 100)
    cx.execute("update pms_reservas set comision_monto=%s, neto=%s where id=%s", (com, dinero(total) - com, reserva_id))


def _validar_ocupacion(tipo: dict, adultos: int, ninos: int):
    if adultos < 1 or ninos < 0:
        raise ErrorNegocio("Debe haber al menos 1 adulto.")
    if not disponibilidad.cabe(tipo["capacidad"], adultos, ninos):
        raise ErrorNegocio(f"El tipo «{tipo['nombre']}» admite máximo {tipo['capacidad']} personas.")


def _insertar_noches(cx, hotel_id, reserva_id, tipo_id, rooms: dict, precios: dict):
    imp = db.Jsonb(config.impuestos_congelados(cx, hotel_id))
    tipo = cx.execute("select nombre from pms_tipos_habitacion where id=%s", (tipo_id,)).fetchone()["nombre"]
    for n in sorted(rooms):
        cx.execute("insert into pms_reserva_noches (hotel_id, reserva_id, noche, tipo_id, habitacion_id, precio) "
                   "values (%s,%s,%s,%s,%s,%s)", (hotel_id, reserva_id, n, tipo_id, rooms[n], precios[n]))
        cx.execute("insert into pms_cargos (hotel_id, reserva_id, tipo, descripcion, cantidad, precio_unitario, monto, "
                   "impuestos, noche) values (%s,%s,'noche',%s,1,%s,%s,%s,%s)",
                   (hotel_id, reserva_id, f"Noche {tipo} · {n:%d/%m/%Y}", precios[n], precios[n], imp, n))


def crear(actor, hotel_id: int, huesped_id: int, tipo_id: int, entrada: dt.date, salida: dt.date, adultos: int = 1,
          ninos: int = 0, estado: str = "confirmada", canal: str = "directo", comision_pct=0,
          referencia_externa: str | None = None, notas: str = "", habitacion_id: int | None = None,
          hoy: dt.date | None = None, permitir_pasado: bool = False) -> dict:
    seguridad.exigir(actor, "reservas")
    seguridad.exigir_hotel(actor, hotel_id)
    if estado not in ESTADOS_NUEVOS:
        raise ErrorNegocio("Una reserva nueva solo puede iniciar como consulta, opción o confirmada.")
    comision = Decimal(str(comision_pct or 0))
    if comision < 0 or comision > 100:
        raise ErrorNegocio("La comisión debe estar entre 0 y 100 %.")
    noches = noches_entre(entrada, salida)
    try:
        with db.tx() as cx:
            _lock_hotel(cx, hotel_id)
            hotel_de(cx, hotel_id)
            hoy = hoy or hoy_hotel(cx, hotel_id)
            if entrada < hoy and not permitir_pasado:
                raise ErrorNegocio("La fecha de entrada no puede ser anterior a hoy.")
            h = cx.execute("select * from pms_huespedes where id=%s", (huesped_id,)).fetchone()
            if not h or h["hotel_id"] != hotel_id:
                raise ErrorNegocio("El huésped no existe en este hotel.")
            if h["anonimizado"]:
                raise ErrorNegocio("Este huésped fue anonimizado: crea una ficha nueva.")
            if not huespedes.consentimiento_vigente(cx, huesped_id, "prestacion_servicio"):
                raise ErrorNegocio("Falta el consentimiento de tratamiento de datos (Ley 1581): regístralo en la ficha del huésped.")
            tipo = cx.execute("select * from pms_tipos_habitacion where id=%s and hotel_id=%s and activo", (tipo_id, hotel_id)).fetchone()
            if not tipo:
                raise ErrorNegocio("Tipo de habitación no válido para este hotel.")
            _validar_ocupacion(tipo, adultos, ninos)
            precios = tarifas.precios_para(cx, tipo_id, noches)
            tarifas.validar_estancia_minima(cx, tipo_id, entrada, len(noches))
            if habitacion_id is not None:
                hab = cx.execute("select * from pms_habitaciones where id=%s and hotel_id=%s and activo and tipo_id=%s",
                                 (habitacion_id, hotel_id, tipo_id)).fetchone()
                if not hab:
                    raise ErrorNegocio("La habitación elegida no es de ese tipo en este hotel.")
            rooms = disponibilidad.asignar(cx, hotel_id, tipo_id, noches, preferida=habitacion_id)
            seq = cx.execute("select count(*) n from pms_reservas where hotel_id=%s", (hotel_id,)).fetchone()["n"] + 1
            codigo = f"R{hotel_id}-{entrada:%y%m}-{seq:04d}"
            r = cx.execute(
                "insert into pms_reservas (hotel_id, codigo, huesped_id, tipo_id, fecha_entrada, fecha_salida, adultos, ninos, "
                "estado, canal, comision_pct, referencia_externa, notas, creado_por, opcion_vence_en) values "
                "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, case when %s::text = 'opcion' then now() + %s::float8 * interval '1 hour' end) returning *",
                (hotel_id, codigo, huesped_id, tipo_id, entrada, salida, adultos, ninos, estado, canal, comision,
                 referencia_externa or None, notas or None, actor["id"], estado, vencimientos.HORAS_OPCION_PMS)).fetchone()
            _insertar_noches(cx, hotel_id, r["id"], tipo_id, rooms, precios)
            _recalcular(cx, r["id"])
            registrar(cx, actor, "crear", "reserva", r["id"], despues={
                "codigo": codigo, "entrada": entrada, "salida": salida, "tipo": tipo["nombre"], "estado": estado,
                "total_noches": sum(precios.values())}, hotel_id=hotel_id)
            return cx.execute("select * from pms_reservas where id=%s", (r["id"],)).fetchone()
    except (pge.UniqueViolation, pge.ExclusionViolation) as e:
        raise (_traducir(e) or ErrorNegocio("No se pudo guardar la reserva: dato duplicado.")) from e


def modificar(actor, reserva_id: int, entrada: dt.date | None = None, salida: dt.date | None = None,
              adultos: int | None = None, ninos: int | None = None, canal: str | None = None, comision_pct=None,
              referencia_externa: str | None = None, notas: str | None = None, estado: str | None = None,
              hoy: dt.date | None = None) -> dict:
    """Cambia fechas y datos. Las noches que se conservan mantienen su precio congelado; solo las noches nuevas
    se cotizan con la tarifa vigente."""
    seguridad.exigir(actor, "reservas")
    try:
        with db.tx() as cx:
            r0 = cx.execute("select hotel_id from pms_reservas where id=%s", (reserva_id,)).fetchone()
            if not r0:
                raise ErrorNegocio("Reserva no encontrada.")
            _lock_hotel(cx, r0["hotel_id"])
            vencimientos.liberar_vencidas(cx, r0["hotel_id"])      # una opción ya vencida no se puede seguir editando
            r = _reserva(cx, reserva_id, actor)
            hoy = hoy or hoy_hotel(cx, r["hotel_id"])
            if r["cancelacion_estado"] == "solicitada":
                raise ErrorNegocio("Hay una cancelación pendiente de aprobación: no se puede modificar la reserva.")
            if r["estado"] not in ESTADOS_EDITABLES + ("alojado",):
                raise ErrorNegocio(f"Una reserva en estado «{ESTADOS_NOMBRE[r['estado']]}» no se puede modificar.")
            alojado = r["estado"] == "alojado"
            nueva_e = entrada or r["fecha_entrada"]
            nueva_s = salida or r["fecha_salida"]
            if alojado and nueva_e != r["fecha_entrada"]:
                raise ErrorNegocio("Con el huésped alojado solo se puede cambiar la fecha de salida.")
            if alojado and nueva_s <= hoy:
                raise ErrorNegocio("Para salir hoy o antes usa el check-out.")
            if nueva_e < hoy and nueva_e != r["fecha_entrada"]:
                raise ErrorNegocio("La nueva fecha de entrada no puede ser anterior a hoy.")
            nuevas = set(noches_entre(nueva_e, nueva_s))
            actuales = {x["noche"]: x for x in cx.execute(
                "select * from pms_reserva_noches where reserva_id=%s and activa order by noche", (reserva_id,)).fetchall()}
            quitar = sorted(set(actuales) - nuevas)
            poner = sorted(nuevas - set(actuales))
            if alojado and any(n <= hoy for n in quitar):
                raise ErrorNegocio("No se pueden quitar noches que ya se usaron.")
            tipo = cx.execute("select * from pms_tipos_habitacion where id=%s", (r["tipo_id"],)).fetchone()
            ad = r["adultos"] if adultos is None else adultos
            ni = r["ninos"] if ninos is None else ninos
            _validar_ocupacion(tipo, ad, ni)
            if estado and estado != r["estado"]:
                if estado not in ESTADOS_NUEVOS or alojado:
                    raise ErrorNegocio("Solo se puede pasar entre consulta, opción y confirmada.")
            com = r["comision_pct"] if comision_pct is None else Decimal(str(comision_pct))
            if com < 0 or com > 100:
                raise ErrorNegocio("La comisión debe estar entre 0 y 100 %.")
            if poner or nueva_e != r["fecha_entrada"]:
                tarifas.validar_estancia_minima(cx, r["tipo_id"], nueva_e, len(nuevas))
            precios = tarifas.precios_para(cx, r["tipo_id"], poner) if poner else {}
            # habitación de las noches nuevas: la de la noche vecina si está libre
            rooms = {}
            if poner:
                libres = disponibilidad.libres_por_noche(cx, r["hotel_id"], r["tipo_id"], poner, excluir_reserva=reserva_id)
                previa = {n: x["habitacion_id"] for n, x in actuales.items() if n not in quitar}
                for n in poner:
                    cand = [h["id"] for h in libres[n]]
                    if not cand:
                        raise ErrorNegocio(f"No hay disponibilidad de este tipo la noche del {n:%d/%m/%Y}.")
                    vecina = previa.get(n - dt.timedelta(days=1)) or previa.get(n + dt.timedelta(days=1)) or rooms.get(n - dt.timedelta(days=1))
                    rooms[n] = vecina if vecina in cand else cand[0]
            antes = {"entrada": r["fecha_entrada"], "salida": r["fecha_salida"], "adultos": r["adultos"], "ninos": r["ninos"],
                     "canal": r["canal"], "notas": r["notas"], "estado": r["estado"]}
            nuevo_estado = estado or r["estado"]
            vence = r["opcion_vence_en"]                       # confirmar/pasar a consulta quita el vencimiento; volver a opción lo reinicia
            if nuevo_estado != "opcion":
                vence = None
            elif r["estado"] != "opcion":
                vence = cx.execute("select now() + %s::float8 * interval '1 hour' v", (vencimientos.HORAS_OPCION_PMS,)).fetchone()["v"]
            for n in quitar:
                cx.execute("update pms_reserva_noches set activa=false where id=%s", (actuales[n]["id"],))
                cx.execute("update pms_cargos set anulado=true, anulado_por=%s, motivo='Noche liberada por cambio de fechas' "
                           "where reserva_id=%s and tipo='noche' and noche=%s and not anulado", (actor["id"], reserva_id, n))
            if poner:
                _insertar_noches(cx, r["hotel_id"], reserva_id, r["tipo_id"], rooms, precios)
            cx.execute("update pms_reservas set fecha_entrada=%s, fecha_salida=%s, adultos=%s, ninos=%s, canal=%s, comision_pct=%s, "
                       "referencia_externa=%s, notas=%s, estado=%s, opcion_vence_en=%s where id=%s",
                       (nueva_e, nueva_s, ad, ni, canal or r["canal"], com,
                        (referencia_externa if referencia_externa is not None else r["referencia_externa"]) or None,
                        notas if notas is not None else r["notas"], estado or r["estado"], vence, reserva_id))
            _recalcular(cx, reserva_id)
            registrar(cx, actor, "modificar", "reserva", reserva_id, antes=antes, despues={
                "entrada": nueva_e, "salida": nueva_s, "adultos": ad, "ninos": ni, "canal": canal or r["canal"],
                "estado": estado or r["estado"], "noches_nuevas": len(poner), "noches_liberadas": len(quitar)},
                hotel_id=r["hotel_id"])
            return cx.execute("select * from pms_reservas where id=%s", (reserva_id,)).fetchone()
    except (pge.UniqueViolation, pge.ExclusionViolation) as e:
        raise (_traducir(e) or ErrorNegocio("No se pudo guardar el cambio: dato duplicado.")) from e


def reasignar_habitacion(actor, reserva_id: int, habitacion_id: int, hoy: dt.date | None = None) -> None:
    """Cambia la habitación de las noches pendientes (hasta el check-in, o desde hoy si ya está alojado)."""
    seguridad.exigir(actor, "reservas")
    try:
        with db.tx() as cx:
            r0 = cx.execute("select hotel_id from pms_reservas where id=%s", (reserva_id,)).fetchone()
            if not r0:
                raise ErrorNegocio("Reserva no encontrada.")
            _lock_hotel(cx, r0["hotel_id"])
            r = _reserva(cx, reserva_id, actor)
            _reasignar(cx, actor, r, habitacion_id, hoy or hoy_hotel(cx, r["hotel_id"]))
    except pge.UniqueViolation as e:
        raise (_traducir(e) or ErrorNegocio("La habitación ya está vendida en esas noches.")) from e


def _reasignar(cx, actor, r, habitacion_id, hoy):
    if r["estado"] not in ESTADOS_EDITABLES + ("alojado",):
        raise ErrorNegocio("En este estado no se puede cambiar la habitación.")
    if r["cancelacion_estado"] == "solicitada":
        raise ErrorNegocio("Hay una cancelación pendiente de aprobación.")
    hab = cx.execute("select h.*, t.capacidad from pms_habitaciones h join pms_tipos_habitacion t on t.id=h.tipo_id "
                     "where h.id=%s and h.hotel_id=%s and h.activo", (habitacion_id, r["hotel_id"])).fetchone()
    if not hab:
        raise ErrorNegocio("La habitación no existe en este hotel.")
    if hab["capacidad"] < r["adultos"] + r["ninos"]:
        raise ErrorNegocio(f"La habitación {hab['numero']} no tiene capacidad para {r['adultos'] + r['ninos']} personas.")
    filas = cx.execute("select * from pms_reserva_noches where reserva_id=%s and activa and noche >= %s order by noche",
                       (r["id"], hoy if r["estado"] == "alojado" else dt.date.min)).fetchall()
    if not filas:
        raise ErrorNegocio("No hay noches pendientes para cambiar.")
    noches = [f["noche"] for f in filas]
    libres = disponibilidad.libres_por_noche(cx, r["hotel_id"], None, noches, excluir_reserva=r["id"])
    for n in noches:
        if habitacion_id not in {h["id"] for h in libres[n]}:
            raise ErrorNegocio(f"La habitación {hab['numero']} no está libre la noche del {n:%d/%m/%Y}.")
    if r["estado"] == "alojado" and hoy in noches and hab["estado_limpieza"] != "lista":
        raise ErrorNegocio(f"La habitación {hab['numero']} aún no está lista (limpia e inspeccionada).")
    antes = {f["noche"].isoformat(): f["habitacion_id"] for f in filas}
    cx.execute("update pms_reserva_noches set habitacion_id=%s where reserva_id=%s and activa and noche >= %s",
               (habitacion_id, r["id"], hoy if r["estado"] == "alojado" else dt.date.min))
    if r["estado"] == "alojado":
        cx.execute("update pms_estancias set habitacion_id=%s where reserva_id=%s", (habitacion_id, r["id"]))
    registrar(cx, actor, "reasignar_habitacion", "reserva", r["id"], antes=antes, despues={"habitacion": hab["numero"]},
              hotel_id=r["hotel_id"])


# ---------- cancelación con aprobación de gerencia ----------
def solicitar_cancelacion(actor, reserva_id: int, motivo: str):
    seguridad.exigir(actor, "reservas")
    if not motivo.strip():
        raise ErrorNegocio("Escribe el motivo de la cancelación.")
    with db.tx() as cx:
        r = _reserva(cx, reserva_id, actor)
        if r["estado"] not in ESTADOS_EDITABLES:
            raise ErrorNegocio("Solo se pueden cancelar reservas en consulta, opción o confirmadas (no alojadas).")
        if r["cancelacion_estado"] == "solicitada":
            raise ErrorNegocio("Ya hay una cancelación pendiente de aprobación.")
        cx.execute("update pms_reservas set cancelacion_estado='solicitada', cancelacion_motivo=%s, "
                   "cancelacion_solicitada_por=%s, cancelacion_resuelta_por=null, cancelacion_resuelta_en=null where id=%s",
                   (motivo.strip(), actor["id"], reserva_id))
        registrar(cx, actor, "solicitar_cancelacion", "reserva", reserva_id, despues={"motivo": motivo}, hotel_id=r["hotel_id"])


def resolver_cancelacion(actor, reserva_id: int, aprobar: bool, comentario: str = ""):
    with db.tx() as cx:
        r = _reserva(cx, reserva_id, actor)
        seguridad.exigir_aprobador(actor, r["cancelacion_solicitada_por"])
        if r["cancelacion_estado"] != "solicitada":
            raise ErrorNegocio("No hay una cancelación pendiente en esta reserva.")
        if aprobar:
            _liberar_todo(cx, actor, r, "Reserva cancelada")
            cx.execute("update pms_reservas set estado='cancelada', cancelacion_estado='aprobada', cancelacion_resuelta_por=%s, "
                       "cancelacion_resuelta_en=now() where id=%s", (actor["id"], reserva_id))
        else:
            cx.execute("update pms_reservas set cancelacion_estado='rechazada', cancelacion_resuelta_por=%s, "
                       "cancelacion_resuelta_en=now() where id=%s", (actor["id"], reserva_id))
        registrar(cx, actor, "aprobar_cancelacion" if aprobar else "rechazar_cancelacion", "reserva", reserva_id,
                  antes={"estado": r["estado"]}, despues={"comentario": comentario}, hotel_id=r["hotel_id"])


def _liberar_todo(cx, actor, r, motivo):
    cx.execute("update pms_reserva_noches set activa=false where reserva_id=%s and activa", (r["id"],))
    cx.execute("update pms_cargos set anulado=true, anulado_por=%s, motivo=coalesce(motivo,'') || %s where reserva_id=%s and "
               "not anulado and tipo in ('noche','extra')", (actor["id"], f" · {motivo}", r["id"]))
    cx.execute("update pms_cargos set estado='rechazado' where reserva_id=%s and tipo='descuento' and estado='pendiente'", (r["id"],))


def no_show(actor, reserva_id: int, hoy: dt.date | None = None):
    seguridad.exigir(actor, "reservas")
    with db.tx() as cx:
        r = _reserva(cx, reserva_id, actor)
        hoy = hoy or hoy_hotel(cx, r["hotel_id"])
        if r["estado"] not in ("opcion", "confirmada"):
            raise ErrorNegocio("Solo una reserva en opción o confirmada puede marcarse como no-show.")
        if r["fecha_entrada"] > hoy:
            raise ErrorNegocio("Aún no llega la fecha de entrada: no se puede marcar no-show.")
        _liberar_todo(cx, actor, r, "No-show")
        cx.execute("update pms_reservas set estado='no_show', cancelacion_estado=null where id=%s", (reserva_id,))
        registrar(cx, actor, "no_show", "reserva", reserva_id, antes={"estado": r["estado"]}, hotel_id=r["hotel_id"])


# ---------- check-in / check-out ----------
def checkin(actor, reserva_id: int, hoy: dt.date | None = None, habitacion_id: int | None = None) -> dict:
    seguridad.exigir(actor, "reservas")
    try:
        with db.tx() as cx:
            r0 = cx.execute("select hotel_id from pms_reservas where id=%s", (reserva_id,)).fetchone()
            if not r0:
                raise ErrorNegocio("Reserva no encontrada.")
            _lock_hotel(cx, r0["hotel_id"])
            r = _reserva(cx, reserva_id, actor)
            hoy = hoy or hoy_hotel(cx, r["hotel_id"])
            if r["estado"] != "confirmada":
                raise ErrorNegocio("Solo se puede hacer check-in a una reserva confirmada.")
            if r["cancelacion_estado"] == "solicitada":
                raise ErrorNegocio("Hay una cancelación pendiente de aprobación.")
            if not (r["fecha_entrada"] <= hoy < r["fecha_salida"]):
                raise ErrorNegocio(f"El check-in solo se hace entre la fecha de entrada ({r['fecha_entrada']:%d/%m/%Y}) y la de salida.")
            if habitacion_id is not None:
                _reasignar(cx, actor, r, habitacion_id, hoy)
            noche = cx.execute("select n.*, h.numero, h.estado_limpieza from pms_reserva_noches n join pms_habitaciones h "
                               "on h.id=n.habitacion_id where n.reserva_id=%s and n.activa and n.noche=%s", (reserva_id, hoy)).fetchone()
            if not noche:
                raise ErrorNegocio("La reserva no tiene habitación asignada para esta noche.")
            if noche["estado_limpieza"] != "lista":
                raise ErrorNegocio(f"La habitación {noche['numero']} está «{noche['estado_limpieza'].replace('_', ' ')}»: debe estar "
                                   "«lista» (limpia e inspeccionada). Cámbiala de habitación o espera a housekeeping.")
            if disponibilidad.bloqueada(cx, noche["habitacion_id"], [hoy]):
                raise ErrorNegocio(f"La habitación {noche['numero']} está bloqueada por mantenimiento.")
            if not huespedes.consentimiento_vigente(cx, r["huesped_id"], "prestacion_servicio"):
                raise ErrorNegocio("El huésped no tiene un consentimiento de datos vigente (Ley 1581).")
            cx.execute("insert into pms_estancias (hotel_id, reserva_id, habitacion_id, usuario_checkin) values (%s,%s,%s,%s)",
                       (r["hotel_id"], reserva_id, noche["habitacion_id"], actor["id"]))
            cx.execute("update pms_reservas set estado='alojado' where id=%s", (reserva_id,))
            registrar(cx, actor, "checkin", "reserva", reserva_id, antes={"estado": "confirmada"},
                      despues={"habitacion": noche["numero"]}, hotel_id=r["hotel_id"])
            return cx.execute("select * from pms_reservas where id=%s", (reserva_id,)).fetchone()
    except pge.UniqueViolation as e:
        raise (_traducir(e) or ErrorNegocio("Ya existe un check-in para esta reserva.")) from e


def checkout(actor, reserva_id: int, hoy: dt.date | None = None, permitir_saldo: bool = False) -> dict:
    """Cierra la estancia y deja la habitación «sucia». Con saldo pendiente solo gerencia puede forzar la salida."""
    seguridad.exigir(actor, "reservas")
    with db.tx() as cx:
        r = _reserva(cx, reserva_id, actor)
        hoy = hoy or hoy_hotel(cx, r["hotel_id"])
        if r["estado"] != "alojado":
            raise ErrorNegocio("Solo se puede hacer check-out a un huésped alojado.")
        saldo = facturacion.resumen_cx(cx, reserva_id)["saldo"]
        if saldo > 0:
            if not permitir_saldo:
                raise ErrorNegocio(f"La reserva tiene un saldo pendiente de {saldo}: registra el pago antes del check-out.")
            if actor["rol"] != "gerencia":
                raise seguridad.PermisoDenegado("Solo gerencia puede autorizar un check-out con saldo pendiente.")
        fin = max(hoy, r["fecha_entrada"] + dt.timedelta(days=1))
        liberar = []
        if r["fecha_salida"] > fin:  # salida anticipada: se liberan las noches no usadas
            liberar = cx.execute("select * from pms_reserva_noches where reserva_id=%s and activa and noche >= %s",
                                 (reserva_id, fin)).fetchall()
        ultima = cx.execute("select habitacion_id from pms_reserva_noches where reserva_id=%s and activa and noche < %s "
                            "order by noche desc limit 1", (reserva_id, fin)).fetchone()
        est = cx.execute("select * from pms_estancias where reserva_id=%s", (reserva_id,)).fetchone()
        hab_id = ultima["habitacion_id"] if ultima else est["habitacion_id"]
        for n in liberar:
            cx.execute("update pms_reserva_noches set activa=false where id=%s", (n["id"],))
            cx.execute("update pms_cargos set anulado=true, anulado_por=%s, motivo='Salida anticipada: noche no usada' "
                       "where reserva_id=%s and tipo='noche' and noche=%s and not anulado", (actor["id"], reserva_id, n["noche"]))
        cx.execute("update pms_estancias set checkout_real=now(), usuario_checkout=%s where reserva_id=%s", (actor["id"], reserva_id))
        cx.execute("update pms_reservas set estado='salida', fecha_salida=%s where id=%s", (min(fin, r["fecha_salida"]), reserva_id))
        _recalcular(cx, reserva_id)
        h = cx.execute("select numero, estado_limpieza from pms_habitaciones where id=%s", (hab_id,)).fetchone()
        cx.execute("update pms_habitaciones set estado_limpieza='sucia' where id=%s", (hab_id,))
        cx.execute("insert into pms_housekeeping (hotel_id, habitacion_id, estado_anterior, estado_nuevo, usuario_id, nota) "
                   "values (%s,%s,%s,'sucia',%s,'Check-out (automático)')", (r["hotel_id"], hab_id, h["estado_limpieza"], actor["id"]))
        registrar(cx, actor, "checkout", "reserva", reserva_id, antes={"estado": "alojado"},
                  despues={"habitacion": h["numero"], "saldo": saldo, "noches_liberadas": len(liberar)}, hotel_id=r["hotel_id"])
        return cx.execute("select * from pms_reservas where id=%s", (reserva_id,)).fetchone()


# ---------- consultas ----------
def listar(actor, hotel_id: int, estados: list[str] | None = None, desde: dt.date | None = None, hasta: dt.date | None = None,
           texto: str = "") -> list[dict]:
    seguridad.exigir(actor, "reservas", editar=False)
    seguridad.exigir_hotel(actor, hotel_id)
    t = f"%{texto.strip()}%"
    return db.todos(
        "select r.*, h.nombres || ' ' || h.apellidos huesped, tp.nombre tipo, "
        "(select string_agg(distinct hb.numero, ', ') from pms_reserva_noches n join pms_habitaciones hb on hb.id=n.habitacion_id "
        " where n.reserva_id=r.id and n.activa) habitaciones "
        "from pms_reservas r join pms_huespedes h on h.id=r.huesped_id join pms_tipos_habitacion tp on tp.id=r.tipo_id "
        "where r.hotel_id=%s and (%s::text[] is null or r.estado = any(%s)) and (%s::date is null or r.fecha_salida > %s) "
        "and (%s::date is null or r.fecha_entrada <= %s) and (%s = '%%%%' or r.codigo ilike %s or h.nombres ilike %s or h.apellidos ilike %s) "
        "order by r.fecha_entrada desc, r.id desc limit 500",
        (hotel_id, estados, estados, desde, desde, hasta, hasta, t, t, t, t))


def noches_de(reserva_id: int) -> list[dict]:
    return db.todos("select n.*, h.numero from pms_reserva_noches n join pms_habitaciones h on h.id=n.habitacion_id "
                    "where n.reserva_id=%s order by n.noche, n.id", (reserva_id,))

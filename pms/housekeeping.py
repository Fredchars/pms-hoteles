"""Housekeeping: estados sucia → en limpieza → inspección → lista, más fuera de servicio."""
from __future__ import annotations

from . import db, seguridad
from .auditoria import registrar
from .errores import ErrorNegocio

ESTADOS = ["sucia", "en_limpieza", "inspeccion", "lista", "fuera_de_servicio"]
NOMBRE = {"sucia": "Sucia", "en_limpieza": "En limpieza", "inspeccion": "En inspección", "lista": "Lista",
          "fuera_de_servicio": "Fuera de servicio"}
TRANSICIONES = {
    "sucia": {"en_limpieza", "fuera_de_servicio"},
    "en_limpieza": {"inspeccion", "sucia", "fuera_de_servicio"},
    "inspeccion": {"lista", "sucia", "fuera_de_servicio"},
    "lista": {"sucia", "fuera_de_servicio"},
    "fuera_de_servicio": {"sucia"},
}


def transicion_valida(de: str, a: str) -> bool:
    return a in TRANSICIONES.get(de, set())


def mover(actor, habitacion_id: int, nuevo: str, nota: str = "") -> dict:
    """Cambia el estado de limpieza respetando las transiciones. Quien pasó la habitación a inspección no puede
    darla por «lista» (separación de funciones: otra persona inspecciona)."""
    seguridad.exigir(actor, "housekeeping")
    if nuevo not in ESTADOS:
        raise ErrorNegocio("Estado no válido.")
    with db.tx() as cx:
        h = cx.execute("select * from pms_habitaciones where id=%s for update", (habitacion_id,)).fetchone()
        if not h:
            raise ErrorNegocio("Habitación no encontrada.")
        seguridad.exigir_hotel(actor, h["hotel_id"])
        if not transicion_valida(h["estado_limpieza"], nuevo):
            raise ErrorNegocio(f"No se puede pasar de «{NOMBRE[h['estado_limpieza']]}» a «{NOMBRE[nuevo]}». "
                               f"Siguiente paso permitido: {', '.join(NOMBRE[x] for x in sorted(TRANSICIONES[h['estado_limpieza']]))}.")
        if nuevo == "lista":
            ult = cx.execute("select usuario_id from pms_housekeeping where habitacion_id=%s and estado_nuevo='inspeccion' "
                             "order by id desc limit 1", (habitacion_id,)).fetchone()
            if ult and ult["usuario_id"] == actor["id"]:
                raise ErrorNegocio("Quien dejó la habitación en inspección no puede aprobarla: la debe revisar otra persona.")
        if nuevo == "fuera_de_servicio":
            if cx.execute("select 1 from pms_estancias e join pms_reservas r on r.id=e.reserva_id join pms_reserva_noches n "
                          "on n.reserva_id=r.id and n.activa and n.habitacion_id=%s where r.estado='alojado' and e.habitacion_id=%s "
                          "limit 1", (habitacion_id, habitacion_id)).fetchone():
                raise ErrorNegocio("La habitación tiene un huésped alojado: cámbialo de habitación antes de ponerla fuera de servicio.")
            if not nota.strip():
                raise ErrorNegocio("Escribe el motivo para dejar la habitación fuera de servicio.")
        cx.execute("update pms_habitaciones set estado_limpieza=%s where id=%s", (nuevo, habitacion_id))
        cx.execute("insert into pms_housekeeping (hotel_id, habitacion_id, estado_anterior, estado_nuevo, usuario_id, nota) "
                   "values (%s,%s,%s,%s,%s,%s)", (h["hotel_id"], habitacion_id, h["estado_limpieza"], nuevo, actor["id"], nota or None))
        registrar(cx, actor, "housekeeping", "habitacion", habitacion_id, antes={"estado": h["estado_limpieza"]},
                  despues={"estado": nuevo, "nota": nota}, hotel_id=h["hotel_id"])
        return {**h, "estado_limpieza": nuevo}


def tablero(actor, hotel_id: int) -> list[dict]:
    """Habitaciones con su estado y si hay un huésped alojado. No incluye precios ni datos de pago."""
    seguridad.exigir(actor, "housekeeping", editar=False)
    seguridad.exigir_hotel(actor, hotel_id)
    return db.todos(
        "select h.id, h.numero, h.planta, t.nombre tipo, h.estado_limpieza, "
        "exists (select 1 from pms_estancias e join pms_reservas r on r.id=e.reserva_id where e.habitacion_id=h.id "
        "and r.estado='alojado') ocupada, "
        "(select estado_nuevo || ' · ' || coalesce(nota,'') from pms_housekeeping k where k.habitacion_id=h.id order by k.id desc limit 1) ultima "
        "from pms_habitaciones h join pms_tipos_habitacion t on t.id=h.tipo_id where h.hotel_id=%s and h.activo "
        "order by h.planta, h.numero", (hotel_id,))


def historial(actor, habitacion_id: int) -> list[dict]:
    seguridad.exigir(actor, "housekeeping", editar=False)
    return db.todos("select k.*, u.nombre usuario from pms_housekeeping k left join pms_usuarios u on u.id=k.usuario_id "
                    "where k.habitacion_id=%s order by k.id desc limit 30", (habitacion_id,))

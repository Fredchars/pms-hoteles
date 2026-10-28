import threading

import psycopg
import pytest

from pms import config, db, reservas
from pms.errores import ErrorNegocio
from tests.conftest import D


def test_no_se_vende_dos_veces_el_mismo_tipo_cuando_se_agota(m):
    m.reservar(desde=2, noches=2, tipo=m.tipo_ind)           # única individual
    with pytest.raises(ErrorNegocio, match="No hay disponibilidad"):
        m.reservar(desde=3, noches=2, tipo=m.tipo_ind)        # se cruza en la noche 3


def test_dos_dobles_se_venden_y_la_tercera_no(m):
    a = m.reservar(desde=2, noches=2)
    b = m.reservar(desde=2, noches=2)
    noches = db.todos("select habitacion_id, noche from pms_reserva_noches where activa")
    assert len({(n["habitacion_id"], n["noche"]) for n in noches}) == len(noches) == 4
    assert {n["habitacion_id"] for n in noches} == {m.h201, m.h202}
    with pytest.raises(ErrorNegocio, match="No hay disponibilidad"):
        m.reservar(desde=2, noches=1)
    assert a["id"] != b["id"]


def test_la_base_de_datos_impide_la_doble_venta_aunque_se_salte_la_aplicacion(m):
    r = m.reservar(desde=2, noches=1)
    n = db.todos("select * from pms_reserva_noches where reserva_id=%s", (r["id"],))[0]
    with pytest.raises(psycopg.errors.UniqueViolation):
        with db.tx() as cx:
            cx.execute("insert into pms_reserva_noches (hotel_id, reserva_id, noche, tipo_id, habitacion_id, precio) values (%s,%s,%s,%s,%s,1)",
                       (n["hotel_id"], r["id"], n["noche"], n["tipo_id"], n["habitacion_id"]))


def test_ventas_simultaneas_no_duplican_habitacion(m):
    """Seis recepcionistas intentan vender a la vez la misma noche de un tipo con solo 2 habitaciones."""
    resultados, huespedes_ = [], [m.nuevo_huesped(m.A) for _ in range(6)]

    def vender(i):
        try:
            reservas.crear(m.rec, m.A, huespedes_[i], m.tipo_doble, m.hoy + D(days=5), m.hoy + D(days=6), 2)
            resultados.append("ok")
        except ErrorNegocio:
            resultados.append("sin")

    hilos = [threading.Thread(target=vender, args=(i,)) for i in range(6)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert resultados.count("ok") == 2 and resultados.count("sin") == 4
    assert db.uno("select count(*) n from pms_reserva_noches where activa")["n"] == 2


def test_cancelar_libera_la_habitacion_para_otra_reserva(m):
    r = m.reservar(desde=2, noches=2, tipo=m.tipo_ind)
    reservas.solicitar_cancelacion(m.rec, r["id"], "Cambio de planes")
    reservas.resolver_cancelacion(m.g1, r["id"], True)
    assert db.uno("select count(*) n from pms_reserva_noches where activa")["n"] == 0
    m.reservar(desde=2, noches=2, tipo=m.tipo_ind)   # ahora sí cabe


def test_referencia_externa_unica_por_canal(m):
    m.reservar(desde=2, noches=1, canal="booking", referencia_externa="BK-1")
    with pytest.raises(ErrorNegocio, match="referencia externa"):
        m.reservar(desde=9, noches=1, canal="booking", referencia_externa="BK-1")
    m.reservar(desde=9, noches=1, canal="airbnb", referencia_externa="BK-1")  # otro canal: permitido


def test_modificar_fechas_respeta_ocupacion_de_otras_reservas(m):
    m.reservar(desde=3, noches=2, tipo=m.tipo_ind)
    r = m.reservar(desde=1, noches=2, tipo=m.tipo_ind)
    with pytest.raises(ErrorNegocio, match="No hay disponibilidad"):
        reservas.modificar(m.rec, r["id"], salida=m.hoy + D(days=4))   # chocaría con la noche 3


def test_capacidad_del_tipo(m):
    with pytest.raises(ErrorNegocio, match="máximo"):
        m.reservar(desde=1, noches=1, tipo=m.tipo_ind, adultos=2)


def test_fecha_pasada_no_permitida(m):
    with pytest.raises(ErrorNegocio, match="anterior a hoy"):
        m.reservar(desde=-2, noches=1)

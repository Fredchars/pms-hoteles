"""Plano de habitaciones: estado por habitación y fechas (misma regla que la reserva), filtros, detalle con precio y prellenado."""
from decimal import Decimal

import pytest

from pms import bloqueos, config, db, disponibilidad, plano, reservas, tarifas
from pms.errores import ErrorNegocio, PermisoDenegado

from .conftest import D, RAIZ


def _estados(m, desde=1, noches=2, adultos=2, ninos=0, actor=None):
    r = plano.consultar(actor or m.rec, m.A, m.hoy + D(days=desde), m.hoy + D(days=desde + noches), adultos, ninos)
    return {h["numero"]: h["estado"] for h in r["habitaciones"]}, r


def test_todo_disponible_y_capacidad_insuficiente(m):
    est, r = _estados(m)
    assert est["201"] == est["202"] == "disponible"
    assert est["301"] == "capacidad"          # individual (1) con 2 adultos
    est, _ = _estados(m, adultos=3)
    assert est["201"] == est["202"] == "capacidad" and est["301"] == "capacidad"
    est, _ = _estados(m, adultos=1)
    assert est["301"] == "disponible"
    assert r["plantas"] == [2, 3] and [t["nombre"] for t in r["tipos"]] == ["Doble", "Individual"]


def test_ocupada_opcion_bloqueada_y_fuera_de_servicio(m):
    m.reservar(desde=1, noches=2, estado="confirmada", habitacion_id=m.h201)
    m.reservar(desde=1, noches=2, estado="opcion", habitacion_id=m.h202, huesped=m.nuevo_huesped(m.A))
    bloqueos.crear(m.g1, m.A, m.h301, m.hoy + D(days=1), m.hoy + D(days=1), "Pintura")
    est, _ = _estados(m, adultos=1)
    assert est == {"201": "ocupada", "202": "opcion", "301": "bloqueada"}
    # prioridad: fuera de servicio manda sobre ocupada
    with db.tx() as cx:
        cx.execute("update pms_habitaciones set estado_limpieza='fuera_de_servicio' where id=%s", (m.h201,))
    est, _ = _estados(m, adultos=1)
    assert est["201"] == "fuera_de_servicio"


def test_solape_parcial_y_noche_de_salida_libre(m):
    m.reservar(desde=1, noches=2, habitacion_id=m.h201)           # noches 1 y 2; sale el día 3
    assert _estados(m, desde=2, noches=2)[0]["201"] == "ocupada"   # noches 2 y 3: la 2 está vendida
    assert _estados(m, desde=3, noches=2)[0]["201"] == "disponible"  # la noche de salida (3) está libre
    assert _estados(m, desde=0, noches=1)[0]["201"] == "disponible"


def test_cancelada_libera_la_habitacion(m):
    r = m.reservar(desde=1, noches=2, habitacion_id=m.h201)
    assert _estados(m)[0]["201"] == "ocupada"
    reservas.solicitar_cancelacion(m.rec, r["id"], "prueba")
    reservas.resolver_cancelacion(m.g1, r["id"], True, "ok")
    assert _estados(m)[0]["201"] == "disponible"


def test_disponible_equivale_a_poder_reservarla(m):
    """Una sola regla: lo que el plano llama «disponible» es exactamente lo que reservas.crear acepta (unicidad habitación+noche)."""
    m.reservar(desde=1, noches=3, habitacion_id=m.h201)
    bloqueos.crear(m.g1, m.A, m.h202, m.hoy + D(days=2), m.hoy + D(days=2), "Obra")
    est, r = _estados(m, desde=1, noches=3, adultos=1)
    assert est == {"201": "ocupada", "202": "bloqueada", "301": "disponible"}
    por_num = {h["numero"]: h for h in r["habitaciones"]}
    for num in ("201", "202"):
        with pytest.raises(ErrorNegocio):
            reservas.crear(m.rec, m.A, m.huesped, por_num[num]["tipo_id"], m.hoy + D(days=1), m.hoy + D(days=4), 1, habitacion_id=por_num[num]["id"])
    ok = reservas.crear(m.rec, m.A, m.huesped, por_num["301"]["tipo_id"], m.hoy + D(days=1), m.hoy + D(days=4), 1, habitacion_id=por_num["301"]["id"])
    assert ok["estado"] == "confirmada"
    assert _estados(m, desde=1, noches=3, adultos=1)[0]["301"] == "ocupada"       # y tras reservar, el plano lo refleja


def test_capacidad_usa_la_misma_regla_que_reservas(m):
    assert disponibilidad.cabe(2, 2, 0) and not disponibilidad.cabe(2, 2, 1) and not disponibilidad.cabe(2, 0, 1)
    with pytest.raises(ErrorNegocio, match="máximo 2"):
        m.reservar(adultos=2, ninos=1)


def test_filtros(m):
    _, r = _estados(m, adultos=1)
    habs = r["habitaciones"]
    nums = lambda l: [h["numero"] for h in l]          # noqa: E731
    assert nums(plano.filtrar(habs)) == ["201", "202", "301"]
    assert nums(plano.filtrar(habs, planta=2)) == ["201", "202"]
    assert nums(plano.filtrar(habs, planta=3)) == ["301"]
    assert nums(plano.filtrar(habs, tipo_id=m.tipo_ind)) == ["301"]
    assert nums(plano.filtrar(habs, solo_mar=True)) == ["201", "202"]          # vista «Mar» deducida del texto
    m.reservar(desde=1, noches=2, habitacion_id=m.h201)
    _, r = _estados(m, adultos=1)
    assert nums(plano.filtrar(r["habitaciones"], ocultar_no_disponibles=True)) == ["202", "301"]
    assert nums(plano.filtrar(r["habitaciones"], planta=2, solo_mar=True, ocultar_no_disponibles=True)) == ["202"]
    vis = {h["numero"]: h["visual"] for h in plano.filtrar(r["habitaciones"], seleccionada=m.h202)}
    assert vis == {"201": "ocupada", "202": "seleccionada", "301": "disponible"}
    # una habitación seleccionada que ya no está disponible no se pinta como seleccionada
    vis = {h["numero"]: h["visual"] for h in plano.filtrar(r["habitaciones"], seleccionada=m.h201)}
    assert vis["201"] == "ocupada"
    assert plano.resumen(r["habitaciones"])["ocupada"] == 1


def test_vista_al_mar_atributo(m):
    with db.tx() as cx:
        v = {h["numero"]: h["vista_mar"] for h in cx.execute("select numero, vista_mar from pms_habitaciones where hotel_id=%s", (m.A,)).fetchall()}
    assert v == {"201": True, "202": True, "301": False}
    h = config.crear_habitacion(m.admin, m.A, "401", 4, m.tipo_doble, 20, "Interior con patio")
    h2 = config.crear_habitacion(m.admin, m.A, "402", 4, m.tipo_doble, 20, "Interior", vista_mar=True)
    h3 = config.crear_habitacion(m.admin, m.A, "403", 4, m.tipo_doble, 20, "Mar", vista_mar=False)
    h4 = config.crear_habitacion(m.admin, m.A, "404", 4, m.tipo_doble, 20, "Marítima y amplia")
    with db.tx() as cx:
        got = {r["id"]: r["vista_mar"] for r in cx.execute("select id, vista_mar from pms_habitaciones where id = any(%s)", ([h, h2, h3, h4],)).fetchall()}
    assert got == {h: False, h2: True, h3: False, h4: False}


def test_migracion_vista_mar_es_idempotente_y_rellena_solo_la_primera_vez(m):
    sql = (RAIZ / "db" / "01_esquema_pms.sql").read_text()
    with db.tx() as cx:
        cx.execute("update pms_habitaciones set vista_mar=false where id=%s", (m.h201,))     # decisión manual
        cx.execute(sql)                                                                       # 2.ª ejecución: no toca nada
        assert cx.execute("select vista_mar from pms_habitaciones where id=%s", (m.h201,)).fetchone()["vista_mar"] is False
        cx.execute("alter table pms_habitaciones drop column vista_mar")                      # base antigua sin la columna
        cx.execute(sql)
        v = {h["numero"]: h["vista_mar"] for h in cx.execute("select numero, vista_mar from pms_habitaciones where hotel_id=%s", (m.A,)).fetchall()}
    assert v == {"201": True, "202": True, "301": False}


def test_permisos_del_plano(m):
    assert plano.consultar(m.rec, m.A, m.hoy, m.hoy + D(days=1))["habitaciones"]
    assert plano.consultar(m.g1, m.A, m.hoy, m.hoy + D(days=1))["habitaciones"]
    assert plano.consultar(m.admin, m.A, m.hoy, m.hoy + D(days=1))["habitaciones"]          # administrador: solo lectura
    assert plano.consultar(m.admin, m.B, m.hoy, m.hoy + D(days=1))["habitaciones"]          # todos los hoteles
    with pytest.raises(PermisoDenegado):
        plano.consultar(m.hk1, m.A, m.hoy, m.hoy + D(days=1))
    with pytest.raises(PermisoDenegado):
        plano.consultar(m.rec, m.B, m.hoy, m.hoy + D(days=1))                                # otro hotel
    with pytest.raises(ErrorNegocio):
        plano.consultar(m.rec, m.A, m.hoy + D(days=2), m.hoy + D(days=2))
    with pytest.raises(ErrorNegocio, match="máximo"):
        plano.consultar(m.rec, m.A, m.hoy, m.hoy + D(days=200))


def test_detalle_con_desglose_de_precio(m):
    d = plano.detalle(m.rec, m.A, m.h201, m.hoy + D(days=1), m.hoy + D(days=3), 2, 0)
    c = d["cotizacion"]
    assert d["habitacion"]["numero"] == "201" and d["habitacion"]["capacidad"] == 2 and d["reservable"]
    assert d["camas_texto"] == ["1 × matrimonial (150 cm)"]
    assert [p for _, p in c["noches"]] == [Decimal("100000.00")] * 2
    assert c["subtotal"] == Decimal("200000.00")
    assert c["impuestos"][0]["monto"] == Decimal("38000.00") and c["total"] == Decimal("238000.00")
    assert c["por_persona_noche"] == Decimal("59500.00")                                   # 238000 / 2 personas / 2 noches
    # misma cifra que calcula la reserva real
    with db.tx() as cx:
        precios = tarifas.precios_para(cx, m.tipo_doble, [m.hoy + D(days=1), m.hoy + D(days=2)])
    assert sum(precios.values()) == c["subtotal"]


def test_detalle_sin_tarifa_cierre_y_no_disponible(m):
    lejos = m.hoy + D(days=900)
    d = plano.detalle(m.rec, m.A, m.h201, lejos, lejos + D(days=2), 2, 0)
    assert d["cotizacion"] is None and "tarifa" in d["error"] and not d["reservable"]
    tarifas.crear(m.admin, m.A, m.tipo_ind, "Cierre", m.hoy + D(days=500), m.hoy + D(days=510), 1000, cierre_ventas=True)
    d = plano.detalle(m.rec, m.A, m.h301, m.hoy + D(days=501), m.hoy + D(days=503), 1, 0)
    assert "cerradas" in d["error"] and not d["reservable"]
    m.reservar(desde=1, noches=2, habitacion_id=m.h201)
    d = plano.detalle(m.rec, m.A, m.h201, m.hoy + D(days=1), m.hoy + D(days=3), 2, 0)
    assert d["cotizacion"] is not None and not d["habitacion"]["disponible"] and not d["reservable"]
    with pytest.raises(ErrorNegocio):
        plano.detalle(m.rec, m.A, m.hb1, m.hoy, m.hoy + D(days=1))                          # habitación de otro hotel


def test_estancia_minima_en_el_detalle(m):
    tarifas.crear(m.admin, m.A, m.tipo_ind, "Puente", m.hoy + D(days=600), m.hoy + D(days=610), 70000, estancia_minima=3)
    d = plano.detalle(m.rec, m.A, m.h301, m.hoy + D(days=601), m.hoy + D(days=603), 1, 0)
    assert "mínima" in d["error"] and not d["reservable"]
    d = plano.detalle(m.rec, m.A, m.h301, m.hoy + D(days=601), m.hoy + D(days=604), 1, 0)
    assert d["reservable"]


def test_prellenado_y_creacion_de_la_reserva(m):
    p = plano.prellenado(m.rec, m.A, m.h202, m.hoy + D(days=1), m.hoy + D(days=3), 2, 0)
    assert p == {"hotel_id": m.A, "habitacion_id": m.h202, "numero": "202", "tipo_id": m.tipo_doble, "tipo": "Doble",
                 "entrada": m.hoy + D(days=1), "salida": m.hoy + D(days=3), "adultos": 2, "ninos": 0}
    r = reservas.crear(m.rec, m.A, m.huesped, p["tipo_id"], p["entrada"], p["salida"], p["adultos"], p["ninos"], habitacion_id=p["habitacion_id"])
    assert {n["numero"] for n in reservas.noches_de(r["id"])} == {"202"}
    with pytest.raises(ErrorNegocio, match="ya no está disponible"):
        plano.prellenado(m.rec, m.A, m.h202, m.hoy + D(days=1), m.hoy + D(days=3), 2, 0)   # alguien la reservó entretanto
    with pytest.raises(PermisoDenegado):
        plano.prellenado(m.admin, m.A, m.h201, m.hoy + D(days=1), m.hoy + D(days=3), 2, 0)  # administrador: solo lectura
    with pytest.raises(ErrorNegocio, match="ya no está disponible"):
        plano.prellenado(m.rec, m.A, m.h301, m.hoy + D(days=1), m.hoy + D(days=3), 2, 0)    # capacidad insuficiente

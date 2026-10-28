import re
from pathlib import Path

from pms import db, facturacion, reservas, seguridad, vistas, semilla
from tests.conftest import D, RAIZ


def test_reporte_de_ocupacion_e_ingresos(m):
    r = m.reservar(desde=0, noches=2)                        # 2 noches × 100 000
    m.reservar(desde=1, noches=1, tipo=m.tipo_ind)           # 1 noche × 60 000
    from pms import bloqueos
    bloqueos.crear(m.g1, m.A, m.h202, m.hoy + D(days=1), m.hoy + D(days=1), "Pintura")
    df = vistas.reporte_diario(m.g1, m.A, m.hoy, m.hoy + D(days=2))
    assert list(df["vendidas"]) == [1, 2, 0]
    assert list(df["vendibles"]) == [3, 2, 3]                # el día 2 hay una habitación bloqueada
    assert list(df["ocupacion_pct"]) == [33.3, 100.0, 0.0]
    assert list(df["ingreso_alojamiento"]) == [100000, 160000, 0]
    res = vistas.resumen_periodo(df)
    assert res["vendidas"] == 3 and res["vendibles"] == 8 and res["ocupacion_pct"] == 37.5 and res["ingreso_neto"] == 260000
    assert vistas.ingresos_por_mes(df)["ingreso_neto"].sum() == 260000


def test_dashboard_del_dia(m):
    a = m.reservar(desde=0, noches=2)
    m.reservar(desde=0, noches=1, tipo=m.tipo_ind)
    reservas.checkin(m.rec, a["id"])
    facturacion.registrar_pago(m.rec, a["id"], "efectivo", 50000)
    reservas.solicitar_cancelacion(m.rec, m.reservar(desde=5, noches=1)["id"], "x")
    d = vistas.dashboard(m.rec, m.A)
    assert len(d["llegadas"]) == 2 and d["en_casa"] == 1 and d["ocupadas_hoy"] == 2
    assert d["ocupacion_pct"] == 66.7 and float(d["ingresos_dia"]) == 160000 and float(d["cobros_dia"]) == 50000
    assert d["cancelaciones_pendientes"] == 1 and d["moneda"] == "COP"
    pend = vistas.pendientes_aprobacion(m.g1, m.A)
    assert len(pend["cancelaciones"]) == 1


def test_calendario_solo_lectura_con_estados(m):
    a = m.reservar(desde=1, noches=2)
    from pms import bloqueos
    bloqueos.crear(m.g1, m.A, m.h301, m.hoy, m.hoy + D(days=1), "Pintura")
    cal = vistas.calendario(m.rec, m.A, m.hoy, 5)
    assert len(cal["habitaciones"]) == 3 and len(cal["fechas"]) == 5
    estados = {c["estado"] for c in cal["celdas"].values()}
    assert estados == {"confirmada", "bloqueo"}


def test_esquema_tiene_17_tablas_pms_con_rls_y_solo_prefijo_pms():
    sql = (RAIZ / "db" / "01_esquema_pms.sql").read_text()
    tablas = re.findall(r"create table if not exists (\w+)", sql)
    assert len(tablas) == 17 and all(t.startswith("pms_") for t in tablas)
    for t in ("pms_reserva_noches", "pms_consentimientos", "pms_bloqueos", "pms_impuestos", "pms_camas"):
        assert t in tablas
    toc = re.findall(r"(?:alter table|drop table|truncate)\s+(?:if exists\s+)?(\w+)", sql + (RAIZ / "db" / "02_rls_pms.sql").read_text())
    assert all(t.startswith("pms_") for t in toc if t not in ("public",))
    rls = {r["tablename"]: r["rowsecurity"] for r in db.todos("select tablename, rowsecurity from pg_tables where tablename like 'pms\\_%%'")}
    assert set(rls) == set(tablas) and all(rls.values())


def test_semilla_crea_3_hoteles_con_layout_de_18_habitaciones():
    claves = semilla.sembrar(reiniciar=True, guardar_claves=False)
    assert len(claves) == 19
    hoteles = db.todos("select * from pms_hoteles order by id")
    assert [(h["moneda"]) for h in hoteles] == ["COP", "DOP", "PEN"]
    for h in hoteles:
        habs = db.todos("select h.numero, t.nombre tipo, t.capacidad from pms_habitaciones h join pms_tipos_habitacion t on t.id=h.tipo_id where h.hotel_id=%s order by 1", (h["id"],))
        assert len(habs) == 18
        por_tipo = {}
        for x in habs:
            por_tipo[x["tipo"]] = por_tipo.get(x["tipo"], 0) + 1
        assert por_tipo == {"Familiar Mar": 3, "Triple Mar": 3, "Doble matrimonial": 9, "Individual": 3}
        h101 = next(x for x in habs if x["numero"] == "101")
        assert h101["capacidad"] == 4
        assert db.uno("select count(*) n from pms_camas where hotel_id=%s", (h["id"],))["n"] == 3 * (1 + 2 + 1 + 1 + 1 + 1)
    assert db.uno("select count(*) n from pms_camas c join pms_habitaciones h on h.id=c.habitacion_id where h.numero='102' and h.hotel_id=%s and c.tipo='individual' and c.ancho_cm=90", (hoteles[0]["id"],))["n"] == 1
    assert db.uno("select count(*) n from pms_impuestos where hotel_id=%s", (hoteles[1]["id"],))["n"] == 2
    # contraseñas: solo hash
    assert db.uno("select count(*) n from pms_usuarios where clave_hash not like '$2%%'")["n"] == 0
    assert db.uno("select count(*) n from pms_reservas where estado in ('alojado','salida','confirmada','opcion','consulta','cancelada','no_show') ")["n"] > 50
    # sin doble venta en toda la semilla
    assert db.uno("select count(*) n from (select habitacion_id, noche from pms_reserva_noches where activa group by 1,2 having count(*)>1) x")["n"] == 0
    # la semilla no se repite si ya hay datos
    assert semilla.sembrar() == {}
    # los usuarios de la semilla pueden iniciar sesión
    e, c = next(iter(claves.items()))
    assert seguridad.iniciar_sesion(e, c)["email"] == e

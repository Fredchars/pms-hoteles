import pytest

from pms import bloqueos, config, facturacion, housekeeping, huespedes, reservas, seguridad, tarifas, vistas
from pms.errores import ErrorNegocio, PermisoDenegado
from tests.conftest import D


def test_matriz_de_permisos_del_diseno():
    p = seguridad.nivel
    assert p("housekeeping", "facturacion") is None and p("housekeeping", "reservas") is None and p("housekeeping", "tarifas") is None
    assert p("recepcion", "tarifas") == "ver" and p("recepcion", "configuracion") is None and p("recepcion", "reportes") is None
    assert p("gerencia", "reportes") == "x" and p("gerencia", "configuracion") == "ver"
    assert p("administrador", "configuracion") == "x" and p("administrador", "reservas") == "ver"
    assert p("housekeeping", "housekeeping") == "x" and p("recepcion", "housekeeping") == "ver"


def test_housekeeping_no_crea_reservas_ni_ve_facturacion(m):
    r = m.reservar(desde=1, noches=1)
    with pytest.raises(PermisoDenegado):
        reservas.crear(m.hk1, m.A, m.huesped, m.tipo_doble, m.hoy + D(days=3), m.hoy + D(days=4))
    with pytest.raises(PermisoDenegado):
        facturacion.resumen(m.hk1, r["id"])
    with pytest.raises(PermisoDenegado):
        reservas.listar(m.hk1, m.A)
    with pytest.raises(PermisoDenegado):
        vistas.dashboard(m.hk1, m.A)


def test_recepcion_no_edita_tarifas_ni_configuracion_ni_ve_reportes(m):
    t = tarifas.listar(m.A)[0]
    with pytest.raises(PermisoDenegado):
        tarifas.actualizar(m.rec, t["id"], precio=1)
    with pytest.raises(PermisoDenegado):
        config.guardar_impuesto(m.rec, m.A, "X", 1)
    with pytest.raises(PermisoDenegado):
        vistas.reporte_diario(m.rec, m.A, m.hoy, m.hoy)
    assert tarifas.listar(m.A)  # pero sí puede ver (nivel "ver")


def test_gerencia_no_configura_y_administrador_no_opera(m):
    with pytest.raises(PermisoDenegado):
        config.crear_tipo(m.g1, m.A, "Suite", 3)
    with pytest.raises(PermisoDenegado):
        reservas.crear(m.admin, m.A, m.huesped, m.tipo_doble, m.hoy + D(days=3), m.hoy + D(days=4))
    with pytest.raises(PermisoDenegado):
        housekeeping.mover(m.rec, m.h201, "sucia")   # recepción solo ve housekeeping
    reservas.listar(m.admin, m.A)                      # el administrador sí puede consultar


def test_aislamiento_entre_hoteles(m):
    with pytest.raises(PermisoDenegado):
        reservas.listar(m.rec, m.B)
    with pytest.raises(PermisoDenegado):
        reservas.crear(m.rec, m.B, m.huesped_b, m.tipo_b, m.hoy + D(days=3), m.hoy + D(days=4))
    r = m.reservar(desde=1, noches=1)
    with pytest.raises(PermisoDenegado):
        reservas.solicitar_cancelacion(m.recb, r["id"], "intento ajeno")
    with pytest.raises(PermisoDenegado):
        facturacion.resumen(m.recb, r["id"])
    assert [h["id"] for h in config.hoteles_visibles(m.rec)] == [m.A]
    assert {h["id"] for h in config.hoteles_visibles(m.admin)} == {m.A, m.B}


def test_bloqueos_solo_gerencia_y_admin_editan(m):
    with pytest.raises(PermisoDenegado):
        bloqueos.crear(m.rec, m.A, m.h201, m.hoy, m.hoy, "x")
    with pytest.raises(PermisoDenegado):
        bloqueos.crear(m.hk1, m.A, m.h201, m.hoy, m.hoy, "x")
    bloqueos.crear(m.g1, m.A, m.h201, m.hoy + D(days=1), m.hoy + D(days=2), "Pintura")
    assert bloqueos.listar(m.hk1, m.A)


def test_solo_administrador_gestiona_usuarios(m):
    with pytest.raises(PermisoDenegado):
        config.crear_usuario(m.g1, "nuevo@t.test", "Nuevo", "recepcion", "clave-1234", m.A)
    config.crear_usuario(m.admin, "nuevo@t.test", "Nuevo", "recepcion", "clave-1234", m.A)
    with pytest.raises(ErrorNegocio):
        config.crear_usuario(m.admin, "otro@t.test", "Otro", "recepcion", "clave-1234", None)   # rol sin hotel
    with pytest.raises(ErrorNegocio):
        config.crear_usuario(m.admin, "malo", "Malo", "recepcion", "clave-1234", m.A)
    with pytest.raises(ErrorNegocio):
        config.crear_usuario(m.admin, "c@t.test", "C", "recepcion", "corta", m.A)

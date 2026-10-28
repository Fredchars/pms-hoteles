import pytest

from pms import db, facturacion, housekeeping as hk, reservas
from pms.errores import ErrorNegocio, PermisoDenegado
from tests.conftest import D


def test_cadena_de_housekeeping_y_transiciones_invalidas(m):
    assert hk.transicion_valida("sucia", "en_limpieza") and not hk.transicion_valida("sucia", "lista")
    assert not hk.transicion_valida("fuera_de_servicio", "lista") and hk.transicion_valida("fuera_de_servicio", "sucia")
    hk.mover(m.hk1, m.h201, "sucia")
    with pytest.raises(ErrorNegocio, match="No se puede pasar"):
        hk.mover(m.hk1, m.h201, "lista")
    hk.mover(m.hk1, m.h201, "en_limpieza")
    hk.mover(m.hk1, m.h201, "inspeccion")
    with pytest.raises(ErrorNegocio, match="otra persona"):
        hk.mover(m.hk1, m.h201, "lista")          # quien limpió no puede aprobar la inspección
    hk.mover(m.hk2, m.h201, "lista")
    assert db.uno("select estado_limpieza e from pms_habitaciones where id=%s", (m.h201,))["e"] == "lista"
    assert len(hk.historial(m.hk1, m.h201)) == 4


def test_fuera_de_servicio_pide_motivo(m):
    with pytest.raises(ErrorNegocio, match="motivo"):
        hk.mover(m.hk1, m.h201, "fuera_de_servicio")
    hk.mover(m.hk1, m.h201, "fuera_de_servicio", "Fuga")


def test_checkin_checkout_flujo_completo(m):
    r = m.reservar(desde=0, noches=2)
    # las habitaciones nacen 'lista'; se ensucia la asignada para probar la regla
    hab = db.uno("select habitacion_id h from pms_reserva_noches where reserva_id=%s limit 1", (r["id"],))["h"]
    with db.tx() as cx:
        cx.execute("update pms_habitaciones set estado_limpieza='sucia' where id=%s", (hab,))
    with pytest.raises(ErrorNegocio, match="debe estar «lista»"):
        reservas.checkin(m.rec, r["id"])
    m.lista(hab)
    r = reservas.checkin(m.rec, r["id"])
    assert r["estado"] == "alojado"
    with pytest.raises(ErrorNegocio, match="saldo pendiente"):
        reservas.checkout(m.rec, r["id"])
    with pytest.raises(PermisoDenegado):
        reservas.checkout(m.rec, r["id"], permitir_saldo=True)
    saldo = facturacion.resumen(m.rec, r["id"])["saldo"]
    facturacion.registrar_pago(m.rec, r["id"], "datafono", saldo)
    r = reservas.checkout(m.rec, r["id"], hoy=m.hoy + D(days=2))
    assert r["estado"] == "salida"
    assert db.uno("select estado_limpieza e from pms_habitaciones where id=%s", (hab,))["e"] == "sucia"      # automático
    assert db.uno("select count(*) n from pms_housekeeping where habitacion_id=%s and nota like 'Check-out%%'", (hab,))["n"] == 1
    est = db.uno("select * from pms_estancias where reserva_id=%s", (r["id"],))
    assert est["checkin_real"] and est["checkout_real"]


def test_checkout_con_saldo_solo_lo_fuerza_gerencia(m):
    r = m.reservar(desde=0, noches=1)
    reservas.checkin(m.rec, r["id"])
    out = reservas.checkout(m.g1, r["id"], hoy=m.hoy + D(days=1), permitir_saldo=True)
    assert out["estado"] == "salida"
    assert facturacion.resumen(m.g1, r["id"])["saldo"] > 0


def test_checkin_solo_confirmadas_y_en_fecha(m):
    op = m.reservar(desde=0, noches=1, estado="opcion")
    with pytest.raises(ErrorNegocio, match="confirmada"):
        reservas.checkin(m.rec, op["id"])
    fut = m.reservar(desde=5, noches=1)
    with pytest.raises(ErrorNegocio, match="check-in solo se hace"):
        reservas.checkin(m.rec, fut["id"])
    reservas.modificar(m.rec, op["id"], estado="confirmada")
    reservas.checkin(m.rec, op["id"])
    with pytest.raises(ErrorNegocio, match="confirmada"):
        reservas.checkin(m.rec, op["id"])   # ya está alojada


def test_salida_anticipada_libera_noches_y_anula_cargos(m):
    r = m.reservar(desde=0, noches=4)
    reservas.checkin(m.rec, r["id"])
    facturacion.registrar_pago(m.rec, r["id"], "efectivo", facturacion.resumen(m.rec, r["id"])["saldo"] - 0)
    # tras pagar 4 noches, sale al día siguiente: se liberan 3 noches y queda saldo a favor, no saldo pendiente
    out = reservas.checkout(m.rec, r["id"], hoy=m.hoy + D(days=1))
    assert out["fecha_salida"] == m.hoy + D(days=1)
    assert db.uno("select count(*) n from pms_reserva_noches where reserva_id=%s and activa", (r["id"],))["n"] == 1
    assert facturacion.resumen(m.rec, r["id"])["subtotal"] == 100000


def test_estados_de_cancelacion_y_aprobacion(m):
    r = m.reservar(desde=3, noches=2)
    with pytest.raises(ErrorNegocio, match="motivo"):
        reservas.solicitar_cancelacion(m.rec, r["id"], " ")
    reservas.solicitar_cancelacion(m.rec, r["id"], "Cambio de planes")
    with pytest.raises(ErrorNegocio, match="ya hay|Ya hay"):
        reservas.solicitar_cancelacion(m.rec, r["id"], "otra vez")
    with pytest.raises(PermisoDenegado):
        reservas.resolver_cancelacion(m.rec, r["id"], True)             # recepción no aprueba
    with pytest.raises(PermisoDenegado):
        reservas.resolver_cancelacion(m.admin, r["id"], True)           # administrador tampoco
    with pytest.raises(PermisoDenegado):
        reservas.resolver_cancelacion(m.gb, r["id"], True)              # gerente de otro hotel
    with pytest.raises(ErrorNegocio, match="pendiente de aprobación"):
        reservas.modificar(m.rec, r["id"], notas="x")
    reservas.resolver_cancelacion(m.g1, r["id"], False, "Se mantiene")
    assert db.uno("select estado, cancelacion_estado c from pms_reservas where id=%s", (r["id"],)) == {"estado": "confirmada", "c": "rechazada"}
    reservas.solicitar_cancelacion(m.g1, r["id"], "El gerente 1 la solicita")
    with pytest.raises(PermisoDenegado, match="no puede aprobarla"):
        reservas.resolver_cancelacion(m.g1, r["id"], True)              # quien solicita no aprueba
    reservas.resolver_cancelacion(m.g2, r["id"], True)
    assert db.uno("select estado from pms_reservas where id=%s", (r["id"],))["estado"] == "cancelada"
    assert db.uno("select count(*) n from pms_cargos where reserva_id=%s and not anulado", (r["id"],))["n"] == 0


def test_no_alojado_no_se_cancela_y_no_show(m):
    r = m.reservar(desde=0, noches=2)
    reservas.checkin(m.rec, r["id"])
    with pytest.raises(ErrorNegocio, match="no alojadas"):
        reservas.solicitar_cancelacion(m.rec, r["id"], "x")
    fut = m.reservar(desde=4, noches=1)
    with pytest.raises(ErrorNegocio, match="Aún no llega"):
        reservas.no_show(m.rec, fut["id"])
    reservas.no_show(m.rec, fut["id"], hoy=m.hoy + D(days=4))
    assert db.uno("select estado from pms_reservas where id=%s", (fut["id"],))["estado"] == "no_show"
    assert db.uno("select count(*) n from pms_reserva_noches where reserva_id=%s and activa", (fut["id"],))["n"] == 0


def test_descuentos_requieren_aprobacion_de_otra_persona_de_gerencia(m):
    r = m.reservar(desde=1, noches=2)
    sin = facturacion.resumen(m.rec, r["id"])["total"]
    d = facturacion.solicitar_descuento(m.rec, r["id"], 10, "Cliente frecuente")
    assert facturacion.resumen(m.rec, r["id"])["total"] == sin            # pendiente: no cuenta
    with pytest.raises(PermisoDenegado):
        facturacion.resolver_descuento(m.rec, d, True)
    d2 = facturacion.solicitar_descuento(m.g1, r["id"], 5, "Lo pide gerencia 1")
    with pytest.raises(PermisoDenegado, match="no puede aprobarla"):
        facturacion.resolver_descuento(m.g1, d2, True)
    facturacion.resolver_descuento(m.g2, d, True, "Aprobado")
    facturacion.resolver_descuento(m.g2, d2, False, "No")
    res = facturacion.resumen(m.rec, r["id"])
    assert float(res["subtotal"]) == 180000 and float(res["total"]) == 214200      # 10 % menos, con IVA 19 %
    with pytest.raises(ErrorNegocio, match="ya fue resuelto"):
        facturacion.resolver_descuento(m.g2, d, True)
    assert len(facturacion.descuentos_pendientes(m.A)) == 0


def test_reasignar_habitacion(m):
    r = m.reservar(desde=2, noches=2)
    actual = reservas.noches_de(r["id"])[0]["habitacion_id"]
    otra = m.h202 if actual == m.h201 else m.h201
    reservas.reasignar_habitacion(m.rec, r["id"], otra)
    assert {n["habitacion_id"] for n in reservas.noches_de(r["id"])} == {otra}
    r2 = m.reservar(desde=2, noches=2, adultos=2)          # la otra doble ya quedó libre
    with pytest.raises(ErrorNegocio, match="no está libre"):
        reservas.reasignar_habitacion(m.rec, r2["id"], otra)
    with pytest.raises(ErrorNegocio, match="capacidad"):
        reservas.reasignar_habitacion(m.rec, r2["id"], m.h301)     # individual: capacidad 1, reserva de 2 personas

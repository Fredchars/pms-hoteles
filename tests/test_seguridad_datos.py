import time

import psycopg
import pytest

from pms import config, db, huespedes, reservas, seguridad
from pms.errores import ErrorNegocio, PermisoDenegado
from tests.conftest import D


def test_contrasena_guardada_con_hash_bcrypt(m):
    h = db.uno("select clave_hash from pms_usuarios where email='admin@t.test'")["clave_hash"]
    assert h.startswith("$2") and "clave-admin-1" not in h
    assert seguridad.verificar_clave("clave-admin-1", h) and not seguridad.verificar_clave("otra", h)


def test_inicio_de_sesion_y_bloqueo_por_intentos(m):
    u = seguridad.iniciar_sesion("ADMIN@t.test", "clave-admin-1")
    assert u["rol"] == "administrador" and "clave_hash" not in u
    for _ in range(seguridad.MAX_FALLOS):
        with pytest.raises(ErrorNegocio, match="incorrectos"):
            seguridad.iniciar_sesion("recepcion1.a@t.test", "mala-clave-x")
    with pytest.raises(ErrorNegocio, match="Demasiados intentos"):
        seguridad.iniciar_sesion("recepcion1.a@t.test", "clave-prueba-1")      # ni siquiera la correcta, mientras dure el bloqueo
    assert seguridad.iniciar_sesion("gerencia1.a@t.test", "clave-prueba-1")["rol"] == "gerencia"   # otro usuario no se ve afectado


def test_usuario_inactivo_no_entra(m):
    config.activar_usuario(m.admin, m.rec["id"], False)
    with pytest.raises(ErrorNegocio):
        seguridad.iniciar_sesion(m.rec["email"], "clave-prueba-1")


def test_sesion_persistente_token_firmado(m):
    t = seguridad.token_para(m.rec)
    assert seguridad.validar_token(t)["id"] == m.rec["id"]               # recargar la página = misma sesión
    assert seguridad.validar_token(t + "x") is None and seguridad.validar_token("basura") is None and seguridad.validar_token(None) is None
    vencido = seguridad.emitir_token(m.rec["id"], db.uno("select clave_hash from pms_usuarios where id=%s", (m.rec["id"],))["clave_hash"],
                                     ahora=time.time() - 9 * 3600)
    assert seguridad.validar_token(vencido) is None                      # vence a las 8 horas
    seguridad.cambiar_clave(m.rec, m.rec["id"], "clave-nueva-99")
    assert seguridad.validar_token(t) is None                            # cambiar la clave cierra las sesiones viejas
    config.activar_usuario(m.admin, m.rec["id"], False)
    assert seguridad.validar_token(seguridad.token_para(m.rec)) is None


def test_cambio_de_clave_ajena_solo_administrador(m):
    with pytest.raises(PermisoDenegado):
        seguridad.cambiar_clave(m.rec, m.g1["id"], "clave-nueva-99")
    seguridad.cambiar_clave(m.admin, m.g1["id"], "clave-nueva-99")
    assert seguridad.iniciar_sesion(m.g1["email"], "clave-nueva-99")


def test_modo_demo_apagado_por_defecto_y_forzado_en_produccion(m):
    assert seguridad.demo_permitido({}) is False
    assert seguridad.demo_permitido({"PMS_MODO_DEMO": "no"}) is False
    assert seguridad.demo_permitido({"PMS_MODO_DEMO": "si"}) is True
    assert seguridad.demo_permitido({"PMS_MODO_DEMO": "si", "PMS_ENTORNO": "produccion"}) is False
    with pytest.raises(PermisoDenegado):
        seguridad.entrar_demo(m.rec["id"], {})
    assert seguridad.entrar_demo(m.rec["id"], {"PMS_MODO_DEMO": "si"})["id"] == m.rec["id"]


def test_consentimiento_obligatorio_para_reservar_y_revocable(m):
    sin = m.nuevo_huesped(m.A, consentimiento=False)
    with pytest.raises(ErrorNegocio, match="Ley 1581"):
        m.reservar(desde=2, noches=1, huesped=sin)
    huespedes.registrar_consentimiento(m.rec, sin, "prestacion_servicio")
    c = huespedes.consentimientos(sin)[0]
    assert c["version"] and c["texto"] and c["fecha"] and c["aceptado"] and c["finalidad"] == "prestacion_servicio"
    m.reservar(desde=2, noches=1, huesped=sin)
    huespedes.revocar_consentimiento(m.rec, sin, "prestacion_servicio")
    with pytest.raises(ErrorNegocio, match="Ley 1581"):
        m.reservar(desde=6, noches=1, huesped=sin)
    with pytest.raises(ErrorNegocio, match="reservas vigentes"):
        huespedes.anonimizar(m.g1, sin)


def test_anonimizar_huesped_sin_reservas(m):
    h = m.nuevo_huesped(m.A)
    with pytest.raises(PermisoDenegado):
        huespedes.anonimizar(m.rec, h)
    huespedes.anonimizar(m.g1, h)
    fila = db.uno("select * from pms_huespedes where id=%s", (h,))
    assert fila["anonimizado"] and fila["email"] is None and fila["numero_documento"] is None and fila["nombres"] == "ANONIMIZADO"


def test_auditoria_registra_y_es_inmutable(m):
    r = m.reservar(desde=2, noches=1)
    reservas.solicitar_cancelacion(m.rec, r["id"], "x")
    acciones = [a["accion"] for a in db.todos("select accion from pms_auditoria where entidad='reserva' order by id")]
    assert acciones == ["crear", "solicitar_cancelacion"]
    fila = db.uno("select * from pms_auditoria where accion='crear' and entidad='reserva'")
    assert fila["usuario_email"] == m.rec["email"] and fila["creado"] and fila["despues"]["codigo"].startswith("R")
    with pytest.raises(psycopg.errors.RaiseException, match="solo agregar"):
        with db.tx() as cx:
            cx.execute("update pms_auditoria set accion='borrado' where id=%s", (fila["id"],))
    with pytest.raises(psycopg.errors.RaiseException):
        with db.tx() as cx:
            cx.execute("delete from pms_auditoria")


def test_cambios_de_tarifa_e_impuestos_quedan_auditados_con_valor_anterior(m):
    t = db.uno("select id from pms_tarifas where tipo_id=%s", (m.tipo_doble,))
    from pms import tarifas
    tarifas.actualizar(m.g1, t["id"], precio=111)
    a = db.uno("select antes, despues from pms_auditoria where entidad='tarifa' and accion='actualizar'")
    assert a["antes"]["precio_noche"] == 100000 and a["despues"]["precio_noche"] == 111
    config.guardar_impuesto(m.admin, m.A, "Impuesto genérico", 7)
    a = db.uno("select antes, despues from pms_auditoria where entidad='impuesto' and accion='actualizar'")
    assert a["antes"]["porcentaje"] == 19 and a["despues"]["porcentaje"] == 7


def test_bloqueos_impiden_vender_y_no_pisan_ventas(m):
    from pms import bloqueos
    b = bloqueos.crear(m.g1, m.A, m.h301, m.hoy + D(days=2), m.hoy + D(days=4), "Reparación")
    with pytest.raises(ErrorNegocio, match="No hay disponibilidad"):
        m.reservar(desde=3, noches=1, tipo=m.tipo_ind)            # única individual bloqueada
    m.reservar(desde=6, noches=1, tipo=m.tipo_ind)                # fuera del bloqueo: sí
    with pytest.raises(ErrorNegocio, match="noches vendidas"):
        bloqueos.crear(m.g1, m.A, m.h301, m.hoy + D(days=5), m.hoy + D(days=7), "Otro")
    bloqueos.liberar(m.g1, b)
    m.reservar(desde=3, noches=1, tipo=m.tipo_ind)

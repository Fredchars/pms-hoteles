"""Primer ingreso: contraseña temporal → cada persona crea la suya (bandera debe_cambiar_clave), y bloqueo de toda la aplicación."""
import json
from pathlib import Path

import pytest

from pms import db, seguridad
from pms.errores import ErrorNegocio, PermisoDenegado


def _u(uid):
    return db.uno("select * from pms_usuarios where id=%s", (uid,))


def _acciones(accion):
    return db.todos("select * from pms_auditoria where accion=%s order by id", (accion,))


def test_columna_existe_con_default_false_y_migracion_idempotente(m):
    assert _u(m.rec["id"])["debe_cambiar_clave"] is False
    sql = (Path(__file__).resolve().parent.parent / "db" / "01_esquema_pms.sql").read_text()
    with db.tx() as cx:                       # ejecutarla dos veces más no falla ni cambia datos
        cx.execute(sql)
        cx.execute(sql)
    assert _u(m.rec["id"])["debe_cambiar_clave"] is False


def test_admin_genera_clave_temporal_una_vez_sin_guardarla_en_claro(m):
    antes = _u(m.rec["id"])["clave_hash"]
    t_viejo = seguridad.token_para(m.rec)
    temporal = seguridad.generar_clave_temporal(m.admin, m.rec["id"])
    assert len(temporal) >= 14 and temporal.isascii()
    u = _u(m.rec["id"])
    assert u["debe_cambiar_clave"] is True and u["clave_hash"] != antes
    assert seguridad.verificar_clave(temporal, u["clave_hash"])
    assert seguridad.validar_token(t_viejo) is None                      # sesiones anteriores cerradas
    a = seguridad.iniciar_sesion(m.rec["email"], temporal)
    assert a["debe_cambiar_clave"] is True
    # la clave nunca queda en claro en la base (auditoría incluida)
    volcado = json.dumps(db.todos("select * from pms_auditoria"), default=str) + json.dumps(_u(m.rec["id"]), default=str)
    assert temporal not in volcado
    ev = _acciones("clave_temporal")
    assert len(ev) == 1 and ev[0]["usuario_id"] == m.admin["id"] and ev[0]["entidad_id"] == str(m.rec["id"])


def test_solo_administrador_genera_temporal_y_no_para_si_mismo(m):
    for quien in (m.rec, m.g1, m.hk1):
        with pytest.raises(PermisoDenegado):
            seguridad.generar_clave_temporal(quien, m.rec["id"])
    with pytest.raises(ErrorNegocio):
        seguridad.generar_clave_temporal(m.admin, m.admin["id"])
    with pytest.raises(ErrorNegocio):
        seguridad.generar_clave_temporal(m.admin, 999999)


def test_crear_clave_propia_reglas_y_efectos(m):
    temporal = seguridad.generar_clave_temporal(m.admin, m.rec["id"])
    a = seguridad.iniciar_sesion(m.rec["email"], temporal)
    with pytest.raises(ErrorNegocio, match="al menos 10"):
        seguridad.crear_clave_propia(a, "corta123", "corta123")
    with pytest.raises(ErrorNegocio, match="confirmación"):
        seguridad.crear_clave_propia(a, "una-clave-larga-1", "una-clave-larga-2")
    with pytest.raises(ErrorNegocio, match="temporal"):
        seguridad.crear_clave_propia(a, temporal, temporal)
    assert _u(m.rec["id"])["debe_cambiar_clave"] is True                    # nada cambió con los intentos fallidos
    nuevo = seguridad.crear_clave_propia(a, "mi-clave-propia-1", "mi-clave-propia-1")
    assert nuevo["debe_cambiar_clave"] is False and nuevo["id"] == m.rec["id"]
    u = _u(m.rec["id"])
    assert u["debe_cambiar_clave"] is False and seguridad.verificar_clave("mi-clave-propia-1", u["clave_hash"])
    assert not seguridad.verificar_clave(temporal, u["clave_hash"])
    assert len(_acciones("cambio_clave")) == 1 and len(_acciones("clave_inicial_creada")) == 1
    assert "mi-clave-propia-1" not in json.dumps(db.todos("select * from pms_auditoria"), default=str)
    # la sesión nueva (con la huella nueva) sigue vigente y la vieja no
    assert seguridad.refrescar_actor(nuevo)["debe_cambiar_clave"] is False
    assert seguridad.refrescar_actor(a) is None
    assert seguridad.iniciar_sesion(m.rec["email"], "mi-clave-propia-1")["debe_cambiar_clave"] is False


def test_sesion_recargada_sigue_bloqueada_hasta_crear_la_clave(m):
    seguridad.generar_clave_temporal(m.admin, m.g1["id"])
    u = _u(m.g1["id"])
    token = seguridad.emitir_token(u["id"], u["clave_hash"])
    a = seguridad.validar_token(token)                                     # recargar la página recupera la sesión...
    assert a and a["debe_cambiar_clave"] is True                          # ...y sigue con la bandera
    assert seguridad.refrescar_actor(a)["debe_cambiar_clave"] is True


def test_refrescar_actor_cierra_sesion_si_cambia_clave_o_se_desactiva(m):
    a = seguridad.iniciar_sesion(m.rec["email"], "clave-prueba-1")
    assert seguridad.refrescar_actor(a)["id"] == m.rec["id"]
    seguridad.generar_clave_temporal(m.admin, m.rec["id"])                # cambia la contraseña con la sesión abierta
    assert seguridad.refrescar_actor(a) is None
    b = seguridad.iniciar_sesion(m.g1["email"], "clave-prueba-1")
    from pms import config
    config.activar_usuario(m.admin, m.g1["id"], False)
    assert seguridad.refrescar_actor(b) is None


def test_admin_que_cambia_la_clave_de_otro_lo_obliga_a_crear_la_suya_pero_la_propia_no(m):
    seguridad.cambiar_clave(m.admin, m.rec["id"], "puesta-por-admin-1")
    assert _u(m.rec["id"])["debe_cambiar_clave"] is True
    seguridad.cambiar_clave(m.rec, m.rec["id"], "mi-propia-clave-1")
    assert _u(m.rec["id"])["debe_cambiar_clave"] is False


def test_modo_demo_no_bloquea_con_la_bandera(m, monkeypatch):
    seguridad.generar_clave_temporal(m.admin, m.rec["id"])
    monkeypatch.setenv("PMS_MODO_DEMO", "si")
    assert seguridad.entrar_demo(m.rec["id"])["debe_cambiar_clave"] is False


def test_semilla_marca_a_todos_para_cambiar_clave():
    from pms import semilla
    claves = semilla.sembrar(reiniciar=True, guardar_claves=False)
    assert db.uno("select count(*) n from pms_usuarios where not debe_cambiar_clave")["n"] == 0
    assert db.uno("select count(*) n from pms_usuarios")["n"] == len(claves) == 19

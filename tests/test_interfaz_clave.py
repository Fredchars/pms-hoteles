"""Interfaz (Streamlit AppTest): con la bandera activa solo se ve «Crea tu contraseña nueva»; ninguna otra página es accesible."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from pms import db, seguridad

INICIO = str(Path(__file__).resolve().parent.parent / "app" / "Inicio.py")


def _app(actor=None, token=None):
    at = AppTest.from_file(INICIO, default_timeout=60)
    if actor is not None:
        at.session_state["pms_actor"] = actor
    if token is not None:
        at.query_params["s"] = token
    return at


def _textos(at):
    return " | ".join(x.value for x in at.title) + " | " + " | ".join(x.value for x in at.markdown) + " | " + " | ".join(x.value for x in at.error)


def _sin_navegacion(at):
    # sin navegación: no hay selector de hotel, no hay páginas del PMS (dashboard, reservas...) ni datos
    assert not at.sidebar.selectbox
    assert not at.dataframe and not at.metric
    assert [t.value for t in at.title] == ["🔑 Crea tu contraseña nueva"]


def test_con_bandera_solo_pantalla_de_clave_nueva_y_luego_entra(m):
    temporal = seguridad.generar_clave_temporal(m.admin, m.rec["id"])
    a = seguridad.iniciar_sesion(m.rec["email"], temporal)
    at = _app(a).run()
    assert not at.exception
    _sin_navegacion(at)
    # claves inválidas: se queda en la pantalla con el error en español
    at.text_input(key="pms_cn_1").set_value("corta")
    at.text_input(key="pms_cn_2").set_value("corta")
    at.button[0].click().run()
    assert any("al menos 10" in e.value for e in at.error)
    _sin_navegacion(at)
    at.text_input(key="pms_cn_1").set_value(temporal)
    at.text_input(key="pms_cn_2").set_value(temporal)
    at.button[0].click().run()
    assert any("temporal" in e.value for e in at.error)
    _sin_navegacion(at)
    # clave válida: deja entrar (aparece el selector de hotel / la navegación) sin volver a pedir ingreso
    at.text_input(key="pms_cn_1").set_value("mi-clave-propia-1")
    at.text_input(key="pms_cn_2").set_value("mi-clave-propia-1")
    at.button[0].click().run()
    assert not at.exception
    assert at.session_state["pms_actor"]["debe_cambiar_clave"] is False
    assert not [t for t in at.title if "Crea tu contraseña" in t.value]
    assert at.sidebar.selectbox                                           # ya hay navegación y hotel
    assert db.uno("select debe_cambiar_clave from pms_usuarios where id=%s", (m.rec["id"],))["debe_cambiar_clave"] is False


def test_recargar_la_pagina_mantiene_la_sesion_y_el_bloqueo(m):
    seguridad.generar_clave_temporal(m.admin, m.g1["id"])
    u = db.uno("select * from pms_usuarios where id=%s", (m.g1["id"],))
    token = seguridad.emitir_token(u["id"], u["clave_hash"])
    at = _app(token=token).run()                                          # sesión nueva del navegador (recarga) con el token de la URL
    assert not at.exception
    _sin_navegacion(at)
    assert at.session_state["pms_actor"]["id"] == m.g1["id"]
    assert at.query_params["s"]                                           # el token sigue en la URL


def test_sesion_abierta_se_cierra_si_el_admin_genera_temporal(m):
    a = seguridad.iniciar_sesion(m.rec["email"], "clave-prueba-1")
    at = _app(a).run()
    assert not at.exception and at.sidebar.selectbox                      # sin bandera: navegación normal
    seguridad.generar_clave_temporal(m.admin, m.rec["id"])
    at.run()
    assert "pms_actor" not in at.session_state                            # sesión anterior cerrada
    assert [t.value for t in at.title] == ["🏨 PMS Hotelero · Piloto"]    # vuelve a la pantalla de ingreso


def test_login_con_temporal_lleva_a_la_pantalla_de_clave_nueva(m):
    temporal = seguridad.generar_clave_temporal(m.admin, m.rec["id"])
    at = _app().run()
    at.text_input(key="pms_ingreso_correo").set_value(m.rec["email"])
    at.text_input(key="pms_ingreso_clave").set_value(temporal)
    at.button[0].click().run()
    assert not at.exception
    _sin_navegacion(at)


def test_ninguna_pagina_funciona_con_la_bandera_activa(m):
    """Defensa en profundidad: aunque una página se ejecutara, ui.actor() la detiene si falta crear la contraseña."""
    import sys
    sys.path.insert(0, str(Path(INICIO).parent))
    paginas = sorted((Path(INICIO).parent / "paginas").glob("*.py"))
    assert len(paginas) == 11
    a = dict(m.admin, debe_cambiar_clave=True)
    hotel = db.uno("select * from pms_hoteles where id=%s", (m.A,))
    for p in paginas:
        at = AppTest.from_file(str(p), default_timeout=60)
        at.session_state["pms_actor"] = a
        at.session_state["pms_hotel"] = hotel
        at.session_state["pms_hotel_id"] = m.A
        at.run()
        assert not at.exception, p.name
        assert not at.dataframe and not at.metric and not at.tabs, p.name


def test_configuracion_boton_generar_temporal_muestra_la_clave_una_sola_vez(m):
    import sys
    sys.path.insert(0, str(Path(INICIO).parent))
    hotel = db.uno("select * from pms_hoteles where id=%s", (m.A,))
    at = AppTest.from_file(str(Path(INICIO).parent / "paginas" / "configuracion.py"), default_timeout=60)
    at.session_state["pms_actor"] = m.admin
    at.session_state["pms_hotel"] = hotel
    at.session_state["pms_hotel_id"] = m.A
    at.run()
    assert not at.exception
    botones = [b for b in at.button if b.label == "Generar contraseña temporal"]
    assert len(botones) >= 5 and not at.code                            # uno por usuario (menos el propio) y nada visible aún
    botones[0].click().run()
    assert not at.exception and len(at.code) == 1
    temporal = at.code[0].value
    objetivo = next(u for u in db.todos("select * from pms_usuarios") if seguridad.verificar_clave(temporal, u["clave_hash"]))
    assert objetivo["debe_cambiar_clave"] is True and objetivo["id"] != m.admin["id"]
    at.run()                                                             # cualquier otra interacción: ya no se muestra
    assert not at.code

"""Interfaz (Streamlit AppTest) del Plano de habitaciones: navegación y permisos, filtros, detalle, prellenado de Reservas y sesión."""
import datetime as dt
from pathlib import Path

from streamlit.testing.v1 import AppTest

from pms import db, seguridad

INICIO = str(Path(__file__).resolve().parent.parent / "app" / "Inicio.py")
D = dt.timedelta


def _app(actor):
    at = AppTest.from_file(INICIO, default_timeout=60)
    at.session_state["pms_actor"] = actor
    return at


def _plano(m, actor=None):
    at = _app(seguridad.actor_de(db.uno("select * from pms_usuarios where id=%s", ((actor or m.rec)["id"],)))).run()
    assert not at.exception
    at.switch_page("paginas/plano.py").run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _tarjetas(at):
    return [x.value for x in at.markdown if x.value.startswith('<div class="pms-room ')]


def _num(html):
    return html.split('class="n">')[1].split("<")[0]


def _estado(html):
    return html.split("pms-room-")[1].split('"')[0]


def test_plano_se_ve_con_estados_y_leyenda(m):
    m.reservar(desde=0, noches=2, habitacion_id=m.h201)
    at = _plano(m)
    assert [t.value for t in at.title] == ["🗺️ Plano de habitaciones"]
    assert any("pms-leyenda" in x.value and "Capacidad insuficiente" in x.value for x in at.markdown)
    # planta 2 (la primera): 201 ocupada hoy, 202 disponible
    est = {_num(h): _estado(h) for h in _tarjetas(at)}
    assert est == {"201": "ocupada", "202": "disponible"}
    assert [mm.label for mm in at.metric][:2] == ["Disponibles", "Ocupadas"]
    assert not any(b.key == "pms_pl_b_%d" % m.h201 for b in at.button)           # ocupada: sin botón
    assert any(b.key == "pms_pl_b_%d" % m.h202 for b in at.button)


def test_filtros_planta_tipo_mar_y_ocultar(m):
    m.reservar(desde=0, noches=2, habitacion_id=m.h201)
    at = _plano(m)
    at.toggle(key="pms_pl_ocultar").set_value(True).run()
    assert [_num(h) for h in _tarjetas(at)] == ["202"]
    at.toggle(key="pms_pl_ocultar").set_value(False)
    at.selectbox(key="pms_pl_planta").set_value(3).run()
    assert [_num(h) for h in _tarjetas(at)] == ["301"]
    assert _estado(_tarjetas(at)[0]) == "capacidad"                                # individual con 2 adultos
    at.number_input(key="pms_pl_adultos").set_value(1).run()
    assert _estado(_tarjetas(at)[0]) == "disponible"
    at.toggle(key="pms_pl_mar").set_value(True).run()
    assert _tarjetas(at) == []                                                    # 301 no tiene vista al mar
    at.toggle(key="pms_pl_mar").set_value(False)
    at.selectbox(key="pms_pl_tipo").set_value(m.tipo_doble).run()
    at.selectbox(key="pms_pl_planta").set_value(2).run()
    assert [_num(h) for h in _tarjetas(at)] == ["201", "202"]


def test_elegir_muestra_detalle_y_continuar_prellena_reservas(m):
    at = _plano(m)
    assert any("Elige una habitación" in i.value for i in at.info)
    next(b for b in at.button if b.key == "pms_pl_b_%d" % m.h202).click().run()
    assert not at.exception
    txt = " ".join(x.value for x in at.markdown)
    assert "Habitación 202 · Doble" in txt and "Total estimado" in txt
    assert any(_estado(h) == "seleccionada" for h in _tarjetas(at))
    assert at.dataframe                                                           # desglose por noche
    at.button(key="pms_pl_continuar").click().run()
    assert not at.exception, [e.value for e in at.exception]
    # ahora estamos en Reservas, con todo prellenado y la sesión intacta
    assert [t.value for t in at.title] == ["📝 Reservas"]
    assert at.session_state["pms_actor"]["id"] == m.rec["id"]
    assert at.session_state["pms_rn_tipo"]["id"] == m.tipo_doble
    assert at.session_state["pms_rn_entrada"] == m.hoy and at.session_state["pms_rn_salida"] == m.hoy + D(days=2)
    assert at.session_state["pms_rn_adultos"] == 2 and at.session_state["pms_rn_ninos"] == 0
    assert at.selectbox(key="pms_rn_hab").value == m.h202
    assert "pms_prellenado_reserva" not in at.session_state                      # se consume una sola vez
    assert any("Plano de habitaciones" in i.value and "202" in i.value for i in at.info)


def test_reservas_con_prellenado_guarda_en_la_habitacion_elegida(m):
    """Lo que entrega el plano (clave pms_prellenado_reserva) llega a Reservas y se guarda con esa habitación exacta."""
    from pms import plano
    at = _app(seguridad.actor_de(db.uno("select * from pms_usuarios where id=%s", (m.rec["id"],)))).run()
    at.session_state["pms_prellenado_reserva"] = plano.prellenado(m.rec, m.A, m.h202, m.hoy + D(days=1), m.hoy + D(days=3), 2, 0)
    at.switch_page("paginas/reservas.py").run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.selectbox(key="pms_rn_hab").value == m.h202
    at.text_input(key="pms_rn_buscar").set_value("Ficticia").run()
    at.selectbox(key="pms_rn_huesped").select_index(0).run()
    assert at.selectbox(key="pms_rn_hab").value == m.h202                         # el prellenado sobrevive a otras interacciones
    at.button(key="pms_rn_guardar").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    assert db.uno("select h.numero from pms_reserva_noches n join pms_habitaciones h on h.id=n.habitacion_id where n.activa limit 1")["numero"] == "202"
    assert not any("pms_rn_pre" == k for k in at.session_state)                    # banderas limpias tras guardar


def test_cambiar_hotel_desde_el_plano_sincroniza_la_barra_lateral(m):
    at = _plano(m, m.admin)
    ids = at.selectbox(key="pms_pl_hotel").options
    assert len(ids) == 2
    at.selectbox(key="pms_pl_hotel").set_value(m.B).run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["pms_hotel_id"] == m.B and at.session_state["pms_w_hotel"] == m.B
    assert [_num(h) for h in _tarjetas(at)] == ["B1"]


def test_administrador_solo_lee_y_housekeeping_no_ve_el_plano(m):
    at = _plano(m, m.admin)
    next(b for b in at.button if b.key == "pms_pl_b_%d" % m.h201).click().run()
    assert not at.exception
    assert any("solo puede consultar" in c.value for c in at.caption)
    assert not any(b.key == "pms_pl_continuar" for b in at.button)
    # housekeeping: sin permiso, la página no entra en su navegación (mismos permisos que Calendario)
    assert not seguridad.puede(m.hk1, "plano") and seguridad.puede(m.rec, "plano", True) and seguridad.puede(m.g1, "plano", True)
    assert seguridad.puede(m.admin, "plano") and not seguridad.puede(m.admin, "plano", True)

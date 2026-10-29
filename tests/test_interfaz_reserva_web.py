"""Interfaz (Streamlit AppTest) de la mini web pública de reservas: flujo completo, temporizador, consentimiento, pasarela simulada."""
import datetime as dt
from pathlib import Path

from streamlit.testing.v1 import AppTest

from pms import db, reserva_web as rw

WEB = str(Path(__file__).resolve().parent.parent / "reserva_web" / "Reservas.py")
D = dt.timedelta


def _app(**params):
    at = AppTest.from_file(WEB, default_timeout=60)
    for k, v in params.items():
        at.query_params[k] = v
    return at


def _textos(at):
    return " ".join([x.value for x in at.markdown] + [x.value for x in at.error] + [x.value for x in at.success] +
                    [x.value for x in at.info] + [x.value for x in at.warning] + [x.value for x in at.caption] +
                    [x.value for x in at.subheader] + [x.value for x in at.code])


def _buscar(at, m, hotel=None):
    at.run()
    assert not at.exception
    at.selectbox(key="rw_hotel").set_value(hotel or m.A)
    at.number_input(key="rw_adultos").set_value(2)
    at.date_input(key="rw_entrada").set_value(m.hoy + D(days=6))
    at.date_input(key="rw_salida").set_value(m.hoy + D(days=8))
    [b for b in at.button if b.label == "Ver habitaciones disponibles"][0].click()
    return at.run()


def test_portada_con_aviso_marca_y_sin_datos_internos(m):
    at = _app().run()
    assert not at.exception
    t = _textos(at)
    assert "Prototipo con datos ficticios" in t and "Prototipo diseñado para ATm Consulting" in t and "data:image/png;base64" in t
    assert "Ver habitaciones disponibles" in [b.label for b in at.button]
    assert "Hotel A" in str([o for s in at.selectbox for o in s.options]) or at.selectbox(key="rw_hotel").value in (m.A, m.B)
    assert not at.sidebar.markdown and "pms_actor" not in at.session_state          # nada del PMS interno: sin sesión de personal


def test_busqueda_muestra_tipos_y_plano_publico(m):
    m.reservar(desde=6, noches=2, tipo=m.tipo_ind)
    at = _buscar(_app(), m)
    assert not at.exception, [e.value for e in at.exception]
    t = _textos(at)
    assert "Tipos de habitación" in t and "Plano de habitaciones" in t and "Doble" in t
    assert "201" in t and "301" in t and "No disponible" in t           # la individual está vendida: aparece como no disponible
    assert "Ana" not in t and "Ficticia" not in t                         # ningún dato de huéspedes
    assert [b.label for b in at.button if b.label == "Elegir"]            # hay habitaciones elegibles


def test_flujo_completo_hasta_la_confirmacion(m):
    at = _buscar(_app(), m)
    [b for b in at.button if b.label == "Elegir"][0].click()
    at.run()
    a, c = at.session_state["rw_cap"]
    at.text_input(key="rw_cap_resp").set_value("0")
    at.button(key="rw_bloquear").click()
    at.run()
    assert "verificación no es correcta" in _textos(at) and not at.query_params.get("r")
    at.text_input(key="rw_cap_resp").set_value(str(a + c))
    at.button(key="rw_bloquear").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    numero, token = at.query_params["r"][0] if isinstance(at.query_params["r"], list) else at.query_params["r"], \
        at.query_params["k"][0] if isinstance(at.query_params["k"], list) else at.query_params["k"]
    assert rw.RE_NUMERO.match(numero)
    t = _textos(at)
    assert "Tus datos" in t
    assert db.uno("select estado, canal from pms_reservas where referencia_externa=%s", (numero,)) == {"estado": "opcion", "canal": "web"}
    # sin consentimiento no avanza
    at.text_input(key="rw_nombres").set_value("Camila")
    at.text_input(key="rw_apellidos").set_value("Prueba")
    at.text_input(key="rw_email").set_value("camila@prueba-web.invalid")
    [b for b in at.button if b.label == "Continuar al pago"][0].click()
    at.run()
    assert "Ley 1581" in " ".join(e.value for e in at.error)
    at.checkbox(key="rw_acepta").set_value(True)
    [b for b in at.button if b.label == "Continuar al pago"][0].click()
    at.run()
    assert not at.exception and [b for b in at.button if b.label.startswith("Pagar ")]
    at.button(key="rw_pagar").click()
    at.run()
    t = _textos(at)
    assert "MODO PRUEBAS: no se cobra dinero" in t and "Pasarela de pagos (simulada)" in t
    assert not at.text_input or all("tarjeta" not in (x.label or "").lower() for x in at.text_input)   # no se piden datos de tarjeta
    at.button(key="rw_sim_ok").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    t = _textos(at)
    assert "Reserva confirmada" in t and numero in t and "Correo simulado: no se envió" in t
    assert rw.consultar(numero, token)["estado"] == "confirmada"


def test_pago_rechazado_permite_reintentar_y_la_consulta_por_enlace_funciona(m):
    b = rw.crear_bloqueo(m.A, m.tipo_doble, m.hoy + D(days=6), m.hoy + D(days=8), 2, 0)
    rw.completar_datos(b["numero"], b["token"], "Camila", "Prueba", "camila@prueba-web.invalid", acepta_tratamiento=True)
    at = _app(r=b["numero"], k=b["token"], pago="1").run()
    assert "MODO PRUEBAS" in _textos(at)
    at.button(key="rw_sim_no").click()
    at.run()
    assert "rechazado" in _textos(at) and [x for x in at.button if x.label.startswith("Pagar ")]
    assert rw.consultar(b["numero"], b["token"])["estado"] == "fallida"


def test_enlace_con_token_incorrecto_no_muestra_la_reserva(m):
    b = rw.crear_bloqueo(m.A, m.tipo_doble, m.hoy + D(days=6), m.hoy + D(days=8), 2, 0)
    at = _app(r=b["numero"], k="incorrecto").run()
    t = _textos(at)
    assert "No encontramos esa reserva" in t and b["numero"] not in t and not at.exception


def test_bloqueo_vencido_muestra_mensaje_y_vuelve_a_buscar(m):
    b = rw.crear_bloqueo(m.A, m.tipo_doble, m.hoy + D(days=6), m.hoy + D(days=8), 2, 0)
    with db.tx() as cx:
        cx.execute("update pms_reservas set opcion_vence_en = now() - interval '1 second' where referencia_externa=%s", (b["numero"],))
    at = _app(r=b["numero"], k=b["token"]).run()
    assert "venció" in _textos(at) and not at.exception
    [x for x in at.button if x.label == "Buscar otra habitación"][0].click()
    at.run()
    assert "Ver habitaciones disponibles" in [x.label for x in at.button]


def test_validaciones_de_fechas_en_la_interfaz(m):
    at = _app().run()
    at.date_input(key="rw_entrada").set_value(m.hoy + D(days=8))
    at.date_input(key="rw_salida").set_value(m.hoy + D(days=8))
    [b for b in at.button if b.label == "Ver habitaciones disponibles"][0].click()
    at.run()
    assert "posterior" in " ".join(e.value for e in at.error) and not at.exception


# ---------- el PMS interno ve las reservas web ----------
def _pms(m, pagina, actor=None):
    from pms import seguridad
    inicio = str(Path(__file__).resolve().parent.parent / "app" / "Inicio.py")
    at = AppTest.from_file(inicio, default_timeout=60)
    at.session_state["pms_actor"] = seguridad.actor_de(db.uno("select * from pms_usuarios where id=%s", ((actor or m.rec)["id"],)))
    at.run()
    assert not at.exception
    at.switch_page(pagina).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_pms_muestra_reservas_web_con_pago_y_correo(m):
    b = rw.crear_bloqueo(m.A, m.tipo_doble, m.hoy + D(days=6), m.hoy + D(days=8), 2, 0)
    rw.completar_datos(b["numero"], b["token"], "Camila", "Prueba", "camila@prueba-web.invalid", acepta_tratamiento=True)
    from pms import pasarela
    p = rw.iniciar_pago(b["numero"], b["token"])
    ev, firma = pasarela.PasarelaSimulada().evento(p["referencia"], p["monto"], p["moneda"], True)
    rw.procesar_evento(ev, firma)
    at = _pms(m, "paginas/reservas_web.py")
    assert [t.value for t in at.title] == ["🌐 Reservas web"]
    fila = at.dataframe[0].value.iloc[0]
    assert fila["Número"] == b["numero"] and fila["Estado web"] == "Reserva confirmada" and fila["Pago"] == "Aprobada"
    assert fila["Correo"].startswith("Simulado") and fila["Referencia"] == p["referencia"]
    # y aparece en la lista normal de Reservas con canal web
    at = _pms(m, "paginas/reservas.py")
    assert "web" in set(at.dataframe[0].value["Canal"])


def test_pms_liberar_vencidas_desde_la_pantalla(m):
    b = rw.crear_bloqueo(m.A, m.tipo_doble, m.hoy + D(days=6), m.hoy + D(days=8), 2, 0)
    with db.tx() as cx:
        cx.execute("update pms_reservas set opcion_vence_en = now() - interval '1 second' where referencia_externa=%s", (b["numero"],))
    at = _pms(m, "paginas/reservas_web.py")
    at.button(key="pms_rw_liberar").click().run()
    assert not at.exception and "Se liberaron 1 reserva" in " ".join(x.value for x in at.success)
    assert db.uno("select estado from pms_reservas_web where numero_publico=%s", (b["numero"],))["estado"] == "expirada"

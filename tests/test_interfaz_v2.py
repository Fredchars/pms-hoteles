"""Suite v2 (pms_v2/Inicio.py): ingreso, primer ingreso, barra lateral por categorías y pantallas reutilizadas sobre la misma base."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from pms import db, seguridad

INICIO = str(Path(__file__).resolve().parent.parent / "pms_v2" / "Inicio.py")


def _app(actor=None):
    at = AppTest.from_file(INICIO, default_timeout=60)
    if actor:
        at.session_state["pms_actor"] = actor
    return at.run()


def _actor(u):
    return seguridad.actor_de(db.uno("select * from pms_usuarios where id=%s", (u["id"],)))


def test_ingreso_v2_muestra_formulario():
    at = _app()
    assert not at.exception
    assert at.title[0].value == "🏨 PMS Hotelero · Suite v2"


def test_v2_paginas_y_fase_siguiente(m):
    at = _app(_actor(m.rec))
    assert not at.exception, [e.value for e in at.exception]
    for pag in ("paginas/plano.py", "paginas/reservas.py", "paginas/calendario.py", "paginas/promos.py", "paginas/crm.py", "paginas/integraciones.py"):
        at.switch_page(pag).run()
        assert not at.exception, (pag, [e.value for e in at.exception])
    assert any("Fase siguiente" in x.value for x in at.markdown)


def test_v2_primer_ingreso_exige_clave(m):
    with db.tx() as c:
        c.execute("update pms_usuarios set debe_cambiar_clave=true where id=%s", (m.rec["id"],))
    at = _app(_actor(m.rec))
    assert not at.exception
    assert at.title[0].value == "🔑 Crea tu contraseña nueva"

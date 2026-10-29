"""Regresión del fallo en producción «No se pudo conectar con la base de datos (AttributeError)»: Streamlit Cloud actualiza el código
sin reiniciar el proceso y deja en memoria la versión vieja de pms/*.py; además los errores no-conexión ya no se disfrazan de conexión."""
import sys
from pathlib import Path

import psycopg
from streamlit.testing.v1 import AppTest

from pms import db, seguridad

APP = Path(__file__).resolve().parent.parent / "app"
INICIO = str(APP / "Inicio.py")


def test_clasificacion_de_errores_de_conexion():
    assert db.es_error_de_conexion(psycopg.OperationalError("no route"))
    assert db.es_error_de_conexion(RuntimeError("Falta DATABASE_URL (variable de entorno o secreto)."))
    assert not db.es_error_de_conexion(AttributeError("x"))
    assert not db.es_error_de_conexion(RuntimeError("otra cosa"))
    assert not db.es_error_de_conexion(KeyError("huella"))


def test_error_no_de_conexion_muestra_error_inesperado_y_traceback_en_stderr(capsys):
    at = AppTest.from_string(
        "import sys\nsys.path.insert(0, %r)\nimport ui\n"
        "try:\n    {}['x'].nada\nexcept Exception as e:\n    ui.mostrar_error(e, 'prueba')\n" % str(APP))
    at.run()
    assert [e.value for e in at.error] == ["Error inesperado (KeyError). Ya quedó registrado; si continúa, avisa a soporte."]
    err = capsys.readouterr().err
    assert "Traceback" in err and "KeyError" in err and "prueba" in err


def test_error_de_conexion_conserva_el_mensaje_de_conexion_sin_detalles(capsys):
    at = AppTest.from_string(
        "import sys\nsys.path.insert(0, %r)\nimport ui, psycopg\n"
        "ui.mostrar_error(psycopg.OperationalError('host=secreto.supabase.co password=NO'), 'prueba')\n" % str(APP))
    at.run()
    assert at.error[0].value.startswith("No se pudo conectar con la base de datos (OperationalError)")
    assert "secreto.supabase" not in at.error[0].value and "password" not in capsys.readouterr().err


CHILD = r"""
import json, sys
sys.path.insert(0, %(raiz)r)
from streamlit.testing.v1 import AppTest
from pms import seguridad
a = seguridad.iniciar_sesion(%(email)r, %(clave)r)
at = AppTest.from_file(%(inicio)r, default_timeout=60)
at.session_state["pms_actor"] = a
at.run()
assert not at.exception and at.sidebar.selectbox, "carga inicial"
viejo = sys.modules["pms.seguridad"]
del viejo.refrescar_actor            # módulo viejo en memoria (sin la función nueva), como tras un push en Streamlit Cloud
sys._pms_marca = 12345               # la marca de archivos ya no coincide (hubo un git pull)
at.run()
assert not at.exception, [str(e) for e in at.exception]
assert not [e.value for e in at.error], [e.value for e in at.error]     # antes del arreglo: «No se pudo conectar... (AttributeError)»
assert at.sidebar.selectbox, "la sesión siguió y la app cargó"
assert hasattr(sys.modules["pms.seguridad"], "refrescar_actor") and sys.modules["pms.seguridad"] is not viejo
print("OK")
"""


def test_modulos_viejos_en_memoria_se_recargan_al_cambiar_el_codigo(m):
    """Simula Streamlit Cloud tras un push: el proceso sigue vivo con un pms.seguridad VIEJO (sin refrescar_actor).
    Corre en un proceso aparte para no alterar los módulos de esta sesión de pruebas."""
    import os
    import subprocess
    raiz = str(APP.parent)
    r = subprocess.run([sys.executable, "-c", CHILD % {"raiz": raiz, "email": m.rec["email"], "clave": "clave-prueba-1", "inicio": INICIO}],
                       capture_output=True, text=True, env=dict(os.environ), timeout=120)
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout[-500:] + r.stderr[-1500:]

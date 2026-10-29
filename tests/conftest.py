"""Pruebas contra un PostgreSQL REAL (local o el servicio de GitHub Actions). Por seguridad se niegan a correr contra
cualquier servidor que no sea local: borran los datos de las tablas pms_ entre pruebas."""
import datetime as dt
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
URL = os.environ.get("PMS_TEST_PG_URL", "postgresql://postgres@127.0.0.1:55432/pms_test")
if not any(h in URL for h in ("@127.0.0.1", "@localhost", "@postgres:", "@127.0.0.1:")):
    raise SystemExit("Las pruebas solo corren contra un PostgreSQL local (PMS_TEST_PG_URL).")
os.environ["DATABASE_URL"] = URL
for v in ("PMS_MODO_DEMO", "PMS_ENTORNO", "PMS_SESION_SECRETO"):
    os.environ.pop(v, None)

import pytest  # noqa: E402

# Las pruebas de interfaz ejecutan app/Inicio.py en este mismo proceso: se marca el código de pms/ como «ya cargado» para que la
# recarga de módulos de Streamlit Cloud (Inicio._modulos_al_dia) no descarte los módulos que usan las demás pruebas.
sys._pms_marca = max(f.stat().st_mtime_ns for f in (RAIZ / "pms").glob("*.py"))

from pms import config, db, huespedes, semilla  # noqa: E402
from pms.seguridad import actor_de, hash_clave  # noqa: E402
from pms.util import hoy_hotel  # noqa: E402

D = dt.timedelta


@pytest.fixture(scope="session", autouse=True)
def esquema():
    with db.tx() as cx:
        cx.execute((RAIZ / "db" / "01_esquema_pms.sql").read_text())
        cx.execute((RAIZ / "db" / "02_rls_pms.sql").read_text())
    yield
    db.cerrar_pool()


@pytest.fixture(autouse=True)
def limpio(esquema):
    with db.tx() as cx:
        cx.execute("truncate " + ", ".join(semilla.TABLAS) + " restart identity cascade")
    yield


class Mundo:
    """Dos hoteles: A (COP, un impuesto 19 %) con 2 dobles y 1 individual; B (DOP, impuestos 18 % y 10 %) con 1 doble."""

    def __init__(self):
        with db.tx() as cx:
            u = cx.execute("insert into pms_usuarios (hotel_id,email,nombre,rol,clave_hash) values (null,'admin@t.test','Admin','administrador',%s) returning *",
                           (hash_clave("clave-admin-1"),)).fetchone()
        self.admin = actor_de(u)
        self.A = config.crear_hotel(self.admin, "Hotel A", "Colombia", "COP", "America/Bogota")
        self.B = config.crear_hotel(self.admin, "Hotel B", "República Dominicana", "DOP", "America/Santo_Domingo")
        config.guardar_impuesto(self.admin, self.A, "Impuesto genérico", 19)
        config.guardar_impuesto(self.admin, self.B, "Impuesto 1", 18)
        config.guardar_impuesto(self.admin, self.B, "Servicio", 10)
        self.hoy = hoy_hotel(None, self.A)
        self.tipo_doble = config.crear_tipo(self.admin, self.A, "Doble", 2)
        self.tipo_ind = config.crear_tipo(self.admin, self.A, "Individual", 1)
        self.tipo_b = config.crear_tipo(self.admin, self.B, "Doble", 2)
        self.h201 = config.crear_habitacion(self.admin, self.A, "201", 2, self.tipo_doble, 22, "Mar", [("matrimonial", 150, 1)])
        self.h202 = config.crear_habitacion(self.admin, self.A, "202", 2, self.tipo_doble, 22, "Mar", [("matrimonial", 150, 1)])
        self.h301 = config.crear_habitacion(self.admin, self.A, "301", 3, self.tipo_ind, 14, "Interior", [("individual", 90, 1)])
        self.hb1 = config.crear_habitacion(self.admin, self.B, "B1", 1, self.tipo_b, 22, "Mar")
        from pms import tarifas
        for hid, tipo, precio in [(self.A, self.tipo_doble, 100000), (self.A, self.tipo_ind, 60000), (self.B, self.tipo_b, 5000)]:
            tarifas.crear(self.admin, hid, tipo, "Base", self.hoy - D(days=400), self.hoy + D(days=400), precio)
        self.u = {}
        for hid, s in ((self.A, "a"), (self.B, "b")):
            for rol, n in (("gerencia", 1), ("gerencia", 2), ("recepcion", 1), ("housekeeping", 1), ("housekeeping", 2)):
                email = f"{rol}{n}.{s}@t.test"
                uid = config.crear_usuario(self.admin, email, f"{rol} {n}", rol, "clave-prueba-1", hid)
                self.u[f"{rol}{n}{s}"] = {"id": uid, "email": email, "nombre": email, "rol": rol, "hotel_id": hid}
        self.g1, self.g2, self.rec = self.u["gerencia1a"], self.u["gerencia2a"], self.u["recepcion1a"]
        self.hk1, self.hk2 = self.u["housekeeping1a"], self.u["housekeeping2a"]
        self.gb, self.recb = self.u["gerencia1b"], self.u["recepcion1b"]
        self.huesped = self.nuevo_huesped(self.A)
        self.huesped_b = self.nuevo_huesped(self.B)

    def nuevo_huesped(self, hid, consentimiento=True):
        actor = self.rec if hid == self.A else self.recb
        g = huespedes.crear(actor, hid, "Ana", "Ficticia", "DOC", f"F-{hid}-{os_rand()}", "ana@ejemplo.invalid")
        if consentimiento:
            huespedes.registrar_consentimiento(actor, g, "prestacion_servicio")
        return g

    def reservar(self, desde=1, noches=2, tipo=None, actor=None, **kw):
        from pms import reservas
        return reservas.crear(actor or self.rec, self.A, kw.pop("huesped", self.huesped), tipo or self.tipo_doble,
                              self.hoy + D(days=desde), self.hoy + D(days=desde + noches), **kw)

    def lista(self, *ids):
        with db.tx() as cx:
            cx.execute("update pms_habitaciones set estado_limpieza='lista' where id = any(%s)", (list(ids),))


def os_rand():
    import random
    return random.randint(0, 10**9)


@pytest.fixture
def m():
    return Mundo()

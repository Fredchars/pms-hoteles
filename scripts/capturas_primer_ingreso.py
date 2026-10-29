"""Capturas para la documentación del primer ingreso, con una base LOCAL de pruebas (nunca producción) y datos ficticios.

Uso:  PMS_CAPT_PG_URL=postgresql://postgres@127.0.0.1:55432/pms_capturas python scripts/capturas_primer_ingreso.py
Crea la base local (esquema + datos ficticios; todos los usuarios quedan obligados a crear su contraseña), arranca la app y toma:
  docs/capturas/00_ingreso.png            pantalla de ingreso
  docs/capturas/clave_nueva.png           «Crea tu contraseña nueva» (formulario vacío)
  docs/capturas/clave_nueva_error.png     la misma pantalla con el aviso de contraseña corta
  docs/capturas/admin_clave_temporal.png  Configuración → Usuarios → «Generar contraseña temporal» (sin generar ninguna)
Las contraseñas de esta base local son aleatorias, no se imprimen y no aparecen en ninguna captura."""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import psycopg
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
SALIDA = RAIZ / "docs" / "capturas"
PUERTO = os.environ.get("PMS_PUERTO", "8598")
URL = f"http://localhost:{PUERTO}"
LOCAL = os.environ.get("PMS_CAPT_PG_URL", "postgresql://postgres@127.0.0.1:55432/pms_capturas")
if not any(h in LOCAL for h in ("@127.0.0.1", "@localhost")):
    raise SystemExit("Solo se permite una base local de pruebas.")


def preparar_base() -> dict:
    admin_url = LOCAL.rsplit("/", 1)[0] + "/postgres"
    nombre = LOCAL.rsplit("/", 1)[1]
    with psycopg.connect(admin_url, autocommit=True) as cx:
        cx.execute(f'drop database if exists "{nombre}" with (force)')
        cx.execute(f'create database "{nombre}"')
    os.environ["DATABASE_URL"] = LOCAL
    os.environ.pop("PMS_SEED_CLAVES", None)
    from pms import db, semilla
    with db.tx() as cx:
        cx.execute((RAIZ / "db" / "01_esquema_pms.sql").read_text())
        cx.execute((RAIZ / "db" / "02_rls_pms.sql").read_text())
    claves = semilla.sembrar(reiniciar=False, guardar_claves=False)
    with db.tx() as cx:       # el administrador entra normal para mostrar Configuración; los demás siguen obligados a crear su clave
        cx.execute("update pms_usuarios set debe_cambiar_clave=false where email='admin@pms-demo.test'")
    db.cerrar_pool()
    return claves


def esperar_app(proc):
    for _ in range(60):
        if proc.poll() is not None:
            raise SystemExit("La app se cerró al arrancar")
        try:
            urllib.request.urlopen(f"{URL}/_stcore/health", timeout=2)
            return
        except Exception:
            time.sleep(1)
    raise SystemExit("La app no arrancó a tiempo")


def entrar(pg, email, clave):
    pg.goto(URL)
    pg.wait_for_selector("input[aria-label='Correo']", timeout=30000)
    pg.fill("input[aria-label='Correo']", email)
    pg.fill("input[aria-label='Contraseña']", clave)
    pg.get_by_role("button", name="Entrar").click()


def main():
    claves = preparar_base()
    env = {**os.environ, "DATABASE_URL": LOCAL, "PMS_SESION_SECRETO": "prueba-local", "PMS_MODO_DEMO": "no", "PMS_ENTORNO": "produccion"}
    log = open("/tmp/pms_capt_app.log", "w")
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app/Inicio.py", "--server.port", PUERTO, "--server.headless", "true"],
                            cwd=RAIZ, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        esperar_app(proc)
        with sync_playwright() as p:
            nav = p.chromium.launch()
            # 1) pantalla de ingreso
            pg = nav.new_context(viewport={"width": 1440, "height": 720}, locale="es-CO").new_page()
            pg.goto(URL)
            pg.wait_for_selector("input[aria-label='Correo']", timeout=30000)
            pg.wait_for_timeout(1000)
            pg.screenshot(path=str(SALIDA / "00_ingreso.png"))
            # 2) primer ingreso con contraseña temporal → solo «Crea tu contraseña nueva»
            ctx = nav.new_context(viewport={"width": 1440, "height": 720}, locale="es-CO")
            pg = ctx.new_page()
            entrar(pg, "recepcion1.col@pms-demo.test", claves["recepcion1.col@pms-demo.test"])
            pg.get_by_role("heading", name="Crea tu contraseña nueva").wait_for(timeout=30000)
            assert pg.locator("[data-testid='stSidebarNavLink']").count() == 0, "hay navegación antes de crear la clave"
            pg.wait_for_timeout(800)
            pg.screenshot(path=str(SALIDA / "clave_nueva.png"))
            # recargar: sigue la misma pantalla
            pg.reload()
            pg.get_by_role("heading", name="Crea tu contraseña nueva").wait_for(timeout=30000)
            print("recarga: sigue en «Crea tu contraseña nueva»")
            # 3) contraseña corta → aviso en rojo (los campos se ven con puntos, sin texto legible)
            pg.fill("input[aria-label='Contraseña nueva']", "corta1")
            pg.fill("input[aria-label='Confirma la contraseña nueva']", "corta1")
            pg.get_by_role("button", name="Guardar y entrar").click()
            pg.get_by_text("al menos 10 caracteres").first.wait_for(timeout=20000)
            pg.wait_for_timeout(500)
            pg.screenshot(path=str(SALIDA / "clave_nueva_error.png"))
            ctx.close()
            # 4) administrador: Configuración → Usuarios → Generar contraseña temporal (sin generar)
            ctx = nav.new_context(viewport={"width": 1440, "height": 1300}, locale="es-CO")
            pg = ctx.new_page()
            entrar(pg, "admin@pms-demo.test", claves["admin@pms-demo.test"])
            pg.wait_for_selector("[data-testid='stSidebarNavLink']", timeout=30000)
            pg.locator("[data-testid='stSidebarNavLink']", has_text="Configuración").first.click()
            pg.get_by_role("tab", name="👤 Usuarios").click()
            pg.get_by_text("Generar contraseña temporal").first.click()
            pg.wait_for_timeout(1500)
            assert pg.locator("[data-testid='stCode']").count() == 0
            pg.screenshot(path=str(SALIDA / "admin_clave_temporal.png"), full_page=True)
            ctx.close()
            nav.close()
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:
            proc.kill()
    print("Capturas OK")


if __name__ == "__main__":
    main()

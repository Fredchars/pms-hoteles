"""Arranca la app en local, entra con cada rol y toma capturas de las pantallas (Playwright + Chromium).

Uso:  DATABASE_URL=... PMS_CLAVES=/ruta/claves.txt python scripts/capturas.py [carpeta_salida]
Comprueba además que el fondo de la página sea blanco. Las contraseñas no se imprimen.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "docs" / "capturas"
PUERTO = os.environ.get("PMS_PUERTO", "8599")
URL = f"http://localhost:{PUERTO}"
CLAVES = {}
for linea in Path(os.environ["PMS_CLAVES"]).read_text().splitlines():
    if "\t" in linea and not linea.startswith("#"):
        e, c = linea.split("\t", 1)
        CLAVES[e.strip()] = c.strip()

RECORRIDO = [  # (correo, [(titulo del menú, nombre de archivo)])
    ("gerencia1.col@pms-demo.test", [("Dashboard del día", "dashboard"), ("Calendario", "calendario"), ("Reservas", "reservas"),
                                     ("Huéspedes", "huespedes"), ("Housekeeping", "housekeeping"), ("Bloqueos", "bloqueos"),
                                     ("Tarifas", "tarifas"), ("Facturación", "facturacion"), ("Reportes", "reportes"),
                                     ("Configuración", "configuracion"), ("Auditoría", "auditoria")]),
    ("recepcion1.col@pms-demo.test", [("Dashboard del día", "recepcion_dashboard"), ("Reservas", "recepcion_reservas")]),
    ("housekeeping1.rd@pms-demo.test", [("Housekeeping", "housekeeping_rol")]),
    ("admin@pms-demo.test", [("Configuración", "admin_configuracion")]),
]


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


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PMS_SESION_SECRETO": "prueba-local", "PMS_MODO_DEMO": os.environ.get("PMS_MODO_DEMO", "no")}
    log = open("/tmp/pms_app.log", "w")
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app/Inicio.py", "--server.port", PUERTO, "--server.headless", "true"],
                            cwd=RAIZ, env=env, stdout=log, stderr=subprocess.STDOUT)
    fallos = []
    try:
        esperar_app(proc)
        with sync_playwright() as p:
            nav = p.chromium.launch()
            for email, paginas in RECORRIDO:
                ctx = nav.new_context(viewport={"width": 1440, "height": 1200}, locale="es-CO")
                pg = ctx.new_page()
                pg.goto(URL)
                pg.wait_for_selector("input[aria-label='Correo']", timeout=30000)
                if email == RECORRIDO[0][0]:
                    pg.screenshot(path=str(SALIDA / "00_ingreso.png"))
                    fondo = pg.evaluate("getComputedStyle(document.querySelector('.stApp')).backgroundColor")
                    print("Fondo de la app:", fondo)
                    if fondo.replace(" ", "") not in ("rgb(255,255,255)", "rgba(255,255,255,1)"):
                        fallos.append(f"fondo no blanco: {fondo}")
                pg.fill("input[aria-label='Correo']", email)
                pg.fill("input[aria-label='Contraseña']", CLAVES[email])
                pg.get_by_role("button", name="Entrar").click()
                pg.wait_for_selector("[data-testid='stSidebarNavLink']", timeout=30000)
                for titulo, archivo in paginas:
                    pg.locator("[data-testid='stSidebarNavLink']", has_text=titulo).first.click()
                    pg.wait_for_timeout(2500)
                    pg.wait_for_selector("h1", timeout=20000)
                    errores = pg.locator("[data-testid='stException']").count()
                    if errores:
                        detalle = pg.locator("[data-testid='stException']").first.inner_text()[:400].replace("\n", " | ")
                        fallos.append(f"{email} / {titulo}: excepción en pantalla: {detalle}")
                    pg.screenshot(path=str(SALIDA / f"{archivo}.png"), full_page=True)
                    print("captura", archivo, "errores:", errores)
                # recargar la página no debe cerrar la sesión
                pg.reload()
                pg.wait_for_selector("[data-testid='stSidebarNavLink']", timeout=30000)
                print("sesión tras recargar: OK")
                ctx.close()
            nav.close()
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:
            proc.kill()
    if fallos:
        print("FALLOS:", *fallos, sep="\n - ")
        raise SystemExit(1)
    print("Capturas OK")


if __name__ == "__main__":
    main()

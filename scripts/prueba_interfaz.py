"""Prueba de humo de la interfaz con Playwright: recorre flujos reales (reserva nueva, check-in, housekeeping, aprobaciones).

Uso:  DATABASE_URL=... PMS_CLAVES=/ruta/claves.txt python scripts/prueba_interfaz.py [carpeta_salida]
Necesita la base con la semilla cargada. No imprime contraseñas.
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
PUERTO = os.environ.get("PMS_PUERTO", "8598")
URL = f"http://localhost:{PUERTO}"
CLAVES = {}
for linea in Path(os.environ["PMS_CLAVES"]).read_text().splitlines():
    if "\t" in linea and not linea.startswith("#"):
        e, c = linea.split("\t", 1)
        CLAVES[e.strip()] = c.strip()


def entrar(nav, email):
    ctx = nav.new_context(viewport={"width": 1440, "height": 1300}, locale="es-CO")
    pg = ctx.new_page()
    pg.goto(URL)
    pg.wait_for_selector("input[aria-label='Correo']", timeout=30000)
    pg.fill("input[aria-label='Correo']", email)
    pg.fill("input[aria-label='Contraseña']", CLAVES[email])
    pg.get_by_role("button", name="Entrar").click()
    pg.wait_for_selector("[data-testid='stSidebarNavLink']", timeout=30000)
    return ctx, pg


def ir(pg, titulo):
    pg.locator("[data-testid='stSidebarNavLink']", has_text=titulo).first.click()
    pg.wait_for_selector("h1", timeout=20000)
    pg.wait_for_timeout(2000)


def elegir(pg, etiqueta, indice=0):
    """Abre un selectbox por su etiqueta y elige la opción número `indice`."""
    caja = pg.locator("[data-testid='stSelectbox']", has_text=etiqueta).first
    caja.click()
    pg.wait_for_timeout(500)
    pg.locator("[role='option']").nth(indice).click()
    pg.wait_for_timeout(1200)


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PMS_SESION_SECRETO": "prueba-local", "PMS_MODO_DEMO": "no"}
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app/Inicio.py", "--server.port", PUERTO, "--server.headless", "true"],
                            cwd=RAIZ, env=env, stdout=open("/tmp/pms_app2.log", "w"), stderr=subprocess.STDOUT)
    resultados = []
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"{URL}/_stcore/health", timeout=2)
                break
            except Exception:
                time.sleep(1)
        with sync_playwright() as p:
            nav = p.chromium.launch()

            # 1) Reserva nueva (gerencia)
            ctx, pg = entrar(nav, "gerencia1.col@pms-demo.test")
            ir(pg, "Reservas")
            pg.get_by_role("tab", name="Nueva reserva").click()
            pg.wait_for_timeout(1000)
            creada = False
            elegir(pg, "Tipo de habitación", 2)          # Doble matrimonial (el tipo con más habitaciones)
            for i in range(6):
                elegir(pg, "Huésped", i)
                pg.get_by_role("button", name="Guardar reserva").click()
                pg.wait_for_timeout(2500)
                if pg.get_by_text("Reserva creada").count():
                    creada = True
                    break
            pg.screenshot(path=str(SALIDA / "flujo_nueva_reserva.png"))
            resultados.append(("Crear reserva desde la pantalla", creada))
            pg.get_by_role("tab", name="Gestionar una reserva").click()
            pg.wait_for_timeout(1500)
            pg.screenshot(path=str(SALIDA / "flujo_gestionar_reserva.png"))
            resultados.append(("Pantalla Gestionar muestra acciones", pg.get_by_text("Acciones").count() > 0))
            ctx.close()

            # 2) Housekeeping: avanzar una habitación sucia (camarera)
            ctx, pg = entrar(nav, "housekeeping1.col@pms-demo.test")
            ir(pg, "Housekeeping")
            btn = pg.get_by_role("button", name="Empezar limpieza")
            hay = btn.count() > 0
            if hay:
                btn.first.click()
                pg.wait_for_timeout(2500)
            pg.screenshot(path=str(SALIDA / "flujo_housekeeping.png"))
            resultados.append(("Housekeeping avanza una habitación", hay and pg.get_by_text("En limpieza").count() > 0))
            resultados.append(("Housekeeping no ve precios", pg.get_by_text("COP").count() == 0))
            ctx.close()

            # 3) Aprobación de cancelación por la otra gerencia
            ctx, pg = entrar(nav, "gerencia2.col@pms-demo.test")
            ir(pg, "Reservas")
            pg.get_by_role("tab", name="Cancelaciones pendientes").click()
            pg.wait_for_timeout(1200)
            pg.screenshot(path=str(SALIDA / "flujo_aprobaciones.png"))
            resultados.append(("Gerencia ve cancelaciones pendientes", pg.get_by_text("Aprobar cancelación").count() + pg.get_by_text("debe aprobarla otra persona").count() > 0))
            ctx.close()

            # 4) Recepción no ve Reportes ni Configuración ni Auditoría
            ctx, pg = entrar(nav, "recepcion1.col@pms-demo.test")
            menu = pg.locator("[data-testid='stSidebarNavLink']").all_inner_texts()
            resultados.append(("Recepción sin Reportes/Configuración/Auditoría", not any(x in " ".join(menu) for x in ("Reportes", "Configuración", "Auditoría"))))
            ctx.close()
            nav.close()
    finally:
        proc.terminate()
    ok = True
    for nombre, v in resultados:
        print("OK  " if v else "FALLA", nombre)
        ok &= bool(v)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()

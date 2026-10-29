"""Capturas del Plano de habitaciones con una base LOCAL de pruebas (nunca producción) y datos ficticios.

Uso:  PMS_CAPT_PG_URL=postgresql://postgres@127.0.0.1:55432/pms_capturas python scripts/capturas_plano.py
Genera: docs/capturas/plano.png (plano de una planta, filtros y leyenda), plano_detalle.png (habitación elegida con desglose de precio),
plano_reserva.png (Reservas con los datos prellenados desde el plano). Ninguna captura muestra contraseñas."""
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))
import capturas_primer_ingreso as base  # noqa: E402  (reutiliza la preparación de la base local y el arranque)

SALIDA = base.SALIDA
EMAIL = "recepcion1.col@pms-demo.test"


def ajustar_datos():
    """Deja visibles todos los estados en la planta 1 del primer hotel: un bloqueo, una habitación fuera de servicio y una opción."""
    os.environ["DATABASE_URL"] = base.LOCAL
    from pms import bloqueos, db, seguridad
    with db.tx() as cx:
        cx.execute("update pms_usuarios set debe_cambiar_clave=false where email=%s", (EMAIL,))
        rec = seguridad.actor_de(cx.execute("select * from pms_usuarios where email=%s", (EMAIL,)).fetchone())
        ger = seguridad.actor_de(cx.execute("select * from pms_usuarios where hotel_id=%s and rol='gerencia' limit 1", (rec["hotel_id"],)).fetchone())
        habs = cx.execute("select id, numero from pms_habitaciones where hotel_id=%s and planta=1 order by numero", (rec["hotel_id"],)).fetchall()
    hoy = dt.date.today()
    # libera 103 y 104 (el movimiento ficticio puede haberlas vendido) y las deja para bloqueo / fuera de servicio
    with db.tx() as cx:
        for h in habs:
            if h["numero"] in ("102", "103", "104"):
                cx.execute("delete from pms_reserva_noches where habitacion_id=%s and noche between %s and %s", (h["id"], hoy, hoy + dt.timedelta(days=2)))
    ids = {h["numero"]: h["id"] for h in habs}
    from pms import reservas
    with db.tx() as cx:
        hues = cx.execute("select id from pms_huespedes where hotel_id=%s order by id limit 1", (rec["hotel_id"],)).fetchone()["id"]
        tipo = cx.execute("select tipo_id from pms_habitaciones where id=%s", (ids["102"],)).fetchone()["tipo_id"]
    reservas.crear(rec, rec["hotel_id"], hues, tipo, hoy, hoy + dt.timedelta(days=2), 2, estado="opcion", habitacion_id=ids["102"])
    bloqueos.crear(ger, rec["hotel_id"], ids["103"], hoy, hoy + dt.timedelta(days=1), "Pintura")
    with db.tx() as cx:
        cx.execute("update pms_habitaciones set estado_limpieza='fuera_de_servicio' where id=%s", (ids["104"],))
    db.cerrar_pool()


def main():
    claves = base.preparar_base()
    ajustar_datos()
    env = {**os.environ, "DATABASE_URL": base.LOCAL, "PMS_SESION_SECRETO": "prueba-local", "PMS_MODO_DEMO": "no", "PMS_ENTORNO": "produccion"}
    log = open("/tmp/pms_capt_app.log", "w")
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app/Inicio.py", "--server.port", base.PUERTO, "--server.headless", "true"],
                            cwd=RAIZ, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        base.esperar_app(proc)
        with sync_playwright() as p:
            nav = p.chromium.launch(executable_path=os.environ.get("PMS_CHROME") or None, args=["--no-sandbox"])
            ctx = nav.new_context(viewport={"width": 1440, "height": 1500}, locale="es-CO")
            pg = ctx.new_page()
            base.entrar(pg, EMAIL, claves[EMAIL])
            pg.wait_for_selector("[data-testid='stSidebarNavLink']", timeout=30000)
            pg.locator("[data-testid='stSidebarNavLink']", has_text="Plano de habitaciones").first.click()
            pg.get_by_role("heading", name="Plano de habitaciones").wait_for(timeout=30000)
            pg.get_by_text("Planta 1").first.wait_for(timeout=30000)
            pg.wait_for_timeout(1500)
            pg.screenshot(path=str(SALIDA / "plano.png"), full_page=True)
            pg.locator(".st-key-pms_plano_planta").screenshot(path=str(SALIDA / "plano_planta.png"))
            boton = pg.get_by_role("button", name="Elegir").first
            boton.click()
            pg.get_by_text("Total estimado").first.wait_for(timeout=30000)
            pg.wait_for_timeout(1000)
            pg.screenshot(path=str(SALIDA / "plano_detalle.png"), full_page=True)
            pg.get_by_role("button", name="Continuar con la reserva").click()
            pg.get_by_role("heading", name="Reservas").wait_for(timeout=30000)
            pg.get_by_text("Datos traídos del Plano").wait_for(timeout=30000)
            pg.wait_for_timeout(1000)
            pg.screenshot(path=str(SALIDA / "plano_reserva.png"), full_page=True)
            # la sesión sigue activa y la navegación intacta
            assert pg.locator("[data-testid='stSidebarNavLink']").count() >= 5
            ctx.close()
            nav.close()
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:
            proc.kill()
    print("Capturas del plano OK")


if __name__ == "__main__":
    main()

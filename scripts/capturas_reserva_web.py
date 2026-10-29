"""Capturas de la reserva web con una base LOCAL de pruebas (nunca producción) y datos ficticios.
Uso:  PMS_CHROME=/usr/bin/google-chrome python scripts/capturas_reserva_web.py [carpeta]
Arranca la mini web (puerto 8602) y el PMS interno (8598), recorre el flujo del cliente y toma las capturas del PMS con las
reservas web (Reservas web y Reservas). Las contraseñas de la base local son aleatorias y no se imprimen ni salen en las capturas."""
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))
import capturas_primer_ingreso as base  # noqa: E402

EMAIL = "recepcion1.col@pms-demo.test"
SALIDA = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "docs" / "capturas"
PUERTO_WEB = "8602"


def datos_web():
    os.environ["DATABASE_URL"] = base.LOCAL
    from pms import db, pasarela, reserva_web as rw
    with db.tx() as cx:
        cx.execute("update pms_usuarios set debe_cambiar_clave=false where email=%s", (EMAIL,))
        h = cx.execute("select hotel_id from pms_usuarios where email=%s", (EMAIL,)).fetchone()["hotel_id"]
    hoy = dt.date.today()
    tipos = [t for t in rw.buscar(h, hoy + dt.timedelta(days=9), hoy + dt.timedelta(days=11))["tipos"] if t["cotizacion"] and t["libres"] >= 3]
    e, s = hoy + dt.timedelta(days=9), hoy + dt.timedelta(days=11)
    # 1) confirmada y pagada
    b = rw.crear_bloqueo(h, tipos[0]["tipo_id"], e, s, 2, 0)
    rw.completar_datos(b["numero"], b["token"], "Camila", "Prueba Ficticia", "camila@prueba-web.invalid", acepta_tratamiento=True)
    p = rw.iniciar_pago(b["numero"], b["token"])
    ev, f = pasarela.PasarelaSimulada().evento(p["referencia"], p["monto"], p["moneda"], True)
    rw.procesar_evento(ev, f)
    # 2) bloqueo en curso
    rw.crear_bloqueo(h, tipos[0]["tipo_id"], e, s, 2, 0)
    # 3) bloqueo vencido → liberado
    b3 = rw.crear_bloqueo(h, tipos[0]["tipo_id"], e, s, 2, 0)
    with db.tx() as cx:
        cx.execute("update pms_reservas set opcion_vence_en = now() - interval '1 second' where referencia_externa=%s", (b3["numero"],))
    # 4) pago rechazado
    b4 = rw.crear_bloqueo(h, tipos[0]["tipo_id"], e, s, 2, 0)
    rw.completar_datos(b4["numero"], b4["token"], "Mateo", "Ejemplo", "mateo@prueba-web.invalid", acepta_tratamiento=True)
    p4 = rw.iniciar_pago(b4["numero"], b4["token"])
    ev, f = pasarela.PasarelaSimulada().evento(p4["referencia"], p4["monto"], p4["moneda"], False)
    rw.procesar_evento(ev, f)
    with db.tx() as cx:
        from pms import vencimientos
        vencimientos.liberar_vencidas(cx)
    db.cerrar_pool()


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    claves = base.preparar_base()
    datos_web()
    env = {**os.environ, "DATABASE_URL": base.LOCAL, "PMS_SESION_SECRETO": "prueba-local", "PMS_MODO_DEMO": "no", "PMS_ENTORNO": "produccion"}
    pms = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app/Inicio.py", "--server.port", base.PUERTO, "--server.headless", "true"],
                           cwd=RAIZ, env=env, stdout=open("/tmp/pms_cw_app.log", "w"), stderr=subprocess.STDOUT)
    web = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "reserva_web/Reservas.py", "--server.port", PUERTO_WEB, "--server.headless", "true"],
                           cwd=RAIZ, env=env, stdout=open("/tmp/pms_cw_web.log", "w"), stderr=subprocess.STDOUT)
    try:
        base.esperar_app(pms)
        with sync_playwright() as p:
            nav = p.chromium.launch(executable_path=os.environ.get("PMS_CHROME") or None, args=["--no-sandbox"])
            ctx = nav.new_context(viewport={"width": 1440, "height": 1000}, locale="es-CO")
            pg = ctx.new_page()
            base.entrar(pg, EMAIL, claves[EMAIL])
            pg.wait_for_selector("[data-testid='stSidebarNavLink']", timeout=30000)
            pg.locator("[data-testid='stSidebarNavLink']", has_text="Reservas web").first.click()
            pg.get_by_role("heading", name="Reservas web").wait_for(timeout=30000)
            pg.wait_for_timeout(2500)
            pg.screenshot(path=str(SALIDA / "pms_reservas_web.png"), full_page=True)
            pg.locator("[data-testid='stSidebarNavLink']", has_text="Reservas").first.click()
            pg.get_by_role("heading", name="Reservas").first.wait_for(timeout=30000)
            pg.wait_for_timeout(2500)
            pg.screenshot(path=str(SALIDA / "pms_reservas_canal_web.png"), full_page=True)
            nav.close()
        print("Capturas del PMS OK")
    finally:
        for pr in (pms, web):
            pr.terminate()
            try:
                pr.wait(10)
            except Exception:
                pr.kill()


if __name__ == "__main__":
    main()

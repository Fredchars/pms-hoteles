"""Prueba de punta a punta de la mini web de reservas con un navegador real (Playwright, sin interfaz). Datos ficticios.
Uso: python scripts/e2e_navegador_reserva_web.py URL [carpeta_capturas] [--movil]
Recorre: buscar → elegir habitación del plano → bloquear (captcha) → datos + consentimiento → pasarela simulada → confirmación,
y guarda capturas. Imprime el número de reserva creado (para limpiarlo después). No imprime secretos."""
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    url, carpeta = args[0], Path(args[1] if len(args) > 1 else "capturas")
    movil = "--movil" in sys.argv
    carpeta.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("PMS_CHROME") or None, args=["--no-sandbox"])
        ctx = b.new_context(viewport={"width": 390, "height": 2600} if movil else {"width": 1100, "height": 2100})
        pg = ctx.new_page()
        pre = "movil_" if movil else ""
        pg.goto(url, wait_until="domcontentloaded")
        pg.get_by_role("button", name="Ver habitaciones disponibles").wait_for(timeout=90000)
        pg.screenshot(path=str(carpeta / f"{pre}01_busqueda.png"), full_page=True)
        pg.get_by_role("button", name="Ver habitaciones disponibles").click()
        pg.get_by_text("Plano de habitaciones").first.wait_for(timeout=60000)
        pg.wait_for_timeout(800)
        pg.screenshot(path=str(carpeta / f"{pre}02_plano.png"), full_page=True)
        pg.get_by_role("button", name="Elegir", exact=True).first.click()
        pg.get_by_text("Tu elección").wait_for(timeout=30000)
        txt = pg.get_by_text(re.compile(r"cuánto es \d \+ \d")).first.inner_text()
        a, c = map(int, re.findall(r"\d", txt.split("es")[-1])[:2])
        pg.get_by_label(re.compile("Verificación anti-robots")).fill(str(a + c))
        pg.get_by_label(re.compile("Verificación anti-robots")).press("Enter")
        pg.screenshot(path=str(carpeta / f"{pre}03_eleccion.png"), full_page=True)
        pg.get_by_role("button", name="Bloquear mi habitación").click()
        pg.get_by_text("Tus datos").first.wait_for(timeout=60000)
        pg.wait_for_timeout(1500)
        pg.screenshot(path=str(carpeta / f"{pre}04_datos_con_temporizador.png"), full_page=True)
        pg.get_by_label("Nombres *").fill("Camila")
        pg.get_by_label("Apellidos *").fill("Prueba Ficticia")
        pg.get_by_label(re.compile("Correo electrónico")).fill("camila@prueba-web.invalid")
        pg.get_by_label("Teléfono").fill("+57 300 000 0000")
        pg.get_by_text("Leer el aviso de privacidad").click()
        pg.wait_for_timeout(500)
        pg.screenshot(path=str(carpeta / f"{pre}05_consentimiento.png"), full_page=True)
        pg.get_by_role("button", name="Continuar al pago").click()
        pg.wait_for_timeout(1500)
        assert pg.get_by_text("Ley 1581").count() > 0 and pg.get_by_role("button", name=re.compile("^Pagar ")).count() == 0, \
            "sin consentimiento no debe avanzar"
        pg.get_by_text("Autorizo el tratamiento").click()
        pg.get_by_role("button", name="Continuar al pago").click()
        pg.get_by_role("button", name=re.compile("^Pagar ")).wait_for(timeout=60000)
        pg.screenshot(path=str(carpeta / f"{pre}06_resumen_pago.png"), full_page=True)
        pg.get_by_role("button", name=re.compile("^Pagar ")).click()
        pg.get_by_text("MODO PRUEBAS: no se cobra dinero").first.wait_for(timeout=60000)
        pg.screenshot(path=str(carpeta / f"{pre}07_pasarela_simulada.png"), full_page=True)
        pg.get_by_role("button", name=re.compile("Simular pago aprobado")).click()
        pg.get_by_text("Reserva confirmada").first.wait_for(timeout=60000)
        pg.get_by_text("Correo simulado: no se envió").first.wait_for(timeout=30000)
        pg.wait_for_timeout(800)
        numero = re.search(r"PMS-\d{4}-[A-Z2-9]{6}", pg.locator("body").inner_text()).group(0)
        pg.screenshot(path=str(carpeta / f"{pre}08_confirmacion.png"), full_page=True)
        pg.get_by_text(re.compile("^Ver correo")).first.click()
        pg.wait_for_timeout(1200)
        pg.screenshot(path=str(carpeta / f"{pre}09_correo_simulado.png"), full_page=True)
        assert "Traceback" not in pg.locator("body").inner_text()
        print("RESERVA_WEB_CREADA", numero)
        b.close()


if __name__ == "__main__":
    main()

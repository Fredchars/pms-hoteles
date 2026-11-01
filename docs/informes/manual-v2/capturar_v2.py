"""Capturas NUEVAS de la Suite v2 (pms_v2/Inicio.py) para el manual descriptivo por pantalla.
Base LOCAL de pruebas (nunca producción) con datos ficticios; las contraseñas son aleatorias, no se imprimen ni aparecen.
Guarda PNG en crudas/ y las cajas de cada zona (para numerar) en crudas/cajas.json. Prototipo diseñado para ATm Consulting."""
import json, os, subprocess, sys, time, urllib.parse
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
sys.path[:0] = [str(RAIZ), str(RAIZ / "scripts")]
os.environ.setdefault("PMS_CAPT_PG_URL", "postgresql://postgres@127.0.0.1:55432/pms_capturas")
import capturas_primer_ingreso as base  # noqa: E402
import capturas_reserva_web as cw  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PUERTO = "8687"
URL = f"http://localhost:{PUERTO}"
SAL = AQUI / "crudas"
CAJAS = {}


JS_BORDE = """([texto, nth]) => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 2 && r.height > 2; };
  const cands = [...document.querySelectorAll('[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"], [data-testid="stMainBlockContainer"] [data-testid="stExpander"]')]
    .filter(e => { const st = getComputedStyle(e); return parseFloat(st.borderTopWidth) > 0 && st.borderTopStyle !== 'none' && vis(e); });
  let lst = texto ? cands.filter(e => e.innerText.includes(texto)) : cands;
  if (texto) lst.sort((a, b) => a.getBoundingClientRect().width * a.getBoundingClientRect().height - b.getBoundingClientRect().width * b.getBoundingClientRect().height);
  const e = lst[nth || 0]; if (!e) return null; const r = e.getBoundingClientRect();
  return {x: r.x, y: r.y, width: r.width, height: r.height};
}"""


def caja(pg, sel, nth=None, texto=None, pad=6):
    if sel == "BORDE":
        b = pg.evaluate(JS_BORDE, [texto, nth])
        if not b:
            print("   (sin caja) BORDE", texto, nth)
            return None
        return [round(b["x"] - pad), round(b["y"] - pad), round(b["x"] + b["width"] + pad), round(b["y"] + b["height"] + pad)]
    sel = sel + " >> visible=true"
    loc = pg.locator(sel) if texto is None else pg.locator(sel, has_text=texto)
    n = loc.count()
    items = loc.all() if nth is None else ([loc.nth(nth)] if nth < n else [])
    bs = []
    for i in items:
        try:
            b = i.bounding_box(timeout=2000)
        except Exception:
            b = None
        if b and b["width"] > 2 and b["height"] > 2:
            bs.append(b)
    if not bs:
        print("   (sin caja)", sel, texto, nth)
        return None
    x0 = min(b["x"] for b in bs); y0 = min(b["y"] for b in bs)
    x1 = max(b["x"] + b["width"] for b in bs); y1 = max(b["y"] + b["height"] for b in bs)
    return [round(x0 - pad), round(y0 - pad), round(x1 + pad), round(y1 + pad)]


def listo(pg, espera=2500):
    pg.wait_for_selector("h1, h2", timeout=30000)
    for _ in range(40):
        if pg.locator("[data-testid='stSpinner'], [data-testid='stStatusWidget'] [data-testid='stStatusWidgetRunningIcon']").count() == 0:
            break
        pg.wait_for_timeout(300)
    pg.wait_for_timeout(espera)


def foto(pg, nombre, zonas, ancho=1440):
    """zonas: lista de (n, selector, nth, texto). Ajusta la altura del viewport al contenido para que todo quepa."""
    alto = pg.evaluate("""() => { const m=document.querySelector('section[data-testid="stMain"]')||document.body;
        const b=document.querySelector('[data-testid="stMainBlockContainer"]'); return Math.max(m.scrollHeight, b? b.scrollHeight+160:0, 800); }""")
    pg.set_viewport_size({"width": ancho, "height": min(int(alto) + 40, 5200)})
    pg.wait_for_timeout(1200)
    if pg.locator("[data-testid='stException']").count():
        print("   ¡EXCEPCIÓN EN PANTALLA!", nombre)
    if nombre in ("10_dashboard", "16_reservas_gestionar") and not getattr(foto, "_d"+nombre, False):
        setattr(foto, "_d"+nombre, True)
        print(sorted(set(pg.evaluate("() => [...document.querySelectorAll('[data-testid]')].map(e=>e.dataset.testid)"))))
    res = []
    for z in zonas:
        n, sel = z[0], z[1]
        nth = z[2] if len(z) > 2 else None
        tx = z[3] if len(z) > 3 else None
        b = caja(pg, sel, nth, tx)
        if b:
            res.append({"n": n, "box": b})
    pg.screenshot(path=str(SAL / f"{nombre}.png"))
    CAJAS[nombre] = res
    print("ok", nombre, len(res), "zonas")
    pg.set_viewport_size({"width": ancho, "height": 1000})


def entrar(pg, email, clave):
    base.entrar(pg, email, clave)
    pg.wait_for_selector("[data-testid='stSidebarNavLink']", timeout=40000)
    listo(pg)
    return urllib.parse.parse_qs(urllib.parse.urlparse(pg.url).query)["s"][0]


def ir(pg, clave, s):
    pg.goto(f"{URL}/{'' if clave == 'dashboard' else clave}?s={s}")
    pg.wait_for_selector("[data-testid='stSidebarNavLink']", timeout=40000)
    listo(pg)
    vb = pg.locator("[data-testid='stSidebarNavViewButton']")
    if vb.count() and "more" in (vb.first.inner_text() or "").lower():
        vb.first.click()
        pg.wait_for_timeout(800)


def tab(pg, texto):
    pg.get_by_role("tab").filter(has_text=texto).first.click()
    pg.wait_for_timeout(1800)


def elegir_select(pg, etiqueta, idx=0):
    pg.get_by_text(etiqueta).first.click()
    pg.wait_for_timeout(600)
    pg.locator("li[role='option']").nth(idx).click()
    pg.wait_for_timeout(2200)


SB = "section[data-testid='stSidebar']"
NAV = "[data-testid='stSidebarNav']"
H1 = "[data-testid='stMainBlockContainer'] h1"
AV = "[data-testid='stMainBlockContainer'] .pms-aviso"
MET = "[data-testid='stMainBlockContainer'] [data-testid='stMetric']"
DF = "[data-testid='stMainBlockContainer'] [data-testid='stDataFrame']"
TABS = "[data-testid='stMainBlockContainer'] [data-testid='stTabs'] [role='tablist']"
EXP = "[data-testid='stMainBlockContainer'] [data-testid='stExpander']"
BOT = "[data-testid='stMainBlockContainer'] [data-testid='stButton']"
SEL = "[data-testid='stMainBlockContainer'] [data-testid='stSelectbox']"
DATE = "[data-testid='stMainBlockContainer'] [data-testid='stDateInput']"
NUM = "[data-testid='stMainBlockContainer'] [data-testid='stNumberInput']"
TXT = "[data-testid='stMainBlockContainer'] [data-testid='stTextInput']"
CONT = "BORDE"
PIE = ".pms-pie"


def main():
    SAL.mkdir(parents=True, exist_ok=True)
    claves = base.preparar_base()
    cw.datos_web()
    from pms import db
    os.environ["DATABASE_URL"] = base.LOCAL
    with db.tx() as cx:
        cx.execute("update pms_usuarios set debe_cambiar_clave=false where email in "
                   "('gerencia1.col@pms-demo.test','recepcion1.col@pms-demo.test','housekeeping1.col@pms-demo.test','admin@pms-demo.test')")
    db.cerrar_pool()
    env = {**os.environ, "DATABASE_URL": base.LOCAL, "PMS_SESION_SECRETO": "prueba-local", "PMS_MODO_DEMO": "no", "PMS_ENTORNO": "produccion"}
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "pms_v2/Inicio.py", "--server.port", PUERTO, "--server.headless", "true"],
                            cwd=RAIZ, env=env, stdout=open("/tmp/pms_v2_manual.log", "w"), stderr=subprocess.STDOUT)
    base.URL = URL
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"{URL}/_stcore/health", timeout=2); break
            except Exception:
                time.sleep(1)
        with sync_playwright() as p:
            nav = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
            nueva = lambda: nav.new_context(viewport={"width": 1440, "height": 1000}, locale="es-CO").new_page()

            # ---------- ingreso y primer ingreso ----------
            pg = nueva(); pg.goto(URL); pg.wait_for_selector("input[aria-label='Correo']", timeout=40000); listo(pg, 1500)
            foto(pg, "01_ingreso", [(1, "h1"), (2, ".pms-aviso"), (3, TXT, 0), (4, TXT, 1), (5, "[data-testid='stFormSubmitButton']"),
                                    (6, "[data-testid='stAlert']"), (7, PIE)])
            pg = nueva(); base.entrar(pg, "recepcion2.col@pms-demo.test", claves["recepcion2.col@pms-demo.test"])
            pg.get_by_role("heading", name="Crea tu contraseña nueva").wait_for(timeout=40000); listo(pg, 1500)
            foto(pg, "02_clave_nueva", [(1, "h1"), (2, "[data-testid='stMarkdownContainer']", None, "al menos"), (3, TXT, 0), (4, TXT, 1),
                                        (5, "[data-testid='stFormSubmitButton']"), (6, BOT, None, "Cerrar sesión")])
            pg.fill("input[aria-label='Contraseña nueva']", "corta"); pg.fill("input[aria-label='Confirma la contraseña nueva']", "corta")
            pg.get_by_role("button", name="Guardar y entrar").click(); pg.wait_for_timeout(2500)
            foto(pg, "02b_clave_nueva_error", [(1, "[data-testid='stAlert']")])

            # ---------- gerencia (Colombia) ----------
            pg = nueva(); s = entrar(pg, "gerencia1.col@pms-demo.test", claves["gerencia1.col@pms-demo.test"])
            ir(pg, "dashboard", s)
            foto(pg, "10_dashboard", [(1, SB + " [data-testid='stSidebarHeader']"), (2, SB + " [data-testid='stSidebarUserContent']"), (3, NAV),
                                      (4, H1), (5, AV), (6, CONT, 0), (7, "[data-testid='stHorizontalBlock']", None, "Ocupación hoy"), (8, DF, 0), (9, DF, 1),
                                      (10, "[data-testid='stHorizontalBlock']", None, "Fuera de servicio"), (11, PIE)])
            ir(pg, "calendario", s)
            foto(pg, "11_planning", [(1, DATE), (2, SEL), (3, "[data-testid='stMarkdownContainer']", None, "Leyenda"), (4, ".pms-cal tr", 0),
                                     (5, ".pms-cal td[colspan]", 0), (6, ".pms-cal td.hab", 0), (7, ".pms-cal td[title]", 0), (8, "[data-testid='stPageLink']")])
            ir(pg, "plano", s)
            foto(pg, "12_plano", [(1, SEL, 0), (2, DATE), (3, NUM, 0), (3, NUM, 1), (4, SEL, 1), (5, "[data-testid='stCheckbox']"), (6, SEL, 2),
                                  (7, MET), (8, ".pms-leyenda"), (9, ".pl-mar"), (10, ".pms-room", 0), (11, ".pl-pasillo"),
                                  (12, CONT, None, "Detalle de la habitación")])
            pg.locator(BOT, has_text="Elegir").first.locator("button").click(); pg.wait_for_timeout(3500)
            foto(pg, "13_plano_detalle", [(1, ".pms-room-seleccionada"), (2, "[data-testid='stMarkdownContainer']", None, "Camas:"),
                                          (3, DF), (4, "[data-testid='stMarkdownContainer']", None, "Total estimado"),
                                          (5, BOT, None, "Continuar con la reserva")])
            pg.locator(BOT, has_text="Continuar con la reserva").locator("button").click(); pg.wait_for_timeout(4000); listo(pg)
            foto(pg, "15_reservas_nueva", [(1, TABS), (2, TXT, 0), (3, SEL, 0), (4, "[data-testid='stAlert']", None, "Plano"),
                                           (5, SEL, 1), (6, DATE), (7, SEL, 2), (8, NUM), (9, SEL, 3), (10, SEL, 4),
                                           (11, "[data-testid='stHeading']", None, "Desglose"), (12, BOT, None, "Guardar reserva")])
            ir(pg, "reservas", s)
            foto(pg, "14_reservas_lista", [(1, TABS), (2, "[data-testid='stMultiSelect']"), (3, TXT), (4, DATE), (5, DF)])
            tab(pg, "Gestionar"); listo(pg, 1500)
            foto(pg, "16_reservas_gestionar", [(1, SEL, 0), (2, "[data-testid='stMarkdownContainer'] h3"), (3, MET), (4, EXP, 0),
                                               (5, CONT, None, "Check"), (6, CONT, None, "Cancelar (requiere gerencia)"),
                                               (7, EXP, None, "Cambiar fechas"), (8, EXP, None, "Cambiar de habitación"), (9, EXP, None, "Confirmación al huésped")])
            tab(pg, "Cancelaciones pendientes"); listo(pg, 1500)
            foto(pg, "17_reservas_cancelaciones", [(1, CONT, None, "Motivo"), (2, TXT, None, "Comentario"), (3, BOT, None, "Aprobar"), (4, BOT, None, "Rechazar")])
            ir(pg, "reservas_web", s)
            foto(pg, "18_reservas_web", [(1, "[data-testid='stMainBlockContainer'] [data-testid='stCaptionContainer']", None, "bloqueo web"), (2, BOT, None, "Liberar"), (3, MET), (4, DF)])
            ir(pg, "huespedes", s)
            try:
                pg.locator("input[aria-label='Huésped']").first.click()
                pg.wait_for_timeout(900)
                op = pg.locator("[role='option'] >> visible=true")
                print("opciones", op.count())
                if op.count():
                    op.first.click()
                else:
                    pg.keyboard.press("ArrowDown"); pg.keyboard.press("Enter")
                pg.wait_for_timeout(2500)
            except Exception as e:
                pg.screenshot(path="/tmp/dbg_hu.png"); print("DBG huesped", type(e).__name__, str(e)[:300])
            foto(pg, "19_huespedes", [(1, TABS), (2, TXT, 0), (3, SEL, 0), (4, "[data-testid='stHorizontalBlock']", 0), (5, BOT, None, "Guardar cambios"),
                                      (6, CONT, None, "Prestación del servicio"), (7, EXP, None, "supresión")])
            ir(pg, "housekeeping", s)
            foto(pg, "20_housekeeping", [(1, MET), (2, "[data-testid='stMultiSelect']"), (3, "[data-testid='stHeading']", None, "Piso 1"),
                                         (4, CONT, 0), (5, ".pms-chip", 0), (6, BOT, 0), (7, "[data-testid='stPopover']", 0)])
            ir(pg, "tarifas", s)
            foto(pg, "21_tarifas", [(1, H1), (2, DF), (3, "[data-testid='stColumn']", 0), (4, "[data-testid='stColumn']", 1)])
            ir(pg, "bloqueos", s)
            foto(pg, "22_bloqueos", [(1, CONT, None, "Hab."), (2, BOT, None, "Liberar"), (3, SEL, 0), (4, DATE), (5, TXT), (6, BOT, None, "Crear bloqueo")])
            ir(pg, "facturacion", s)
            foto(pg, "23_facturacion", [(1, "[data-testid='stAlert']", 0), (2, TABS), (3, SEL, 0), (4, DF, 0), (5, MET),
                                        (6, "[data-testid='stDownloadButton']"), (7, CONT, None, "Agregar un extra"),
                                        (8, CONT, None, "Registrar pago"), (9, CONT, None, "Pedir un descuento"), (10, EXP, None, "Anular")])
            tab(pg, "Descuentos pendientes"); listo(pg, 1500)
            foto(pg, "24_facturacion_descuentos", [(1, CONT, None, "Motivo"), (2, BOT, None, "Aprobar"), (3, BOT, None, "Rechazar")])
            for clave, nombre in (("promos", "25_promos"), ("crm", "26_crm"), ("integraciones", "28_integraciones")):
                ir(pg, clave, s)
                foto(pg, nombre, [(1, H1), (2, ".v2-badge"), (3, ".v2-fase")])
            ir(pg, "reportes", s)
            foto(pg, "27_reportes", [(1, DATE), (2, MET), (3, "[data-testid='stVegaLiteChart']", 0), (4, "[data-testid='stVegaLiteChart']", 1),
                                     (5, DF), (6, "[data-testid='stDownloadButton']")])

            # ---------- administrador ----------
            pg = nueva(); s = entrar(pg, "admin@pms-demo.test", claves["admin@pms-demo.test"])
            ir(pg, "configuracion", s)
            foto(pg, "29_configuracion", [(1, NAV), (2, TABS), (3, DF), (4, EXP, 0), (5, EXP, 1)])
            tab(pg, "Habitaciones y camas"); listo(pg, 1500)
            foto(pg, "30_configuracion_habitaciones", [(1, "[data-testid='stMainBlockContainer'] [data-testid='stCaptionContainer']", None, "Distribución"), (2, DF), (3, EXP)])
            tab(pg, "Usuarios"); listo(pg, 1500)
            foto(pg, "31_configuracion_usuarios", [(1, DF), (2, EXP, 0), (3, EXP, 1), (4, EXP, 2)])
            ir(pg, "auditoria", s)
            foto(pg, "32_auditoria", [(1, TXT, 0), (2, TXT, 1), (3, SEL, 0), (4, "[data-testid='stMainBlockContainer'] [data-testid='stCaptionContainer']", None, "registro"), (5, DF)])

            # ---------- roles con menú reducido ----------
            pg = nueva(); s = entrar(pg, "housekeeping1.col@pms-demo.test", claves["housekeeping1.col@pms-demo.test"])
            listo(pg, 1500)
            foto(pg, "33_rol_housekeeping", [(1, NAV), (2, MET), (3, BOT, 0)])
            pg = nueva(); s = entrar(pg, "recepcion1.col@pms-demo.test", claves["recepcion1.col@pms-demo.test"])
            ir(pg, "dashboard", s)
            foto(pg, "34_rol_recepcion", [(1, NAV), (2, MET)])
            nav.close()
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:
            proc.kill()
        (SAL / "cajas.json").write_text(json.dumps(CAJAS, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()

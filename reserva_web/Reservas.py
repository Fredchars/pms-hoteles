"""Mini web de reservas (prototipo) · punto de entrada de Streamlit: reserva_web/Reservas.py
Aplicación PÚBLICA y separada del PMS interno: usa solo `pms/reserva_web.py` (no hay sesión de personal, ni páginas internas, ni
acceso directo a la base desde el navegador). Embebible: ?embed=true (ver docs de «Reserva web»)."""
from __future__ import annotations

import base64
import datetime as dt
import os
import random
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="Reserva en línea · Prototipo", page_icon="🏨", layout="centered", initial_sidebar_state="collapsed")

for _k in ("DATABASE_URL", "PMS_SESION_SECRETO", "PMS_PASARELA_SECRETO", "PMS_WEB_URL", "PMS_ENTORNO", "PMS_WEB_HOLD_MINUTOS",
           "PMS_CORREO_PROVEEDOR", "PMS_CORREO_API_KEY", "PMS_CORREO_REMITENTE", "PMS_CORREO_PERMITIDOS"):
    try:
        if _k in st.secrets and not os.environ.get(_k):
            os.environ[_k] = str(st.secrets[_k])
    except Exception:
        pass


def _modulos_al_dia():
    """Streamlit Cloud actualiza el código sin reiniciar el proceso: si cambió algo de `pms/`, se descartan los módulos viejos."""
    marca = max((f.stat().st_mtime_ns for f in (RAIZ / "pms").glob("*.py")), default=0)
    if getattr(sys, "_pms_marca", None) == marca:
        return
    viejos = [k for k in sys.modules if k == "pms" or k.startswith("pms.")]
    if viejos:
        try:
            sys.modules["pms.db"].cerrar_pool()
        except Exception:
            pass
        for k in viejos:
            del sys.modules[k]
    sys._pms_marca = marca


_modulos_al_dia()
from pms import correo, dibujo, huespedes, pasarela, reserva_web as rw  # noqa: E402
from pms.errores import ErrorNegocio  # noqa: E402
from pms.util import fmt_moneda, hoy_hotel  # noqa: E402

MARCA = "Prototipo diseñado para ATm Consulting"
LEYENDA = pasarela.LEYENDA_PRUEBAS
ASSETS = RAIZ / "app" / "assets"
INCRUSTADO = str(st.query_params.get("embed", "")).lower() == "true"
URL_PUBLICA = os.environ.get("PMS_WEB_URL", "https://pms-reservas-atm.streamlit.app").rstrip("/")

AVISO_PRIVACIDAD = """**Aviso de privacidad (Ley 1581 de 2012, Colombia).**
**Responsable:** el hotel donde haces la reserva (en este prototipo, un hotel ficticio de demostración de ATm Consulting).
**Finalidad:** usamos tus datos (nombre, correo, teléfono y documento si lo indicas) únicamente para gestionar tu reserva, el pago y
enviarte la confirmación. Si marcas la casilla opcional, también para enviarte ofertas.
**Tus derechos:** conocer, actualizar y rectificar tus datos, pedir su supresión, revocar tu autorización y presentar quejas ante la
Superintendencia de Industria y Comercio. Puedes ejercerlos escribiendo al hotel.
**Datos sensibles:** no te pedimos datos de tarjetas: el pago lo procesa la pasarela. Este prototipo no cobra dinero."""


@st.cache_data(show_spinner=False)
def _logo() -> str:
    return base64.b64encode((ASSETS / "atm_logo_pie.png").read_bytes()).decode()


st.markdown(f"""
<style>
.stApp {{background:#fff}}
div[data-testid="stMainBlockContainer"] {{max-width:760px;padding:{'1rem' if INCRUSTADO else '2rem'} 1rem 5rem}}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{display:none}}
.rw-aviso {{background:#FFF4E5;border:1px solid #F5A524;border-radius:8px;padding:.5rem .8rem;margin-bottom:.8rem;font-size:.88rem;color:#5c3b00}}
.rw-prueba {{background:#fff4cc;border:2px dashed #b88a00;border-radius:8px;padding:.5rem .8rem;margin:.4rem 0 .8rem;font-weight:700;color:#7a5b00;text-align:center}}
.rw-room {{border:2px solid #cbd2d9;border-radius:12px;padding:.5rem .6rem;line-height:1.25;background:#fff;margin-bottom:.25rem}}
.rw-room .n {{font-size:1.2rem;font-weight:700;color:#102a43}} .rw-room .t,.rw-room .m {{font-size:.8rem;color:#52606d}}
.rw-room .p {{font-size:.85rem;font-weight:600;color:#102a43}}
.rw-libre {{background:#e8f7ee;border-color:#2f9e60}}
.rw-no {{background:#f1f3f5;border-color:#d9dee3}} .rw-no .n,.rw-no .t,.rw-no .m,.rw-no .p {{color:#9aa5b1}}
.rw-sel {{background:#dbeafe;border-color:#1a56a8;box-shadow:0 0 0 3px #1a56a833}}
.rw-timer {{background:#102a43;color:#fff;border-radius:10px;padding:.55rem .9rem;font-size:1.05rem;text-align:center;margin-bottom:.8rem}}
.rw-timer b {{font-size:1.5rem;letter-spacing:.06em}}
.rw-numero {{background:#f4f6f8;border-radius:10px;padding:.8rem;text-align:center;margin:.6rem 0}}
.rw-numero div:first-child {{font-size:.75rem;color:#52606d;letter-spacing:.08em}}
.rw-numero div:last-child {{font-size:1.9rem;font-weight:800;color:#102a43;letter-spacing:.05em}}
.rw-pasarela {{border:1px solid #c6d0da;border-radius:12px;padding:1rem;background:#fafcff}}
.rw-pie {{position:fixed;left:0;right:0;bottom:0;z-index:999;background:rgba(255,255,255,.97);border-top:1px solid #d9e2ec;padding:.3rem 1rem;
         text-align:center;font-size:.85rem;color:#334e68}}
.rw-pie img {{height:22px;vertical-align:middle;margin-right:.45rem}}
</style>
<div class="rw-pie"><img src="data:image/png;base64,{_logo()}" alt="ATm Consulting">{MARCA}</div>""", unsafe_allow_html=True)


def _ip() -> str:
    try:
        h = st.context.headers
        return (h.get("X-Forwarded-For") or h.get("X-Real-Ip") or "").split(",")[0].strip()
    except Exception:
        return ""


def _fecha(d) -> str:
    return f"{d:%d/%m/%Y}"


def _error(e: Exception):
    if isinstance(e, ErrorNegocio):
        st.error(str(e))
    else:
        print(f"[reserva_web] error inesperado: {type(e).__name__}", file=sys.stderr)
        st.error("No pudimos completar la operación por un problema técnico. Intenta de nuevo en un momento.")


def _params(numero=None, token=None, **extra):
    hotel = st.query_params.get("hotel")
    st.query_params.clear()
    for k, v in {"r": numero, "k": token, "hotel": hotel, **extra}.items():
        if v:
            st.query_params[k] = v
    if INCRUSTADO:
        st.query_params["embed"] = "true"


def _nueva_busqueda():
    for k in [k for k in st.session_state if k.startswith("rw_")]:
        del st.session_state[k]
    _params()
    st.rerun()


@st.fragment(run_every=1)
def _temporizador(fin: float):
    resto = int(fin - time.time())
    if resto <= 0:
        st.rerun()
    st.markdown(f'<div class="rw-timer">⏱ Tu habitación está bloqueada para ti durante <b>{resto // 60:02d}:{resto % 60:02d}</b></div>',
                unsafe_allow_html=True)


def encabezado(subtitulo: str = ""):
    st.markdown("## 🏨 Reserva en línea")
    if subtitulo:
        st.caption(subtitulo)
    st.markdown('<div class="rw-aviso">🧪 <b>Prototipo con datos ficticios.</b> No se cobra dinero ni se hace una reserva real: '
                'el pago y el correo son simulados.</div>', unsafe_allow_html=True)


# ------------------------------------------------------------------ 1) búsqueda + plano
def vista_buscar():
    encabezado("Elige hotel, fechas y huéspedes para ver las habitaciones libres.")
    hoteles = rw.hoteles_publicos()
    if not hoteles:
        st.info("No hay hoteles disponibles ahora mismo.")
        return
    fijo = st.query_params.get("hotel")
    if fijo and str(fijo).isdigit() and int(fijo) in {h["id"] for h in hoteles}:
        hoteles = [h for h in hoteles if h["id"] == int(fijo)]
    with st.form("rw_form_buscar"):
        hid = st.selectbox("Hotel", [h["id"] for h in hoteles], format_func=lambda i: next(h["nombre"] for h in hoteles if h["id"] == i),
                           disabled=len(hoteles) == 1, key="rw_hotel")
        hoy = hoy_hotel(None, hid)
        c1, c2 = st.columns(2)
        entrada = c1.date_input("Entrada", hoy + dt.timedelta(days=7), min_value=hoy, format="DD/MM/YYYY", key="rw_entrada")
        salida = c2.date_input("Salida", hoy + dt.timedelta(days=9), min_value=hoy + dt.timedelta(days=1), format="DD/MM/YYYY", key="rw_salida")
        c3, c4 = st.columns(2)
        adultos = c3.number_input("Adultos", 1, rw.MAX_PERSONAS, 2, key="rw_adultos")
        ninos = c4.number_input("Niños", 0, rw.MAX_PERSONAS, 0, key="rw_ninos")
        ok = st.form_submit_button("Ver habitaciones disponibles", type="primary")
    if ok:
        st.session_state.pop("rw_sel", None)
        try:
            res = rw.buscar(hid, entrada, salida, int(adultos), int(ninos))
            st.session_state["rw_busq"] = {"hotel_id": hid, "entrada": entrada, "salida": salida, "adultos": int(adultos),
                                           "ninos": int(ninos), "res": res}
        except Exception as e:
            st.session_state.pop("rw_busq", None)
            _error(e)
    b = st.session_state.get("rw_busq")
    if b:
        _resultados(b)


def _resultados(b: dict):
    res, mon = b["res"], b["res"]["hotel"]["moneda"]
    st.markdown(f"**{res['hotel']['nombre']}** · {_fecha(b['entrada'])} → {_fecha(b['salida'])} · {res['noches']} noche(s) · "
                f"{b['adultos']} adulto(s)" + (f", {b['ninos']} niño(s)" if b["ninos"] else ""))
    sel = st.session_state.get("rw_sel")
    if sel:
        _confirmar_bloqueo(b, sel)
    st.subheader("Tipos de habitación")
    cot = {}
    for t in res["tipos"]:
        with st.container(border=True):
            c1, c2 = st.columns([3, 2])
            c1.markdown(f"**{t['nombre']}** · hasta {t['capacidad']} personas  \n<span style='color:#52606d;font-size:.85rem'>{t['descripcion']}</span>",
                        unsafe_allow_html=True)
            if t["cotizacion"]:
                cot[t["tipo_id"]] = t["cotizacion"]
                c2.markdown(f"**{fmt_moneda(t['cotizacion']['total'], mon)}**  \n<span style='font-size:.8rem'>total con impuestos · "
                            f"{t['libres']} libre(s)</span>", unsafe_allow_html=True)
                if c2.button("Reservar este tipo", key=f"rw_tipo_{t['tipo_id']}"):
                    st.session_state["rw_sel"] = {"tipo_id": t["tipo_id"], "habitacion_id": None, "nombre": t["nombre"],
                                                  "total": t["cotizacion"]["total"]}
                    st.rerun()
            else:
                c2.caption(t["motivo"] or "No disponible")
    st.subheader("Plano de habitaciones")
    st.markdown(f"<style>{dibujo.CSS}</style>"
                '<div style="display:flex;gap:1rem;font-size:.82rem;color:#334e68;margin-bottom:.4rem"><span>🟩 Libre</span><span>⬜ No disponible</span>'
                '<span>🟦 Elegida</span><span>🌊 Vista al mar</span></div>', unsafe_allow_html=True)
    plantas = sorted({h["planta"] for h in res["plano"]})
    if not plantas:
        return

    def _celda(h):
        elegida = bool(sel) and sel["habitacion_id"] == h["habitacion_id"]
        clase = "rw-sel" if elegida else ("rw-libre" if h["libre"] else "rw-no")
        precio = fmt_moneda(h["total"], mon) + " <span>total</span>" if h["libre"] else "—"
        st.markdown(dibujo.tarjeta(f"rw-room {clase}", h["numero"], h["tipo"], h["vista"], h.get("vista_mar"), h["metros"], h.get("camas", []),
                                   precio, h.get("capacidad"), "Elegida" if elegida else ("Libre" if h["libre"] else "No disponible")),
                    unsafe_allow_html=True)
        if h["libre"] and st.button("Elegir" if not elegida else "✔ Elegida", key=f"rw_hab_{h['habitacion_id']}", disabled=elegida,
                                    width="stretch"):
            st.session_state["rw_sel"] = {"tipo_id": h["tipo_id"], "habitacion_id": h["habitacion_id"],
                                          "nombre": f"Habitación {h['numero']} · {h['tipo']}", "total": h["total"]}
            st.rerun()

    for pl in plantas:
        st.markdown(f"**Planta {pl}**")
        frente, fondo = dibujo.filas([h for h in res["plano"] if h["planta"] == pl])
        with st.container(key=f"rw_plano_planta_{pl}"):
            st.markdown(dibujo.MAR, unsafe_allow_html=True)
            for lista in (frente, fondo):
                if lista is fondo:
                    st.markdown(dibujo.PASILLO, unsafe_allow_html=True)
                for i in range(0, len(lista), 3):
                    cols = st.columns(3)
                    for col, h in zip(cols, lista[i:i + 3]):
                        with col:
                            _celda(h)


def _confirmar_bloqueo(b: dict, sel: dict):
    mon = b["res"]["hotel"]["moneda"]
    with st.container(border=True):
        st.markdown(f"#### Tu elección: {sel['nombre']}")
        st.write(f"Total: **{fmt_moneda(sel['total'], mon)}** (impuestos incluidos). Al continuar, **bloqueamos la habitación "
                 f"{rw.vencimientos.MINUTOS_BLOQUEO_WEB} minutos** para que puedas completar tus datos y el pago.")
        if "rw_cap" not in st.session_state:
            st.session_state["rw_cap"] = (random.randint(2, 9), random.randint(2, 9))
        a, c = st.session_state["rw_cap"]
        resp = st.text_input(f"Verificación anti-robots: ¿cuánto es {a} + {c}?", key="rw_cap_resp", max_chars=3)
        c1, c2 = st.columns(2)
        if c1.button("Bloquear mi habitación", type="primary", key="rw_bloquear"):
            if resp.strip() != str(a + c):
                st.error("La verificación no es correcta.")
            else:
                try:
                    r = rw.crear_bloqueo(b["hotel_id"], sel["tipo_id"], b["entrada"], b["salida"], b["adultos"], b["ninos"],
                                         sel["habitacion_id"], ip=_ip())
                except Exception as e:
                    _error(e)
                else:
                    st.session_state.pop("rw_cap", None)
                    st.session_state.pop("rw_sel", None)
                    _params(r["numero"], r["token"])
                    st.rerun()
        if c2.button("Cambiar elección", key="rw_cambiar"):
            st.session_state.pop("rw_sel", None)
            st.rerun()


# ------------------------------------------------------------------ 2) datos + consentimiento
def vista_datos(numero: str, token: str, c: dict):
    encabezado()
    _temporizador(time.time() + c["segundos"])
    _resumen(c)
    st.subheader("Tus datos")
    with st.form("rw_form_datos"):
        c1, c2 = st.columns(2)
        nombres = c1.text_input("Nombres *", max_chars=60, key="rw_nombres")
        apellidos = c2.text_input("Apellidos *", max_chars=60, key="rw_apellidos")
        email = st.text_input("Correo electrónico * (te enviaremos la confirmación)", max_chars=120, key="rw_email")
        tel = st.text_input("Teléfono", max_chars=25, key="rw_tel")
        c3, c4 = st.columns([1, 2])
        tdoc = c3.selectbox("Documento (opcional)", ["", "CC", "CE", "Pasaporte", "Otro"], key="rw_tdoc", format_func=lambda x: x or "—")
        ndoc = c4.text_input("Número de documento", max_chars=25, key="rw_ndoc")
        with st.expander("Leer el aviso de privacidad (Ley 1581 de 2012)"):
            st.markdown(AVISO_PRIVACIDAD)
        acepta = st.checkbox("Autorizo el tratamiento de mis datos personales para gestionar mi reserva, el pago y la comunicación con el hotel, "
                             "conforme al aviso de privacidad (Ley 1581 de 2012). *", key="rw_acepta")
        mkt = st.checkbox("(Opcional) Quiero recibir ofertas del hotel.", key="rw_mkt")
        ok = st.form_submit_button("Continuar al pago", type="primary")
    if ok:
        try:
            rw.completar_datos(numero, token, nombres, apellidos, email, tel, tdoc, ndoc, bool(acepta), bool(mkt))
        except Exception as e:
            _error(e)
        else:
            st.session_state.pop("rw_editar_datos", None)
            st.rerun()
    _boton_cancelar(numero, token)


def _boton_cancelar(numero, token):
    if st.button("Cancelar y liberar la habitación", key="rw_cancelar"):
        try:
            rw.cancelar_bloqueo(numero, token)
        except Exception as e:
            _error(e)
        else:
            _nueva_busqueda()


def _resumen(c: dict):
    with st.container(border=True):
        st.markdown(f"**{c['hotel']}** · {c['tipo']}" + (f" · hab. {c['habitacion']}" if c["habitacion"] else ""))
        st.write(f"{_fecha(c['entrada'])} → {_fecha(c['salida'])} · {c['adultos']} adulto(s)" + (f", {c['ninos']} niño(s)" if c["ninos"] else ""))
        st.write(f"Total: **{fmt_moneda(c['total'], c['moneda'])}** (impuestos incluidos)  ·  Reserva **{c['numero']}**")


# ------------------------------------------------------------------ 3) pago (checkout de la pasarela simulada)
def vista_pago(numero: str, token: str, c: dict):
    encabezado()
    _temporizador(time.time() + c["segundos"])
    _resumen(c)
    st.write(f"A nombre de **{c['huesped']}** · confirmación a {c['correo']}")
    if c["estado"] == "fallida":
        st.warning("El pago anterior fue rechazado. Puedes intentarlo de nuevo mientras tu habitación siga bloqueada.")
    c1, c2 = st.columns(2)
    if c1.button(f"Pagar {fmt_moneda(c['total'], c['moneda'])}", type="primary", key="rw_pagar"):
        try:
            rw.iniciar_pago(numero, token)
        except Exception as e:
            _error(e)
        else:
            _params(numero, token, pago="1")
            st.rerun()
    if c2.button("Editar mis datos", key="rw_editar"):
        st.session_state["rw_editar_datos"] = True
        st.rerun()
    _boton_cancelar(numero, token)


def vista_checkout(numero: str, token: str, c: dict):
    """Pantalla de «la pasarela» (simulada): imita el checkout alojado de Wompi/PayU. Aquí NO se piden datos de tarjeta."""
    try:
        p = rw.iniciar_pago(numero, token)               # reutiliza el intento pendiente
    except Exception as e:
        _error(e)
        return
    pas = pasarela.PasarelaSimulada()
    st.markdown("## 💳 Pasarela de pagos (simulada)")
    st.markdown(f'<div class="rw-prueba">{LEYENDA}</div>', unsafe_allow_html=True)
    _temporizador(time.time() + c["segundos"])
    st.write(f"Comercio: **{c['hotel']}**  \nReferencia: `{p['referencia']}`")
    st.markdown(f"### {fmt_moneda(p['monto'], p['moneda'])}")
    st.caption("En producción aquí el cliente escribiría su tarjeta o elegiría PSE/Nequi en la página de la pasarela. En este prototipo solo "
               "eliges el resultado para probar el flujo; no se procesa ningún dato de pago.")
    b1, b2, b3 = st.columns(3)
    for col, etiqueta, aprobado, clave in ((b1, "✅ Simular pago aprobado", True, "rw_sim_ok"), (b2, "❌ Simular pago rechazado", False, "rw_sim_no")):
        if col.button(etiqueta, key=clave, type="primary" if aprobado else "secondary"):
            ev, firma = pas.evento(p["referencia"], p["monto"], p["moneda"], aprobado)
            try:
                r = rw.procesar_evento(ev, firma)                  # equivale al webhook que enviaría la pasarela
            except Exception as e:
                _error(e)
            else:
                st.session_state["rw_resultado"] = r["resultado"]
                _params(numero, token)
                st.rerun()
    if b3.button("↩ Volver", key="rw_sim_volver"):
        _params(numero, token)
        st.rerun()


# ------------------------------------------------------------------ 4) confirmación / consulta
def vista_final(numero: str, token: str, c: dict):
    encabezado()
    if c["estado"] == "confirmada":
        res = st.session_state.pop("rw_resultado", None)
        if res == "pago_tardio_reubicado":
            st.info("Tu pago llegó cuando el bloqueo había vencido, pero la habitación seguía libre: quedó confirmada.")
        st.success("🎉 ¡Reserva confirmada!")
        st.markdown(f'<div class="rw-numero"><div>NÚMERO DE RESERVA</div><div>{numero}</div></div>', unsafe_allow_html=True)
        _resumen(c)
        st.write(f"Pagado: **{fmt_moneda(c['pagado'], c['moneda'])}** · _" + LEYENDA.lower() + "_")
        enlace = f"{URL_PUBLICA}/?r={numero}&k={token}"
        st.markdown("**Enlace para ver tu reserva:**")
        st.code(enlace, language=None)
        try:
            cr = rw.correo_enviado(numero, token)
        except Exception:
            cr = None
        if cr:
            if cr["estado"] == "enviado":
                st.success(f"📧 Te enviamos la confirmación a {c['correo']}.")
            elif cr["estado"] == "error":
                st.warning("No pudimos enviar el correo, pero tu reserva está confirmada. Guarda tu número de reserva.")
            else:
                st.info(f"📧 **{correo.AVISO_SIMULADO}.** Así se vería el correo que recibirías en {c['correo']}:")
            with st.expander(f"Ver correo: {cr['asunto']}"):
                st.components.v1.html(cr["cuerpo_html"], height=620, scrolling=True)
        if st.button("Hacer otra reserva", key="rw_otra"):
            _nueva_busqueda()
        return
    if c["estado"] in ("expirada", "cancelada"):
        st.warning("⌛ El bloqueo de esta reserva venció." if c["estado"] == "expirada" else "Esta reserva fue cancelada.")
        st.caption("La habitación volvió a estar disponible. Puedes buscar de nuevo.")
    else:
        st.info(c["estado_texto"])
    if st.button("Buscar otra habitación", key="rw_buscar_otra", type="primary"):
        _nueva_busqueda()


# ------------------------------------------------------------------ enrutador
def main():
    numero, token = st.query_params.get("r"), st.query_params.get("k")
    if numero and token:
        try:
            c = rw.consultar(str(numero), str(token))
        except Exception as e:
            encabezado()
            _error(e)
            if st.button("Buscar habitaciones", key="rw_inicio"):
                _nueva_busqueda()
            return
        abierto = c["estado"] in rw.ABIERTOS and c["segundos"] > 0
        if abierto and (not c["con_datos"] or st.session_state.get("rw_editar_datos")):
            return vista_datos(str(numero), str(token), c)
        if abierto and st.query_params.get("pago") == "1":
            return vista_checkout(str(numero), str(token), c)
        if abierto:
            return vista_pago(str(numero), str(token), c)
        return vista_final(str(numero), str(token), c)
    vista_buscar()


try:
    main()
except Exception as _e:                      # nunca se muestra un traceback al público
    _error(_e)

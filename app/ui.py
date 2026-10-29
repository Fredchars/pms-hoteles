"""Utilidades de interfaz compartidas por todas las páginas del PMS piloto."""
from __future__ import annotations

import base64
import datetime as dt
import sys
import traceback
from functools import lru_cache
from pathlib import Path

import streamlit as st

from pms import db, seguridad
from pms.errores import ErrorNegocio
from pms.util import fmt_moneda

PAGINAS: dict = {}
MARCA = "Prototipo diseñado para ATm Consulting"
AVISO = ("🧪 <b>Prototipo con datos 100 % ficticios.</b> Los correos, pagos e integraciones (Booking, Airbnb, pasarelas) están "
         "<b>simulados</b>: no se envía, cobra ni factura nada real. El comprobante PDF <b>no es una factura legal</b>.")
ASSETS = Path(__file__).resolve().parent / "assets"
COLOR_RESERVA = {"consulta": ("#eef2f7", "#52606d"), "opcion": ("#fff4cc", "#7a5b00"), "confirmada": ("#dbeafe", "#1e40af"),
                 "alojado": ("#d1fae5", "#065f46"), "salida": ("#e5e7eb", "#374151"), "cancelada": ("#fee2e2", "#991b1b"),
                 "no_show": ("#fde8d7", "#9a3412"), "bloqueo": ("#f3d1d1", "#7f1d1d")}
COLOR_HK = {"sucia": ("#fee2e2", "#991b1b"), "en_limpieza": ("#fff4cc", "#7a5b00"), "inspeccion": ("#e0e7ff", "#3730a3"),
            "lista": ("#d1fae5", "#065f46"), "fuera_de_servicio": ("#e5e7eb", "#374151")}


@lru_cache(maxsize=1)
def _logo_b64() -> str:
    return base64.b64encode((ASSETS / "atm_logo_pie.png").read_bytes()).decode()


def marca():
    """Logo de ATm Consulting en la barra lateral y pie fijo con la leyenda en todas las páginas."""
    st.logo(str(ASSETS / "atm_logo.png"), size="large", icon_image=str(ASSETS / "atm_logo.png"))
    st.markdown(f"""
<style>
div[data-testid="stMainBlockContainer"] {{padding-bottom:4.5rem}}
.pms-pie {{position:fixed;left:0;right:0;bottom:0;z-index:999;background:rgba(255,255,255,.97);
          border-top:1px solid #d9e2ec;padding:.3rem 1rem;text-align:center;font-size:.85rem;color:#334e68}}
.pms-pie img {{height:22px;vertical-align:middle;margin-right:.45rem}}
</style>
<div class="pms-pie"><img src="data:image/png;base64,{_logo_b64()}" alt="ATm Consulting">{MARCA}</div>""",
                unsafe_allow_html=True)


def estilos():
    st.markdown("""
<style>
.stApp {background:#fff}
.pms-aviso {background:#FFF4E5;border:1px solid #F5A524;border-radius:8px;padding:.45rem .8rem;margin-bottom:.8rem;font-size:.9rem;color:#5c3b00}
.pms-chip {display:inline-block;border-radius:12px;padding:.05rem .6rem;font-size:.8rem;font-weight:600;border:1px solid transparent}
.pms-cal {border-collapse:collapse;font-size:.78rem;width:100%}
.pms-cal th, .pms-cal td {border:1px solid #e4e7eb;padding:.25rem .3rem;text-align:center;white-space:nowrap}
.pms-cal th {background:#f4f6f8;position:sticky;top:0}
.pms-cal td.hab {text-align:left;background:#fafbfc;font-weight:600}
.pms-hk {border:1px solid #e4e7eb;border-radius:10px;padding:.5rem .7rem;margin-bottom:.4rem;background:#fff}
.pms-room {border:2px solid #cbd2d9;border-radius:12px;padding:.55rem .7rem;min-height:8rem;background:#fff;line-height:1.25}
.pms-room .n {font-size:1.25rem;font-weight:700;color:#102a43}
.pms-room .t {font-size:.8rem;color:#334e68}
.pms-room .m {font-size:.78rem;color:#52606d}
.pms-room .p {font-size:.85rem;font-weight:600;color:#102a43;margin-top:.15rem}
.pms-room .e {font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.03em;margin-top:.2rem}
.pms-room-disponible {background:#e8f7ee;border-color:#2f9e60}.pms-room-disponible .e {color:#17693c}
.pms-room-ocupada {background:#fdeaea;border-color:#e08a8a}.pms-room-ocupada .e {color:#9b2c2c}
.pms-room-opcion {background:#fff6d6;border-color:#e0b84a}.pms-room-opcion .e {color:#7a5b00}
.pms-room-bloqueada {background:repeating-linear-gradient(45deg,#f4e3e3,#f4e3e3 6px,#fbf1f1 6px,#fbf1f1 12px);border-color:#b97a7a}.pms-room-bloqueada .e {color:#7f1d1d}
.pms-room-fuera_de_servicio {background:repeating-linear-gradient(45deg,#e4e7eb,#e4e7eb 6px,#f4f6f8 6px,#f4f6f8 12px);border-color:#7b8794}.pms-room-fuera_de_servicio .e {color:#323f4b}
.pms-room-capacidad {background:#f1f3f5;border-color:#d9dee3}.pms-room-capacidad .n,.pms-room-capacidad .t,.pms-room-capacidad .m,.pms-room-capacidad .p {color:#9aa5b1}.pms-room-capacidad .e {color:#7b8794}
.pms-room-seleccionada {background:#dbeafe;border-color:#1a56a8;box-shadow:0 0 0 3px #1a56a833}.pms-room-seleccionada .e {color:#1a56a8}
.pms-leyenda {display:flex;flex-wrap:wrap;gap:.9rem;font-size:.82rem;color:#334e68;margin:.3rem 0 .6rem}
.pms-leyenda i {display:inline-block;width:.9rem;height:.9rem;border-radius:4px;border:2px solid;vertical-align:-2px;margin-right:.3rem}
.pms-mar {background:linear-gradient(90deg,#e6f1fb,#d3e8f9,#e6f1fb);border:1px solid #b6d4ee;border-radius:8px;text-align:center;color:#1a4b7a;font-size:.78rem;letter-spacing:.35em;padding:.2rem;margin:.2rem 0 .5rem}
.pms-pasillo {background:#f4f6f8;border:1px dashed #cbd2d9;border-radius:8px;text-align:center;color:#7b8794;font-size:.72rem;letter-spacing:.2em;padding:.1rem;margin:.5rem 0}
div[data-testid="stMetricValue"] {font-size:1.5rem}
</style>""", unsafe_allow_html=True)


def encabezado(titulo: str, subtitulo: str = ""):
    st.title(titulo)
    st.markdown(f'<div class="pms-aviso">{AVISO}</div>', unsafe_allow_html=True)
    mostrar_flash()
    if subtitulo:
        st.caption(subtitulo)


def chip(texto: str, estado: str, paleta: dict | None = None) -> str:
    fondo, tinta = (paleta or COLOR_RESERVA).get(estado, ("#eef2f7", "#52606d"))
    return f'<span class="pms-chip" style="background:{fondo};color:{tinta};border-color:{tinta}33">{texto}</span>'


# ---------- sesión ----------
def actor() -> dict:
    a = st.session_state["pms_actor"]
    if a.get("debe_cambiar_clave"):        # defensa extra: ninguna página trabaja mientras falte crear la contraseña propia
        st.stop()
    return a


def hotel() -> dict:
    return st.session_state["pms_hotel"]


def hotel_id() -> int:
    return st.session_state["pms_hotel"]["id"]


def dinero(x) -> str:
    return fmt_moneda(x, hotel()["moneda"])


def puede(pantalla: str, editar: bool = False) -> bool:
    return seguridad.puede(actor(), pantalla, editar)


def solo_lectura(pantalla: str) -> bool:
    return not seguridad.puede(actor(), pantalla, True)


# ---------- mensajes ----------
def flash(msg: str, tipo: str = "ok"):
    st.session_state.setdefault("pms_flash", []).append((tipo, msg))


def mostrar_flash():
    for tipo, msg in st.session_state.pop("pms_flash", []):
        (st.success if tipo == "ok" else st.warning)(msg)


def mostrar_error(e: BaseException, accion: str = "") -> None:
    """Error de conexión → mensaje de conexión (sin detalles). Cualquier otro → «Error inesperado (Tipo)» y el traceback completo va a los
    registros (stderr). Nunca se muestra la cadena de conexión."""
    if db.es_error_de_conexion(e):
        # el texto de un error de conexión puede incluir el servidor: solo se registra el tipo
        print(f"[PMS] Error de conexión con la base de datos ({type(e).__name__}) {accion}", file=sys.stderr, flush=True)
        st.error(f"No se pudo conectar con la base de datos ({type(e).__name__}). Revisa el secreto DATABASE_URL y que Supabase esté activo.")
        return
    print(f"[PMS] Error inesperado {accion}:\n" + "".join(traceback.format_exception(type(e), e, e.__traceback__)), file=sys.stderr, flush=True)
    st.error(f"Error inesperado ({type(e).__name__}). Ya quedó registrado; si continúa, avisa a soporte.")


def correr(fn, *args, ok: str = "Listo.", recargar: bool = True, **kw):
    """Ejecuta una operación de negocio; muestra el error en español si falla. Devuelve el resultado o None."""
    try:
        r = fn(*args, **kw)
    except ErrorNegocio as e:
        st.error(str(e))
        return None
    except Exception as e:  # pragma: no cover
        mostrar_error(e, f"en {getattr(fn, '__name__', 'operación')}")
        return None
    flash(ok)
    if recargar:
        st.rerun()
    return True if r is None else r


def enlace(clave: str, etiqueta: str, **kw):
    """Enlace directo a otra pantalla (si el rol la puede ver)."""
    p = PAGINAS.get(clave)
    if p is not None:
        st.page_link(p, label=etiqueta, **kw)


def f_fecha(d) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def nombre_hotel(h: dict) -> str:
    return f"{h['nombre']} · {h['pais']} ({h['moneda']})"

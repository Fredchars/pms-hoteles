"""Utilidades de interfaz compartidas por todas las páginas del PMS piloto."""
from __future__ import annotations

import base64
import datetime as dt
from functools import lru_cache
from pathlib import Path

import streamlit as st

from pms import seguridad
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
    return st.session_state["pms_actor"]


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


def correr(fn, *args, ok: str = "Listo.", recargar: bool = True, **kw):
    """Ejecuta una operación de negocio; muestra el error en español si falla. Devuelve el resultado o None."""
    try:
        r = fn(*args, **kw)
    except ErrorNegocio as e:
        st.error(str(e))
        return None
    except Exception as e:  # pragma: no cover
        st.error(f"Ocurrió un problema inesperado ({type(e).__name__}). Intenta de nuevo; si continúa, avisa a soporte.")
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

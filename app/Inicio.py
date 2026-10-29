"""PMS hotelero · Piloto. Punto de entrada de Streamlit: app/Inicio.py"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
for p in (str(RAIZ), str(RAIZ / "app")):
    if p not in sys.path:
        sys.path.insert(0, p)

import streamlit as st  # noqa: E402

st.set_page_config(page_title="PMS Hotelero · Piloto", page_icon="🏨", layout="wide")

# Secretos de Streamlit -> variables de entorno (el código solo lee el entorno). Nunca se guardan en el repositorio.
for _k in ("DATABASE_URL", "PMS_SESION_SECRETO", "PMS_MODO_DEMO", "PMS_ENTORNO"):
    try:
        if _k in st.secrets and not os.environ.get(_k):
            os.environ[_k] = str(st.secrets[_k])
    except Exception:  # sin secrets.toml
        pass



def _modulos_al_dia():
    """Streamlit Cloud actualiza el código con `git pull` SIN reiniciar el proceso y no recarga la carpeta `pms/` (está fuera de `app/`):
    los módulos viejos quedarían en memoria (p. ej. `pms.seguridad` sin una función nueva → AttributeError). Si algún archivo de `pms/`
    cambió desde que se cargaron, se descartan para que se importen de nuevo."""
    marca = max((f.stat().st_mtime_ns for f in (RAIZ / "pms").glob("*.py")), default=0)
    if getattr(sys, "_pms_marca", None) == marca:
        return
    viejos = [k for k in sys.modules if k in ("pms", "ui") or k.startswith("pms.")]
    if viejos:
        try:
            sys.modules["pms.db"].cerrar_pool()
        except Exception:
            pass
        for k in viejos:
            del sys.modules[k]
    sys._pms_marca = marca


_modulos_al_dia()
import ui  # noqa: E402
from pms import config, db, seguridad  # noqa: E402
from pms.errores import ErrorNegocio  # noqa: E402

ui.estilos()
ui.marca()


def _cerrar_sesion():
    for k in ("pms_actor", "pms_hotel", "pms_hotel_id"):
        st.session_state.pop(k, None)
    st.query_params.clear()


def _entrar(actor: dict):
    st.session_state["pms_actor"] = actor
    st.query_params["s"] = seguridad.token_para(actor)     # recargar la página no cierra la sesión
    st.rerun()


# --- sesión abierta: confirmar en cada ejecución que sigue vigente (usuario activo y contraseña sin cambios) ---
_sesion_cerrada = False
if "pms_actor" in st.session_state:
    try:
        _vigente = seguridad.refrescar_actor(st.session_state["pms_actor"])
    except Exception as _e:
        ui.mostrar_error(_e, "al validar la sesión abierta")
        st.stop()
    if _vigente is None:
        _cerrar_sesion()
        _sesion_cerrada = True
    else:
        st.session_state["pms_actor"] = _vigente

# --- recuperar sesión tras recargar (token firmado en la URL) ---
try:
    if "pms_actor" not in st.session_state:
        _a = seguridad.validar_token(st.query_params.get("s"))
        if _a:
            st.session_state["pms_actor"] = _a
except Exception as _e:
    ui.mostrar_error(_e, "al recuperar la sesión del token")
    st.stop()

# --- pantalla de ingreso ---
if "pms_actor" not in st.session_state:
    st.title("🏨 PMS Hotelero · Piloto")
    st.markdown(f'<div class="pms-aviso">{ui.AVISO}</div>', unsafe_allow_html=True)
    if _sesion_cerrada:
        st.info("Tu sesión se cerró porque tu contraseña cambió o tu usuario fue desactivado. Ingresa de nuevo.")
    c1, c2 = st.columns([1, 1])
    with c1:
        with st.form("pms_form_ingreso"):
            st.subheader("Ingresar")
            email = st.text_input("Correo", key="pms_ingreso_correo")
            clave = st.text_input("Contraseña", type="password", key="pms_ingreso_clave")
            ok = st.form_submit_button("Entrar", type="primary")
        if ok:
            try:
                _entrar(seguridad.iniciar_sesion(email, clave))
            except ErrorNegocio as e:
                st.error(str(e))
            except Exception as e:
                ui.mostrar_error(e, "al iniciar sesión")
        st.caption("Si olvidaste tu contraseña, pide a un administrador que la cambie.")
    with c2:
        if seguridad.demo_permitido():
            st.subheader("Acceso rápido de demostración")
            st.warning("Modo demo ACTIVO: cualquiera puede entrar sin contraseña. Es solo para pruebas con datos ficticios "
                       "y debe estar apagado (PMS_MODO_DEMO=no) en producción.")
            us = db.todos("select u.id, u.nombre, u.rol, h.nombre hotel from pms_usuarios u left join pms_hoteles h on h.id=u.hotel_id "
                          "where u.activo order by h.nombre nulls first, u.rol, u.email")
            elegido = st.selectbox("Entrar como", us, key="pms_demo_usuario",
                                   format_func=lambda u: f"{seguridad.ROL_NOMBRE[u['rol']]} · {u['nombre']} · {u['hotel'] or 'todos los hoteles'}")
            if st.button("Entrar en modo demo", key="pms_demo_entrar"):
                _entrar(seguridad.entrar_demo(elegido["id"]))
        else:
            st.info("El acceso de demostración está apagado. Usa tu correo y contraseña.")
    st.stop()

# --- sesión iniciada ---
A = st.session_state["pms_actor"]

# --- primer ingreso / contraseña temporal: solo se muestra esta pantalla; no se construye la navegación, así que ninguna otra página es accesible ---
if A.get("debe_cambiar_clave"):
    st.query_params["s"] = seguridad.token_para(A)      # recargar mantiene la sesión (y esta misma pantalla)
    st.title("🔑 Crea tu contraseña nueva")
    st.markdown(f"Hola **{A['nombre']}**. Por seguridad, antes de usar el sistema debes crear tu propia contraseña. "
                f"Debe tener **al menos {seguridad.MIN_CLAVE_NUEVA} caracteres** y ser distinta de la temporal que recibiste.")
    with st.form("pms_form_clave_nueva"):
        n1 = st.text_input("Contraseña nueva", type="password", key="pms_cn_1")
        n2 = st.text_input("Confirma la contraseña nueva", type="password", key="pms_cn_2")
        guardar = st.form_submit_button("Guardar y entrar", type="primary")
    if guardar:
        try:
            st.session_state["pms_actor"] = seguridad.crear_clave_propia(A, n1, n2)
        except ErrorNegocio as e:
            st.error(str(e))
        except Exception as e:
            ui.mostrar_error(e, "al crear la contraseña propia")
        else:
            st.session_state.pop("pms_cn_1", None)
            st.session_state.pop("pms_cn_2", None)
            ui.flash("Contraseña creada. ¡Bienvenido!")
            st.rerun()
    if st.button("Cerrar sesión", key="pms_cn_salir"):
        _cerrar_sesion()
        st.rerun()
    st.stop()
try:
    hoteles = config.hoteles_visibles(A)
except Exception as e:
    ui.mostrar_error(e, "al leer los hoteles")
    st.stop()
if not hoteles:
    st.warning("No hay hoteles disponibles para este usuario.")
    st.stop()

with st.sidebar:
    st.markdown(f"**{A['nombre']}**  \n{seguridad.ROL_NOMBRE[A['rol']]}")
    ids = [h["id"] for h in hoteles]
    actual = st.session_state.get("pms_hotel_id", ids[0])
    sel = st.selectbox("Hotel", ids, index=ids.index(actual) if actual in ids else 0, key="pms_w_hotel",
                       format_func=lambda i: ui.nombre_hotel(next(h for h in hoteles if h["id"] == i)),
                       disabled=len(ids) == 1)
    st.session_state["pms_hotel_id"] = sel
    st.session_state["pms_hotel"] = next(h for h in hoteles if h["id"] == sel)
    if st.button("Cerrar sesión", key="pms_cerrar_sesion"):
        _cerrar_sesion()
        st.rerun()
    st.caption("Datos ficticios · correos, pagos e integraciones simulados")

st.query_params["s"] = seguridad.token_para(A)         # se conserva al cambiar de página

D = "paginas"
DEF = [  # (clave, archivo, título, ícono, pantalla de permisos)
    ("dashboard", "dashboard.py", "Dashboard del día", "📊", "dashboard"),
    ("calendario", "calendario.py", "Calendario", "🗓️", "calendario"),
    ("plano", "plano.py", "Plano de habitaciones", "🗺️", "plano"),
    ("reservas", "reservas.py", "Reservas", "📝", "reservas"),
    ("reservas_web", "reservas_web.py", "Reservas web", "🌐", "reservas"),
    ("huespedes", "huespedes.py", "Huéspedes", "🧑‍🤝‍🧑", "huespedes"),
    ("housekeeping", "housekeeping.py", "Housekeeping", "🧹", "housekeeping"),
    ("bloqueos", "bloqueos.py", "Bloqueos", "🚧", "bloqueos"),
    ("tarifas", "tarifas.py", "Tarifas", "💲", "tarifas"),
    ("facturacion", "facturacion.py", "Facturación", "🧾", "facturacion"),
    ("reportes", "reportes.py", "Reportes", "📈", "reportes"),
    ("configuracion", "configuracion.py", "Configuración", "⚙️", "configuracion"),
    ("auditoria", "auditoria.py", "Auditoría", "🔍", "auditoria"),
]
visibles = [d for d in DEF if seguridad.puede(A, d[4])]
paginas = {}
for i, (clave, archivo, titulo, icono, _) in enumerate(visibles):
    paginas[clave] = st.Page(f"{D}/{archivo}", title=titulo, icon=icono, url_path=clave, default=(i == 0))
ui.PAGINAS.clear()
ui.PAGINAS.update(paginas)
st.navigation(list(paginas.values())).run()

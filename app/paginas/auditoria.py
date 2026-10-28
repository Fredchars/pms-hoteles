import streamlit as st

import ui
from pms import vistas

A, H = ui.actor(), ui.hotel()
ui.encabezado("🔍 Auditoría", "Registro de cambios importantes: quién, cuándo y qué había antes. Solo se agrega; nadie puede editarlo ni borrarlo.")
c1, c2, c3 = st.columns(3)
accion = c1.text_input("Filtrar por acción (ej. crear, checkin)", key="pms_au_accion")
usuario = c2.text_input("Filtrar por correo del usuario", key="pms_au_usuario")
limite = c3.selectbox("Cuántos registros", [100, 300, 1000], index=1, key="pms_au_limite")
filas = vistas.auditoria(A, H["id"], limite, accion, usuario)
st.caption(f"{len(filas)} registro(s), del más reciente al más antiguo.")
st.dataframe([{"Fecha": f["creado"].strftime("%d/%m/%Y %H:%M:%S"), "Usuario": f["usuario_email"] or "—",
               "Acción": f["accion"], "Entidad": f["entidad"], "Id": f["entidad_id"],
               "Antes": str(f["antes"] or "")[:120], "Después": str(f["despues"] or "")[:160]} for f in filas],
             hide_index=True, width="stretch")

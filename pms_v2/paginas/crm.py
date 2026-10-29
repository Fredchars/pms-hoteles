"""Suite v2 · pantalla de fase siguiente: no muestra ni inventa datos."""
import streamlit as st

import ui

ui.encabezado("💬 CRM · Inbox")
st.markdown('<div class="v2-fase"><span class="v2-badge">Fase siguiente</span><p>Bandeja omnicanal (correo, WhatsApp, OTAs) y copiloto IA para responder a huéspedes.</p>'
            '<p>Esta pantalla todavía <b>no está construida</b>: no muestra ni guarda datos. Está planificada en la hoja de fases del proyecto.</p></div>',
            unsafe_allow_html=True)

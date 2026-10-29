"""Suite v2 · pantalla de fase siguiente: no muestra ni inventa datos."""
import streamlit as st

import ui

ui.encabezado("🔌 Integraciones")
st.markdown('<div class="v2-fase"><span class="v2-badge">Fase siguiente</span><p>Channel manager con Booking, Airbnb y Expedia, pasarela de pago real (Wompi en Colombia; Azul o CardNET en República Dominicana) y correo transaccional real.</p>'
            '<p>Esta pantalla todavía <b>no está construida</b>: no muestra ni guarda datos. Está planificada en la hoja de fases del proyecto.</p></div>',
            unsafe_allow_html=True)

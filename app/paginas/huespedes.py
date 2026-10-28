import streamlit as st

import ui
from pms import huespedes
from pms.errores import ErrorNegocio

A, H = ui.actor(), ui.hotel()
ui.encabezado("🧑‍🤝‍🧑 Huéspedes", "Fichas y consentimientos de tratamiento de datos (Ley 1581 de 2012, Colombia). Todos los datos son ficticios.")
EDITA = ui.puede("huespedes", True)
t_buscar, t_nuevo = st.tabs(["🔎 Buscar y ver ficha", "➕ Nuevo huésped"])

with t_buscar:
    q = st.text_input("Buscar por nombre, documento o correo", key="pms_hu_buscar")
    lista = huespedes.buscar(A, H["id"], q)
    st.caption(f"{len(lista)} huésped(es).")
    h = st.selectbox("Huésped", lista, index=None, placeholder="Elige un huésped", key="pms_hu_sel",
                     format_func=lambda x: f"{x['nombres']} {x['apellidos']} · {x['numero_documento'] or 'sin documento'}")
    if h:
        st.subheader(f"{h['nombres']} {h['apellidos']}")
        if h["anonimizado"]:
            st.info("Ficha anonimizada: ya no contiene datos personales.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                nom = st.text_input("Nombres", h["nombres"], key=f"pms_hu_n_{h['id']}", disabled=not EDITA)
                ape = st.text_input("Apellidos", h["apellidos"], key=f"pms_hu_a_{h['id']}", disabled=not EDITA)
                tdoc = st.text_input("Tipo de documento", h["tipo_documento"] or "", key=f"pms_hu_t_{h['id']}", disabled=not EDITA)
                ndoc = st.text_input("Número de documento", h["numero_documento"] or "", key=f"pms_hu_d_{h['id']}", disabled=not EDITA)
            with c2:
                mail = st.text_input("Correo", h["email"] or "", key=f"pms_hu_e_{h['id']}", disabled=not EDITA)
                tel = st.text_input("Teléfono", h["telefono"] or "", key=f"pms_hu_p_{h['id']}", disabled=not EDITA)
                pais = st.text_input("País", h["pais"] or "", key=f"pms_hu_s_{h['id']}", disabled=not EDITA)
            if EDITA and st.button("Guardar cambios", key=f"pms_hu_g_{h['id']}"):
                ui.correr(huespedes.actualizar, A, h["id"], nombres=nom, apellidos=ape, tipo_documento=tdoc, numero_documento=ndoc,
                          email=mail, telefono=tel, pais=pais, ok="Ficha actualizada.")
        st.markdown("#### Consentimientos")
        cons = huespedes.consentimientos(h["id"])
        vigentes = {c["finalidad"] for c in cons if c["aceptado"] and not c["revocado_en"]}
        for fin, (titulo, texto) in huespedes.FINALIDADES.items():
            with st.container(border=True):
                ok = fin in vigentes
                st.markdown(f"{'✅' if ok else '⚪'} **{titulo}** — {'vigente' if ok else 'sin consentimiento'}")
                st.caption(texto)
                if EDITA and not h["anonimizado"]:
                    if ok and st.button("Revocar", key=f"pms_hu_rv_{h['id']}_{fin}"):
                        ui.correr(huespedes.revocar_consentimiento, A, h["id"], fin, ok="Consentimiento revocado.")
                    if not ok and st.button("Registrar que el huésped aceptó", key=f"pms_hu_ac_{h['id']}_{fin}", type="primary"):
                        ui.correr(huespedes.registrar_consentimiento, A, h["id"], fin, ok="Consentimiento registrado con fecha y versión del texto.")
        if cons:
            with st.expander("Historial de consentimientos"):
                st.dataframe([{"Finalidad": c["finalidad"], "Versión": c["version"], "Fecha": c["fecha"].strftime("%d/%m/%Y %H:%M"),
                               "Aceptado": "Sí" if c["aceptado"] else "No",
                               "Revocado": c["revocado_en"].strftime("%d/%m/%Y %H:%M") if c["revocado_en"] else ""} for c in cons],
                             hide_index=True, width="stretch")
        if A["rol"] == "gerencia" and not h["anonimizado"]:
            with st.expander("🗑️ Derecho de supresión (anonimizar) · solo gerencia"):
                st.warning("Borra los datos personales de forma definitiva. No se puede si hay reservas vigentes.")
                if st.checkbox("Entiendo que no se puede deshacer", key=f"pms_hu_ck_{h['id']}") and st.button(
                        "Anonimizar huésped", key=f"pms_hu_an_{h['id']}"):
                    ui.correr(huespedes.anonimizar, A, h["id"], ok="Huésped anonimizado.")

with t_nuevo:
    if not EDITA:
        st.warning("Tu rol no puede crear huéspedes.")
    else:
        with st.form("pms_form_huesped", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nom = c1.text_input("Nombres *", key="pms_nh_nombres")
            ape = c2.text_input("Apellidos *", key="pms_nh_apellidos")
            tdoc = c1.selectbox("Tipo de documento", ["", "CC", "CE", "Pasaporte", "Cédula RD", "DNI", "Otro"], key="pms_nh_tdoc")
            ndoc = c2.text_input("Número de documento", key="pms_nh_ndoc")
            mail = c1.text_input("Correo", key="pms_nh_mail")
            tel = c2.text_input("Teléfono", key="pms_nh_tel")
            pais = c1.text_input("País", key="pms_nh_pais")
            cons = st.checkbox("El huésped aceptó el tratamiento de sus datos para la prestación del servicio (Ley 1581)", key="pms_nh_cons")
            enviar = st.form_submit_button("Crear huésped", type="primary")
        if enviar:
            try:
                nuevo = huespedes.crear(A, H["id"], nom, ape, tdoc, ndoc, mail, tel, pais)
                if cons:
                    huespedes.registrar_consentimiento(A, nuevo, "prestacion_servicio")
                    ui.flash("Huésped creado con consentimiento registrado.")
                else:
                    ui.flash("Huésped creado SIN consentimiento: no podrá reservar hasta registrarlo.", "aviso")
                st.rerun()
            except ErrorNegocio as e:
                st.error(str(e))

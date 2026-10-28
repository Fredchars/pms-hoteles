import streamlit as st

import ui
from pms import config, seguridad

A, H = ui.actor(), ui.hotel()
ui.encabezado("⚙️ Configuración", "Hoteles, impuestos, tipos de habitación, habitaciones y camas, y usuarios.")
EDITA = ui.puede("configuracion", True)
if not EDITA:
    st.info("Tu rol solo puede consultar la configuración. Los cambios los hace un administrador.")
t_h, t_i, t_t, t_hab, t_u = st.tabs(["🏨 Hoteles", "🧮 Impuestos", "🛏️ Tipos de habitación", "🚪 Habitaciones y camas", "👤 Usuarios"])

with t_h:
    hs = config.hoteles_visibles(A)
    st.dataframe([{"Hotel": h["nombre"], "País": h["pais"], "Moneda": h["moneda"], "Zona horaria": h["zona_horaria"]} for h in hs],
                 hide_index=True, width="stretch")
    if EDITA:
        with st.expander("Editar el hotel seleccionado"):
            n = st.text_input("Nombre", H["nombre"], key=f"pms_cf_hn_{H['id']}")
            p = st.text_input("País", H["pais"], key=f"pms_cf_hp_{H['id']}")
            mo = st.text_input("Moneda (3 letras)", H["moneda"], key=f"pms_cf_hm_{H['id']}")
            z = st.text_input("Zona horaria", H["zona_horaria"], key=f"pms_cf_hz_{H['id']}")
            if st.button("Guardar hotel", key=f"pms_cf_hg_{H['id']}"):
                ui.correr(config.actualizar_hotel, A, H["id"], nombre=n, pais=p, moneda=mo, zona_horaria=z, ok="Hotel actualizado.")
        if A.get("hotel_id") is None:
            with st.expander("➕ Crear un hotel nuevo"):
                n = st.text_input("Nombre", key="pms_cf_nn")
                p = st.text_input("País", key="pms_cf_np")
                mo = st.text_input("Moneda (ej. COP, DOP, USD)", key="pms_cf_nm")
                z = st.text_input("Zona horaria", "America/Bogota", key="pms_cf_nz")
                if st.button("Crear hotel", key="pms_cf_nc"):
                    ui.correr(config.crear_hotel, A, n, p, mo, z, ok="Hotel creado.")

with t_i:
    st.caption("Cada hotel define sus propios impuestos (nombre y porcentaje). Un cambio solo afecta reservas nuevas: las existentes conservan los impuestos con los que se crearon.")
    imp = config.impuestos(H["id"], solo_activos=False)
    st.dataframe([{"Impuesto": i["nombre"], "Porcentaje": f"{i['porcentaje']} %", "Activo": "Sí" if i["activo"] else "No"} for i in imp],
                 hide_index=True, width="stretch")
    if EDITA:
        c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
        nom = c1.text_input("Nombre del impuesto", key="pms_cf_in")
        pct = c2.number_input("Porcentaje", 0.0, 100.0, 0.0, step=0.5, key="pms_cf_ip")
        act = c3.checkbox("Activo", True, key="pms_cf_ia")
        c4.write("")
        if c4.button("Guardar", key="pms_cf_ig"):
            ui.correr(config.guardar_impuesto, A, H["id"], nom, pct, act, ok="Impuesto guardado.")

with t_t:
    tipos = config.tipos(H["id"], solo_activos=False)
    st.dataframe([{"Tipo": t["nombre"], "Capacidad": t["capacidad"], "Descripción": t["descripcion"]} for t in tipos], hide_index=True, width="stretch")
    if EDITA:
        c1, c2, c3 = st.columns([3, 1, 3])
        nom = c1.text_input("Nombre del tipo", key="pms_cf_tn")
        cap = c2.number_input("Capacidad", 1, 12, 2, key="pms_cf_tc")
        des = c3.text_input("Descripción", key="pms_cf_td")
        if st.button("Crear tipo", key="pms_cf_tb"):
            ui.correr(config.crear_tipo, A, H["id"], nom, int(cap), des, ok="Tipo creado.")

with t_hab:
    habs = config.habitaciones(H["id"], solo_activas=False)
    camas = config.camas(H["id"])
    por = {}
    for c in camas:
        por.setdefault(c["habitacion_id"], []).append(f"{c['cantidad']} {c['tipo']}" + (f" ({c['ancho_cm']} cm)" if c["ancho_cm"] else ""))
    st.caption("Distribución de prueba provisional (3 pisos × 6 habitaciones). Las camas son información: se vende la habitación, no la cama.")
    st.dataframe([{"Hab.": h["numero"], "Piso": h["planta"], "Tipo": h["tipo"], "Capacidad": h["capacidad"], "m²": h["metros"],
                   "Vista": h["vista"] or "", "Camas": ", ".join(por.get(h["id"], []))} for h in habs], hide_index=True, width="stretch")
    if EDITA:
        with st.expander("➕ Crear una habitación"):
            c1, c2 = st.columns(2)
            num = c1.text_input("Número", key="pms_cf_hbn")
            pl = c2.number_input("Piso", 0, 50, 1, key="pms_cf_hbp")
            tipo = st.selectbox("Tipo", config.tipos(H["id"]), key="pms_cf_hbt", format_func=lambda t: t["nombre"])
            m2 = st.number_input("Metros cuadrados", 0, 500, 20, key="pms_cf_hbm")
            vi = st.text_input("Vista", key="pms_cf_hbv")
            c3, c4, c5 = st.columns(3)
            ct = c3.selectbox("Tipo de cama", config.TIPOS_CAMA, key="pms_cf_hbct")
            ca = c4.number_input("Ancho (cm)", 0, 300, 140, key="pms_cf_hbca")
            cc = c5.number_input("Cantidad", 1, 6, 1, key="pms_cf_hbcc")
            if st.button("Crear habitación", key="pms_cf_hbb"):
                ui.correr(config.crear_habitacion, A, H["id"], num, int(pl), tipo["id"], int(m2) or None, vi, [(ct, int(ca) or None, int(cc))],
                          ok="Habitación creada.")

with t_u:
    us = config.usuarios(A)
    st.dataframe([{"Correo": u["email"], "Nombre": u["nombre"], "Rol": seguridad.ROL_NOMBRE[u["rol"]], "Activo": "Sí" if u["activo"] else "No",
                   "Último acceso": u["ultimo_acceso"].strftime("%d/%m/%Y %H:%M") if u["ultimo_acceso"] else ""} for u in us],
                 hide_index=True, width="stretch")
    if EDITA:
        with st.expander("➕ Crear un usuario"):
            c1, c2 = st.columns(2)
            mail = c1.text_input("Correo", key="pms_cf_ue")
            nom = c2.text_input("Nombre", key="pms_cf_un")
            rol = c1.selectbox("Rol", seguridad.ROLES, key="pms_cf_ur", format_func=lambda r: seguridad.ROL_NOMBRE[r])
            cl = c2.text_input("Contraseña inicial (mínimo 8 caracteres)", type="password", key="pms_cf_uc")
            todos = st.checkbox("Acceso a todos los hoteles (solo administrador)", key="pms_cf_ut")
            if st.button("Crear usuario", key="pms_cf_ub"):
                ui.correr(config.crear_usuario, A, mail, nom, rol, cl, None if todos else H["id"], ok="Usuario creado.")
        with st.expander("🔒 Activar, desactivar o cambiar contraseña"):
            u = st.selectbox("Usuario", us, key="pms_cf_us", format_func=lambda u: f"{u['email']} · {seguridad.ROL_NOMBRE[u['rol']]}")
            c1, c2 = st.columns(2)
            if u and c1.button("Desactivar" if u["activo"] else "Activar", key="pms_cf_ua"):
                ui.correr(config.activar_usuario, A, u["id"], not u["activo"], ok="Usuario actualizado.")
            nueva = c2.text_input("Nueva contraseña", type="password", key="pms_cf_up")
            if u and c2.button("Cambiar contraseña", key="pms_cf_upb"):
                ui.correr(seguridad.cambiar_clave, A, u["id"], nueva, ok="Contraseña cambiada: se cerraron sus sesiones anteriores.")
    st.caption("Las contraseñas se guardan cifradas (bcrypt); nadie, ni el administrador, puede verlas.")

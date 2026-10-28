import datetime as dt

import streamlit as st

import ui
from pms import vistas
from pms.util import hoy_hotel

A, H = ui.actor(), ui.hotel()
ui.encabezado("📈 Reportes de ocupación e ingresos", f"Cifras sin impuestos, en {H['moneda']}. Datos ficticios.")
hoy = hoy_hotel(None, H["id"])
c1, c2 = st.columns(2)
d1 = c1.date_input("Desde", value=hoy - dt.timedelta(days=30), key="pms_rp_desde", format="DD/MM/YYYY")
d2 = c2.date_input("Hasta", value=hoy + dt.timedelta(days=30), key="pms_rp_hasta", format="DD/MM/YYYY")
if d2 < d1:
    st.error("La fecha final debe ser igual o posterior a la inicial.")
    st.stop()
if (d2 - d1).days > 400:
    st.error("Elige un rango de máximo 400 días.")
    st.stop()
df = vistas.reporte_diario(A, H["id"], d1, d2)
r = vistas.resumen_periodo(df)
m = st.columns(4)
m[0].metric("Ocupación del período", f"{r['ocupacion_pct']} %")
m[1].metric("Noches vendidas", f"{r['vendidas']} de {r['vendibles']}")
m[2].metric("Ingreso neto", ui.dinero(r["ingreso_neto"]))
m[3].metric("Tarifa media por noche vendida", ui.dinero(r["alojamiento"] / r["vendidas"]) if r["vendidas"] else "—")
st.caption("Ingreso neto = alojamiento + extras − descuentos aprobados. Vendibles = habitaciones activas menos bloqueadas.")
if not df.empty:
    graf = df.set_index("fecha")
    st.subheader("Ocupación diaria (%)")
    st.line_chart(graf["ocupacion_pct"])
    st.subheader("Ingreso diario de alojamiento")
    st.bar_chart(graf["ingreso_alojamiento"])
    st.subheader("Resumen por mes")
    mes = vistas.ingresos_por_mes(df)
    st.dataframe(mes.rename(columns={"mes": "Mes", "vendidas": "Noches vendidas", "vendibles": "Noches vendibles",
                                     "ingreso_neto": "Ingreso neto", "ocupacion_pct": "Ocupación %"}), hide_index=True, width="stretch")
    export = df.rename(columns={"fecha": "Fecha", "vendibles": "Vendibles", "vendidas": "Vendidas", "ocupacion_pct": "Ocupación %",
                                "ingreso_alojamiento": "Alojamiento", "ingreso_extras": "Extras", "descuentos": "Descuentos",
                                "ingreso_neto": "Ingreso neto"})
    st.download_button("⬇️ Descargar detalle diario (CSV)", export.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"reporte_{H['id']}_{d1}_{d2}.csv", mime="text/csv", key="pms_rp_csv")

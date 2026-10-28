from decimal import Decimal

import pytest

from pms import config, db, facturacion, reservas, tarifas
from pms.errores import ErrorNegocio
from pms.util import fmt_moneda
from tests.conftest import D


def test_precio_congelado_no_cambia_al_subir_la_tarifa(m):
    r = m.reservar(desde=2, noches=2)
    t = db.uno("select id from pms_tarifas where tipo_id=%s", (m.tipo_doble,))
    tarifas.actualizar(m.g1, t["id"], precio=250000)
    assert {n["precio"] for n in reservas.noches_de(r["id"])} == {Decimal("100000.00")}
    assert facturacion.resumen(m.rec, r["id"])["subtotal"] == Decimal("200000.00")
    r2 = m.reservar(desde=10, noches=1)
    assert reservas.noches_de(r2["id"])[0]["precio"] == Decimal("250000.00")


def test_extender_estancia_conserva_precio_viejo_y_cotiza_solo_la_noche_nueva(m):
    r = m.reservar(desde=2, noches=2)
    t = db.uno("select id from pms_tarifas where tipo_id=%s", (m.tipo_doble,))
    tarifas.actualizar(m.g1, t["id"], precio=130000)
    reservas.modificar(m.rec, r["id"], salida=m.hoy + D(days=5))
    precios = sorted(float(n["precio"]) for n in reservas.noches_de(r["id"]))
    assert precios == [100000, 100000, 130000]


def test_impuesto_por_hotel_y_moneda_local(m):
    a = m.reservar(desde=2, noches=2)                                     # COP, 19 %
    from pms import reservas as rv
    b = rv.crear(m.recb, m.B, m.huesped_b, m.tipo_b, m.hoy + D(days=2), m.hoy + D(days=4), 2)   # DOP, 18 % + 10 %
    ra, rb = facturacion.resumen(m.rec, a["id"]), facturacion.resumen(m.recb, b["id"])
    assert ra["subtotal"] == Decimal("200000.00")
    assert [i["monto"] for i in ra["impuestos"]] == [Decimal("38000.00")] and ra["total"] == Decimal("238000.00")
    assert rb["subtotal"] == Decimal("10000.00")
    assert [(i["nombre"], i["monto"]) for i in rb["impuestos"]] == [("Impuesto 1", Decimal("1800.00")), ("Servicio", Decimal("1000.00"))]
    assert rb["total"] == Decimal("12800.00")
    assert fmt_moneda(ra["total"], "COP") == "COP 238.000" and fmt_moneda(rb["total"], "DOP") == "DOP 12.800,00"


def test_cambiar_el_impuesto_no_altera_reservas_existentes_pero_si_las_nuevas(m):
    a = m.reservar(desde=2, noches=1)
    config.guardar_impuesto(m.admin, m.A, "Impuesto genérico", 5)
    assert facturacion.resumen(m.rec, a["id"])["total"] == Decimal("119000.00")      # sigue al 19 %
    b = m.reservar(desde=5, noches=1)
    assert facturacion.resumen(m.rec, b["id"])["total"] == Decimal("105000.00")      # nuevo: 5 %


def test_extra_lleva_impuesto_y_pagos_no_superan_el_saldo(m):
    r = m.reservar(desde=1, noches=1)
    facturacion.agregar_extra(m.rec, r["id"], "Minibar", 2, 10000)
    res = facturacion.resumen(m.rec, r["id"])
    assert res["total"] == Decimal("142800.00")
    with pytest.raises(ErrorNegocio, match="mayor que el saldo"):
        facturacion.registrar_pago(m.rec, r["id"], "efectivo", 200000)
    facturacion.registrar_pago(m.rec, r["id"], "efectivo", 42800)
    assert facturacion.resumen(m.rec, r["id"])["saldo"] == Decimal("100000.00")


def test_tarifa_sin_cruce_cierre_de_ventas_y_estancia_minima(m):
    with pytest.raises(ErrorNegocio, match="se cruzan"):
        tarifas.crear(m.g1, m.A, m.tipo_doble, "Otra", m.hoy, m.hoy + D(days=3), 1)
    t = db.uno("select id from pms_tarifas where tipo_id=%s", (m.tipo_doble,))
    tarifas.actualizar(m.g1, t["id"], estancia_minima=3)
    with pytest.raises(ErrorNegocio, match="estancia mínima"):
        m.reservar(desde=2, noches=2)
    m.reservar(desde=2, noches=3)
    tarifas.actualizar(m.g1, t["id"], estancia_minima=1, cierre_ventas=True)
    with pytest.raises(ErrorNegocio, match="cerradas"):
        m.reservar(desde=20, noches=1)


def test_noche_sin_tarifa_no_se_vende(m):
    db.todos("select 1")
    with db.tx() as cx:
        cx.execute("update pms_tarifas set activo=false where tipo_id=%s", (m.tipo_doble,))
    with pytest.raises(ErrorNegocio, match="No hay tarifa"):
        m.reservar(desde=2, noches=1)


def test_comision_y_neto(m):
    r = m.reservar(desde=2, noches=2, canal="booking", comision_pct=15, referencia_externa="BK-9")
    assert r["comision_monto"] == Decimal("30000.00") and r["neto"] == Decimal("170000.00")


def test_comprobante_pdf_aclara_que_no_es_factura(m):
    r = m.reservar(desde=1, noches=1)
    pdf = facturacion.comprobante_pdf(m.rec, r["id"])
    assert pdf[:4] == b"%PDF"
    import shutil, subprocess, tempfile
    if shutil.which("pdftotext"):
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(pdf); f.flush()
            txt = subprocess.run(["pdftotext", f.name, "-"], capture_output=True, text=True).stdout
        assert "NO ES UNA FACTURA LEGAL" in txt and "COP" in txt and "ATm Consulting" in txt

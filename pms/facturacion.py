"""Facturación simple: cargos y pagos como líneas separadas, impuestos genéricos congelados por línea, descuentos con
aprobación de gerencia y comprobante PDF (NO es una factura legal)."""
from __future__ import annotations

import io
from collections import OrderedDict
from decimal import Decimal

from . import config, db, seguridad
from .auditoria import registrar
from .errores import ErrorNegocio
from .util import dinero, fmt_moneda, hotel_de

AVISO_COMPROBANTE = ("COMPROBANTE INTERNO DE ESTANCIA · NO ES UNA FACTURA LEGAL. Este piloto no emite factura "
                     "electrónica DIAN ni de ningún otro país. Datos ficticios; pagos simulados.")


def _reserva(cx, reserva_id: int) -> dict:
    r = cx.execute("select * from pms_reservas where id=%s", (reserva_id,)).fetchone()
    if not r:
        raise ErrorNegocio("Reserva no encontrada.")
    return r


def resumen_cx(cx, reserva_id: int) -> dict:
    """Líneas, subtotal, impuestos por nombre, total, pagado y saldo. Solo cuentan cargos aprobados y no anulados."""
    r = _reserva(cx, reserva_id)
    cargos = cx.execute("select * from pms_cargos where reserva_id=%s order by noche nulls last, id", (reserva_id,)).fetchall()
    pagos = cx.execute("select * from pms_pagos where reserva_id=%s order by id", (reserva_id,)).fetchall()
    vigentes = [c for c in cargos if c["estado"] == "aprobado" and not c["anulado"]]
    subtotal = sum((c["monto"] for c in vigentes), Decimal("0"))
    imp: "OrderedDict[str, tuple[float, Decimal]]" = OrderedDict()
    for c in vigentes:
        for i in c["impuestos"] or []:
            pct, acum = imp.get(i["nombre"], (i["porcentaje"], Decimal("0")))
            imp[i["nombre"]] = (i["porcentaje"], acum + c["monto"] * Decimal(str(i["porcentaje"])) / Decimal(100))
    impuestos = [{"nombre": n, "porcentaje": p, "monto": dinero(m)} for n, (p, m) in imp.items()]
    total = dinero(subtotal) + sum((i["monto"] for i in impuestos), Decimal("0"))
    pagado = sum((p["monto"] for p in pagos if not p["anulado"]), Decimal("0"))
    return {"reserva": r, "cargos": cargos, "pagos": pagos, "subtotal": dinero(subtotal), "impuestos": impuestos,
            "total": dinero(total), "pagado": dinero(pagado), "saldo": dinero(total - pagado)}


def resumen(actor, reserva_id: int) -> dict:
    seguridad.exigir(actor, "facturacion", editar=False)
    with db.tx() as cx:
        r = _reserva(cx, reserva_id)
        seguridad.exigir_hotel(actor, r["hotel_id"])
        return resumen_cx(cx, reserva_id)


def _bloquear_si_cerrada(r: dict):
    if r["estado"] in ("cancelada", "no_show"):
        raise ErrorNegocio("La reserva está cancelada o fue no-show: no admite más cargos ni pagos.")


def agregar_extra(actor, reserva_id: int, descripcion: str, cantidad, precio_unitario) -> int:
    seguridad.exigir(actor, "facturacion")
    cant, precio = dinero(cantidad), dinero(precio_unitario)
    if cant <= 0 or precio <= 0:
        raise ErrorNegocio("La cantidad y el precio deben ser mayores que cero.")
    if not descripcion.strip():
        raise ErrorNegocio("Escribe una descripción del extra.")
    with db.tx() as cx:
        r = _reserva(cx, reserva_id)
        seguridad.exigir_hotel(actor, r["hotel_id"])
        _bloquear_si_cerrada(r)
        if r["estado"] == "salida":
            raise ErrorNegocio("La estancia ya terminó (check-out): no se pueden agregar cargos.")
        c = cx.execute("insert into pms_cargos (hotel_id, reserva_id, tipo, descripcion, cantidad, precio_unitario, monto, "
                       "impuestos, solicitado_por) values (%s,%s,'extra',%s,%s,%s,%s,%s,%s) returning id",
                       (r["hotel_id"], reserva_id, descripcion.strip(), cant, precio, dinero(cant * precio),
                        db.Jsonb(config.impuestos_congelados(cx, r["hotel_id"])), actor["id"])).fetchone()
        registrar(cx, actor, "crear", "cargo", c["id"], despues={"extra": descripcion, "monto": dinero(cant * precio)},
                  hotel_id=r["hotel_id"])
        return c["id"]


def anular_cargo(actor, cargo_id: int, motivo: str):
    """Solo gerencia anula un extra. Las noches se liberan con la modificación o cancelación de la reserva."""
    if actor.get("rol") != "gerencia":
        raise seguridad.PermisoDenegado("Solo gerencia puede anular un cargo.")
    with db.tx() as cx:
        c = cx.execute("select * from pms_cargos where id=%s", (cargo_id,)).fetchone()
        if not c or c["tipo"] != "extra" or c["anulado"]:
            raise ErrorNegocio("Solo se pueden anular cargos extra vigentes.")
        seguridad.exigir_hotel(actor, c["hotel_id"])
        if not motivo.strip():
            raise ErrorNegocio("Escribe el motivo de la anulación.")
        cx.execute("update pms_cargos set anulado=true, anulado_por=%s, motivo=%s where id=%s", (actor["id"], motivo, cargo_id))
        registrar(cx, actor, "anular", "cargo", cargo_id, antes={"monto": c["monto"]}, despues={"motivo": motivo},
                  hotel_id=c["hotel_id"])


def solicitar_descuento(actor, reserva_id: int, porcentaje, motivo: str) -> int:
    """Crea un descuento PENDIENTE (porcentaje sobre noches y extras). No cuenta hasta que gerencia lo apruebe."""
    seguridad.exigir(actor, "facturacion")
    try:
        p = Decimal(str(porcentaje))
    except Exception:
        raise ErrorNegocio("El porcentaje no es válido.")
    if p <= 0 or p > 100:
        raise ErrorNegocio("El descuento debe ser mayor que 0 y no más de 100 %.")
    if not motivo.strip():
        raise ErrorNegocio("Escribe el motivo del descuento.")
    with db.tx() as cx:
        r = _reserva(cx, reserva_id)
        seguridad.exigir_hotel(actor, r["hotel_id"])
        _bloquear_si_cerrada(r)
        base = cx.execute("select coalesce(sum(monto),0) b from pms_cargos where reserva_id=%s and tipo in ('noche','extra') "
                          "and estado='aprobado' and not anulado", (reserva_id,)).fetchone()["b"]
        if base <= 0:
            raise ErrorNegocio("La reserva no tiene cargos sobre los que aplicar un descuento.")
        monto = -dinero(Decimal(base) * p / 100)
        ya = cx.execute("select coalesce(sum(-monto),0) d from pms_cargos where reserva_id=%s and tipo='descuento' and "
                        "estado in ('aprobado','pendiente') and not anulado", (reserva_id,)).fetchone()["d"]
        if ya + (-monto) > base:
            raise ErrorNegocio("Los descuentos no pueden superar el valor de los cargos.")
        imp = cx.execute("select impuestos from pms_cargos where reserva_id=%s and tipo='noche' order by id limit 1",
                         (reserva_id,)).fetchone()
        impuestos = imp["impuestos"] if imp else config.impuestos_congelados(cx, r["hotel_id"])
        c = cx.execute("insert into pms_cargos (hotel_id, reserva_id, tipo, descripcion, cantidad, precio_unitario, monto, "
                       "impuestos, estado, solicitado_por, motivo) values (%s,%s,'descuento',%s,1,%s,%s,%s,'pendiente',%s,%s) "
                       "returning id", (r["hotel_id"], reserva_id, f"Descuento {p.normalize():f} %", monto, monto,
                                        db.Jsonb(impuestos), actor["id"], motivo.strip())).fetchone()
        registrar(cx, actor, "solicitar_descuento", "cargo", c["id"], despues={"porcentaje": p, "monto": monto, "motivo": motivo},
                  hotel_id=r["hotel_id"])
        return c["id"]


def resolver_descuento(actor, cargo_id: int, aprobar: bool, comentario: str = ""):
    with db.tx() as cx:
        c = cx.execute("select * from pms_cargos where id=%s for update", (cargo_id,)).fetchone()
        if not c or c["tipo"] != "descuento":
            raise ErrorNegocio("Descuento no encontrado.")
        seguridad.exigir_hotel(actor, c["hotel_id"])
        seguridad.exigir_aprobador(actor, c["solicitado_por"])
        if c["estado"] != "pendiente":
            raise ErrorNegocio("Este descuento ya fue resuelto.")
        nuevo = "aprobado" if aprobar else "rechazado"
        cx.execute("update pms_cargos set estado=%s, aprobado_por=%s, resuelto_en=now(), motivo=coalesce(motivo,'') || %s where id=%s",
                   (nuevo, actor["id"], f" · Resolución: {comentario}" if comentario else "", cargo_id))
        registrar(cx, actor, "aprobar_descuento" if aprobar else "rechazar_descuento", "cargo", cargo_id,
                  antes={"estado": "pendiente"}, despues={"estado": nuevo, "comentario": comentario}, hotel_id=c["hotel_id"])


def descuentos_pendientes(hotel_id: int) -> list[dict]:
    return db.todos("select c.*, r.codigo, u.nombre solicitante from pms_cargos c join pms_reservas r on r.id=c.reserva_id "
                    "left join pms_usuarios u on u.id=c.solicitado_por where c.hotel_id=%s and c.tipo='descuento' and "
                    "c.estado='pendiente' and not c.anulado order by c.creado", (hotel_id,))


def registrar_pago(actor, reserva_id: int, metodo: str, monto, referencia: str = "") -> int:
    """Registra un pago manual (efectivo, datáfono o transferencia). El piloto NO procesa pagos reales."""
    seguridad.exigir(actor, "facturacion")
    m = dinero(monto)
    if m <= 0:
        raise ErrorNegocio("El monto del pago debe ser mayor que cero.")
    with db.tx() as cx:
        r = _reserva(cx, reserva_id)
        seguridad.exigir_hotel(actor, r["hotel_id"])
        _bloquear_si_cerrada(r)
        res = resumen_cx(cx, reserva_id)
        if m > res["saldo"]:
            raise ErrorNegocio(f"El pago ({m}) es mayor que el saldo pendiente ({res['saldo']}).")
        p = cx.execute("insert into pms_pagos (hotel_id, reserva_id, metodo, monto, referencia, creado_por) values "
                       "(%s,%s,%s,%s,%s,%s) returning id", (r["hotel_id"], reserva_id, metodo, m, referencia or None,
                                                             actor["id"])).fetchone()
        registrar(cx, actor, "crear", "pago", p["id"], despues={"metodo": metodo, "monto": m}, hotel_id=r["hotel_id"])
        return p["id"]


def anular_pago(actor, pago_id: int, motivo: str):
    if actor.get("rol") != "gerencia":
        raise seguridad.PermisoDenegado("Solo gerencia puede anular un pago.")
    with db.tx() as cx:
        p = cx.execute("select * from pms_pagos where id=%s", (pago_id,)).fetchone()
        if not p or p["anulado"]:
            raise ErrorNegocio("Pago no encontrado o ya anulado.")
        seguridad.exigir_hotel(actor, p["hotel_id"])
        if not motivo.strip():
            raise ErrorNegocio("Escribe el motivo de la anulación.")
        cx.execute("update pms_pagos set anulado=true, anulado_por=%s where id=%s", (actor["id"], pago_id))
        registrar(cx, actor, "anular", "pago", pago_id, antes={"monto": p["monto"]}, despues={"motivo": motivo},
                  hotel_id=p["hotel_id"])


def comprobante_pdf(actor, reserva_id: int) -> bytes:
    """Comprobante interno en PDF. Aclara en el encabezado y el pie que NO es una factura legal."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from pathlib import Path

    seguridad.exigir(actor, "facturacion", editar=False)
    with db.tx() as cx:
        r0 = _reserva(cx, reserva_id)
        seguridad.exigir_hotel(actor, r0["hotel_id"])
        res = resumen_cx(cx, reserva_id)
        hotel = hotel_de(cx, r0["hotel_id"])
        hu = cx.execute("select * from pms_huespedes where id=%s", (r0["huesped_id"],)).fetchone()
        tipo = cx.execute("select nombre from pms_tipos_habitacion where id=%s", (r0["tipo_id"],)).fetchone()
        habs = cx.execute("select distinct h.numero from pms_reserva_noches n join pms_habitaciones h on h.id=n.habitacion_id "
                          "where n.reserva_id=%s and n.activa order by 1", (reserva_id,)).fetchall()
        registrar(cx, actor, "descargar_comprobante", "reserva", reserva_id, hotel_id=r0["hotel_id"])
    mon = hotel["moneda"]
    ss = getSampleStyleSheet()
    chico = ParagraphStyle("c", parent=ss["Normal"], fontSize=8, textColor=colors.HexColor("#52606d"))
    aviso = ParagraphStyle("a", parent=ss["Normal"], fontSize=9, textColor=colors.HexColor("#8c1d18"), leading=12)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.6 * cm, bottomMargin=1.6 * cm,
                            title=f"Comprobante {r0['codigo']}")
    logo = Path(__file__).resolve().parent.parent / "app" / "assets" / "atm_logo.png"
    el = []
    if logo.exists():
        el.append(Image(str(logo), width=3.2 * cm, height=3.2 * cm * 409 / 895))
    el += [Spacer(1, 6), Paragraph(f"<b>{hotel['nombre']}</b> · {hotel['pais']} · Moneda: {mon}", ss["Heading3"]),
           Paragraph(f"Comprobante de estancia · Reserva <b>{r0['codigo']}</b>", ss["Heading2"]),
           Paragraph(AVISO_COMPROBANTE, aviso), Spacer(1, 8),
           Paragraph(f"Huésped: {hu['nombres']} {hu['apellidos']} (dato ficticio) · Tipo: {tipo['nombre']} · "
                     f"Habitación(es): {', '.join(h['numero'] for h in habs) or 'sin asignar'}<br/>"
                     f"Entrada: {r0['fecha_entrada']:%d/%m/%Y} · Salida: {r0['fecha_salida']:%d/%m/%Y} · Estado: {r0['estado']}",
                     ss["Normal"]), Spacer(1, 10)]
    filas = [["Descripción", "Fecha", "Cant.", "Valor"]]
    for c in res["cargos"]:
        if c["anulado"] or c["estado"] != "aprobado":
            continue
        filas.append([c["descripcion"], f"{c['noche']:%d/%m/%Y}" if c["noche"] else "", f"{c['cantidad']:g}",
                      fmt_moneda(c["monto"], mon)])
    filas.append(["Subtotal", "", "", fmt_moneda(res["subtotal"], mon)])
    for i in res["impuestos"]:
        filas.append([f"{i['nombre']} ({i['porcentaje']:g} %) · impuesto genérico del hotel", "", "", fmt_moneda(i["monto"], mon)])
    filas.append(["TOTAL", "", "", fmt_moneda(res["total"], mon)])
    t = Table(filas, colWidths=[8.6 * cm, 2.6 * cm, 1.6 * cm, 4.2 * cm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                           ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8d1dc")), ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                           ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]))
    el += [t, Spacer(1, 10), Paragraph("<b>Pagos registrados</b> (simulados)", ss["Normal"])]
    pf = [["Método", "Referencia", "Valor"]] + [[p["metodo"], p["referencia"] or "", fmt_moneda(p["monto"], mon)]
                                                 for p in res["pagos"] if not p["anulado"]]
    pf.append(["Saldo pendiente", "", fmt_moneda(res["saldo"], mon)])
    t2 = Table(pf, colWidths=[5 * cm, 7 * cm, 5 * cm])
    t2.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8.5), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8d1dc")),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")), ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]))
    el += [t2, Spacer(1, 14), Paragraph(AVISO_COMPROBANTE, aviso), Spacer(1, 4),
           Paragraph("Prototipo diseñado para ATm Consulting", chico)]
    doc.build(el)
    return buf.getvalue()

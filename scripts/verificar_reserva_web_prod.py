"""Prueba de punta a punta de la reserva web contra la base REAL (Supabase), con datos ficticios, y limpieza posterior.
Se ejecuta desde GitHub Actions (workflow «Verificar reserva web»). No toca datos del piloto: usa fechas lejanas, un huésped
@prueba-web.invalid, y al final borra SOLO lo que creó (por número de reserva). pms_auditoria es de solo agregar por diseño: sus filas
quedan. No imprime secretos. Sale con código 1 si algo falla."""
import datetime as dt
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pms import db, pasarela, reserva_web as rw, vencimientos  # noqa: E402

fallos = []
creadas: list[str] = []


def ok(cond, msg):
    print(("OK   " if cond else "FALLA") + " " + msg)
    if not cond:
        fallos.append(msg)



def foto_piloto():
    """Conteos de lo que NO es de esta prueba: debe ser idéntico antes y después."""
    return {t: db.uno(f"select count(*) n from {t}")["n"] for t in
            ("pms_hoteles", "pms_habitaciones", "pms_tarifas", "pms_usuarios")} | {
        "reservas_no_web": db.uno("select count(*) n from pms_reservas where canal <> 'web'")["n"],
        "huespedes_no_prueba": db.uno("select count(*) n from pms_huespedes where coalesce(email,'') not like '%%@prueba-web.invalid' "
                                      "and not (nombres='Cliente web' and pais='WEB')")["n"],
        "pagos_no_web": db.uno("select count(*) n from pms_pagos p join pms_reservas r on r.id=p.reserva_id where r.canal <> 'web'")["n"]}


def ventana(hotel_id):
    """Busca unas fechas lejanas (150-340 días) con un tipo de habitación libre y con tarifa."""
    hoy = dt.date.today()
    for off in range(150, 340, 3):
        e, s = hoy + dt.timedelta(days=off), hoy + dt.timedelta(days=off + 2)
        r = rw.buscar(hotel_id, e, s, 2, 0)
        for t in r["tipos"]:
            if t["cotizacion"] and t["libres"] >= 2 and t["capacidad"] >= 2:
                return e, s, t["tipo_id"]
    raise SystemExit("No se encontró una ventana de fechas libre con tarifa para probar")


def limpiar():
    """Borra únicamente lo creado por esta ejecución (por número público) y el huésped de prueba."""
    if not creadas:
        return
    with db.tx() as cx:
        rs = [r["id"] for r in cx.execute("select id from pms_reservas where referencia_externa = any(%s) and canal='web'", (creadas,)).fetchall()]
        ws = [r["id"] for r in cx.execute("select id from pms_reservas_web where numero_publico = any(%s)", (creadas,)).fetchall()]
        refs = [r["referencia"] for r in cx.execute("select referencia from pms_pagos_pasarela where reserva_web_id = any(%s)", (ws,)).fetchall()]
        cx.execute("delete from pms_eventos_pasarela where payload->>'referencia' = any(%s)", (refs,))
        cx.execute("delete from pms_pagos_pasarela where reserva_web_id = any(%s)", (ws,))
        cx.execute("delete from pms_correos where reserva_id = any(%s)", (rs,))
        cx.execute("delete from pms_reservas_web where id = any(%s)", (ws,))
        for t in ("pms_pagos", "pms_cargos", "pms_estancias", "pms_reserva_noches"):
            cx.execute(f"delete from {t} where reserva_id = any(%s)", (rs,))
        gs = [r["huesped_id"] for r in cx.execute("select huesped_id from pms_reservas where id = any(%s)", (rs,)).fetchall()]
        cx.execute("delete from pms_reservas where id = any(%s)", (rs,))
        cx.execute("delete from pms_consentimientos where huesped_id in (select id from pms_huespedes where id = any(%s) and email like '%%@prueba-web.invalid')", (gs,))
        cx.execute("delete from pms_huespedes where id = any(%s) and email like '%%@prueba-web.invalid'", (gs,))
        cx.execute("delete from pms_huespedes h where h.nombres='Cliente web' and h.pais='WEB' and not exists "
                   "(select 1 from pms_reservas r where r.huesped_id=h.id)")


def main():
    if not os.environ.get("DATABASE_URL"):
        sys.exit("Falta DATABASE_URL")
    antes = foto_piloto()
    print("Piloto antes:", antes)
    try:
        hoteles = rw.hoteles_publicos()
        ok(bool(hoteles), f"hay {len(hoteles)} hotel(es) publicados")
        hid = hoteles[0]["id"]
        entrada, salida, tipo = ventana(hid)
        ok(True, f"ventana de prueba {entrada}→{salida} (fechas lejanas)")

        # 1) bloqueo temporal + sin doble venta
        b = rw.crear_bloqueo(hid, tipo, entrada, salida, 2, 0, ip="203.0.113.7")
        creadas.append(b["numero"])
        ok(rw.RE_NUMERO.match(b["numero"]) is not None, "número de reserva legible " + b["numero"])
        fila = db.uno("select estado, canal, opcion_vence_en from pms_reservas where referencia_externa=%s", (b["numero"],))
        ok(fila and fila["estado"] == "opcion" and fila["canal"] == "web" and fila["opcion_vence_en"] is not None, "bloqueo creado: opción, canal web, con vencimiento")

        # 2) datos + consentimiento (sin consentimiento debe fallar)
        try:
            rw.completar_datos(b["numero"], b["token"], "Camila", "Prueba Ficticia", "camila@prueba-web.invalid", acepta_tratamiento=False)
            ok(False, "sin consentimiento NO debe avanzar")
        except Exception:
            ok(True, "sin consentimiento no avanza (Ley 1581)")
        rw.completar_datos(b["numero"], b["token"], "Camila", "Prueba Ficticia", "camila@prueba-web.invalid", telefono="+57 300 000 0000",
                           acepta_tratamiento=True)
        ok(db.uno("select count(*) n from pms_consentimientos c join pms_huespedes h on h.id=c.huesped_id where h.email='camila@prueba-web.invalid'")["n"] >= 1,
           "consentimiento registrado")

        # 3) pago simulado aprobado (con idempotencia y firma inválida)
        p = rw.iniciar_pago(b["numero"], b["token"])
        pas = pasarela.PasarelaSimulada()
        ev, firma = pas.evento(p["referencia"], p["monto"], p["moneda"], True)
        ok(rw.procesar_evento(ev, "0" * 64)["resultado"] == "firma_invalida", "evento con firma falsa rechazado")
        ok(rw.procesar_evento(ev, firma)["resultado"] == "confirmada", "pago aprobado → reserva confirmada")
        ok(rw.procesar_evento(ev, firma)["resultado"] == "duplicado", "el mismo evento dos veces no duplica el pago")
        c = rw.consultar(b["numero"], b["token"])
        ok(c["estado"] == "confirmada", "la consulta pública por enlace muestra «confirmada»")
        d = db.uno("select r.estado, r.canal, (select count(*) from pms_pagos p where p.reserva_id=r.id and not p.anulado) pagos, "
                   "(select coalesce(sum(p.monto),0) from pms_pagos p where p.reserva_id=r.id and not p.anulado) pagado "
                   "from pms_reservas r where r.referencia_externa=%s", (b["numero"],))
        ok(d["estado"] == "confirmada" and d["canal"] == "web" and d["pagos"] == 1, "en el PMS: reserva confirmada, canal web, 1 pago registrado")
        ok(float(d["pagado"]) == float(p["monto"]), "el pago registrado en el PMS coincide con el monto")
        ok(db.uno("select estado from pms_correos where reserva_id=(select id from pms_reservas where referencia_externa=%s)", (b["numero"],))["estado"] == "simulado",
           "correo de confirmación en modo simulado (no se envió nada)")

        # 4) expiración automática
        b2 = rw.crear_bloqueo(hid, tipo, entrada, salida, 2, 0, ip="203.0.113.8")
        creadas.append(b2["numero"])
        with db.tx() as cx:
            cx.execute("update pms_reservas set opcion_vence_en = now() - interval '1 second' where referencia_externa=%s", (b2["numero"],))
        with db.tx() as cx:
            lib = vencimientos.liberar_vencidas(cx)
        ok(any(x.get("web") for x in lib), "el bloqueo vencido se liberó solo")
        ok(db.uno("select estado from pms_reservas_web where numero_publico=%s", (b2["numero"],))["estado"] == "expirada", "estado web «expirada»")
        ok(db.uno("select count(*) n from pms_reserva_noches n join pms_reservas r on r.id=n.reserva_id where r.referencia_externa=%s and n.activa", (b2["numero"],))["n"] == 0,
           "las noches quedaron libres")
        ok(rw.consultar(b2["numero"], b2["token"])["estado"] == "expirada", "el enlace de un bloqueo vencido lo indica")
    finally:
        limpiar()
        despues = foto_piloto()
        print("Piloto después:", despues)
        ok(antes == despues, "limpieza completa: los datos del piloto quedaron idénticos")
        resto = db.uno("select count(*) n from pms_reservas_web where numero_publico = any(%s)", (creadas,))["n"]
        ok(resto == 0, "no quedan reservas web de prueba")
    print("\nRESULTADO:", "TODO OK" if not fallos else f"{len(fallos)} FALLA(S)")
    sys.stdout.flush()
    os._exit(1 if fallos else 0)           # cierra de golpe: el pool de conexiones no termina solo


if __name__ == "__main__":
    main()

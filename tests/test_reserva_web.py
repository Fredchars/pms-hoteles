"""Reserva web (prototipo): bloqueo temporal con vencimiento, doble venta con concurrencia, estados de pago, número único,
consentimiento, correo, visibilidad en el PMS interno y privacidad de la vista pública."""
import hashlib
import threading

import pytest

from pms import correo, db, facturacion, pasarela, reserva_web as rw, reservas, seguridad, vencimientos
from pms.errores import ErrorNegocio
from tests.conftest import D

DATOS = dict(nombres="Camila", apellidos="Prueba", email="camila@prueba-web.invalid", telefono="+57 300 000 0000",
             acepta_tratamiento=True)
PAS = pasarela.PasarelaSimulada()


def bloquear(m, desde=5, noches=2, tipo=None, adultos=2, **kw):
    return rw.crear_bloqueo(m.A, tipo or m.tipo_doble, m.hoy + D(days=desde), m.hoy + D(days=desde + noches), adultos, 0, **kw)


def llegar_a_pago(m, **kw):
    b = bloquear(m, **kw)
    rw.completar_datos(b["numero"], b["token"], **DATOS)
    return b, rw.iniciar_pago(b["numero"], b["token"])


def pagar(ref, monto, aprobado=True, moneda="COP"):
    ev, firma = PAS.evento(ref, monto, moneda, aprobado)
    return ev, firma, rw.procesar_evento(ev, firma)


def vencer(numero):
    with db.tx() as cx:
        cx.execute("update pms_reservas set opcion_vence_en = now() - interval '1 minute' where referencia_externa=%s", (numero,))


# ---------- bloqueo ----------
def test_el_bloqueo_aparta_la_habitacion_15_minutos_en_canal_web(m):
    b = bloquear(m)
    assert rw.RE_NUMERO.match(b["numero"]) and b["numero"].startswith(f"PMS-{m.hoy.year}-")
    r = db.uno("select * from pms_reservas where id=%s", (b["reserva_id"],))
    assert r["estado"] == "opcion" and r["canal"] == "web" and r["referencia_externa"] == b["numero"]
    seg = db.uno("select extract(epoch from (opcion_vence_en - now())) s from pms_reservas where id=%s", (r["id"],))["s"]
    assert 14 * 60 < seg <= 15 * 60
    assert db.uno("select count(*) n from pms_reserva_noches where reserva_id=%s and activa", (r["id"],))["n"] == 2
    w = rw.consultar(b["numero"], b["token"])
    assert w["estado"] == "bloqueada" and 14 * 60 < w["segundos"] <= 15 * 60 and not w["con_datos"] and w["total"] == b["total"]
    with db.tx() as cx:
        assert b["total"] == facturacion.resumen_cx(cx, r["id"])["total"] > 0


def test_el_bloqueo_no_expone_nada_sin_el_token_correcto(m):
    b = bloquear(m)
    for numero, token in [(b["numero"], "x" * 32), (b["numero"], ""), ("PMS-2026-AAAAAA", b["token"]), ("R1-2611-0001", b["token"])]:
        with pytest.raises(ErrorNegocio, match="No encontramos esa reserva"):
            rw.consultar(numero, token)
    assert hashlib.sha256(b["token"].encode()).hexdigest() == db.uno("select token_hash from pms_reservas_web")["token_hash"]


def test_numeros_publicos_unicos_y_no_consecutivos(m):
    nums = set()
    for i in range(12):
        b = rw.crear_bloqueo(m.A, m.tipo_ind, m.hoy + D(days=2 * i + 3), m.hoy + D(days=2 * i + 4), 1, 0)
        nums.add(b["numero"])
    assert len(nums) == 12 and all(rw.RE_NUMERO.match(n) for n in nums)


def test_dos_clientes_no_pueden_bloquear_la_misma_habitacion(m):
    a = bloquear(m, tipo=m.tipo_ind, adultos=1)
    with pytest.raises(ErrorNegocio, match="Ya no hay habitaciones libres|No hay disponibilidad"):
        bloquear(m, tipo=m.tipo_ind, adultos=1)
    assert a["habitacion_id"] == m.h301


def test_el_bloqueo_web_tambien_frena_a_recepcion(m):
    bloquear(m, tipo=m.tipo_ind, adultos=1)
    with pytest.raises(ErrorNegocio, match="No hay disponibilidad"):
        m.reservar(desde=5, noches=2, tipo=m.tipo_ind)


def test_validaciones_de_entrada(m):
    f = m.hoy
    with pytest.raises(ErrorNegocio, match="anterior a hoy"):
        rw.crear_bloqueo(m.A, m.tipo_doble, f - D(days=1), f + D(days=1), 2, 0)
    with pytest.raises(ErrorNegocio, match="posterior"):
        rw.crear_bloqueo(m.A, m.tipo_doble, f + D(days=3), f + D(days=3), 2, 0)
    with pytest.raises(ErrorNegocio, match="Máximo"):
        rw.crear_bloqueo(m.A, m.tipo_doble, f + D(days=3), f + D(days=60), 2, 0)
    with pytest.raises(ErrorNegocio, match="próximo año"):
        rw.crear_bloqueo(m.A, m.tipo_doble, f + D(days=500), f + D(days=502), 2, 0)
    with pytest.raises(ErrorNegocio, match="máximo 2 personas"):
        rw.crear_bloqueo(m.A, m.tipo_doble, f + D(days=3), f + D(days=4), 3, 0)
    with pytest.raises(ErrorNegocio, match="no válido"):
        rw.crear_bloqueo(m.A, m.tipo_doble, f + D(days=3), f + D(days=4), 0, 0)
    with pytest.raises(ErrorNegocio, match="no válido"):
        rw.crear_bloqueo(m.A, m.tipo_b, f + D(days=3), f + D(days=4), 1, 0)           # tipo de OTRO hotel
    with pytest.raises(ErrorNegocio):
        rw.crear_bloqueo(m.A, m.tipo_doble, f + D(days=3), f + D(days=4), 1, 0, habitacion_id=m.hb1)  # habitación de otro hotel


def test_limite_de_bloqueos_por_ip(m):
    for i in range(rw.LIMITE_ACTIVAS_POR_IP):
        rw.crear_bloqueo(m.A, m.tipo_doble, m.hoy + D(days=10 + 3 * i), m.hoy + D(days=11 + 3 * i), 2, 0, ip="203.0.113.7")
    with pytest.raises(ErrorNegocio, match="demasiados bloqueos"):
        rw.crear_bloqueo(m.A, m.tipo_doble, m.hoy + D(days=40), m.hoy + D(days=41), 2, 0, ip="203.0.113.7")
    rw.crear_bloqueo(m.A, m.tipo_doble, m.hoy + D(days=40), m.hoy + D(days=41), 2, 0, ip="203.0.113.8")   # otra IP sí puede
    assert "203.0.113.7" not in str(db.todos("select * from pms_reservas_web"))                              # solo hashes


def test_ventas_web_simultaneas_de_la_ultima_habitacion_solo_una_gana(m):
    resultados = []

    def intento():
        try:
            resultados.append(bloquear(m, desde=7, noches=3, tipo=m.tipo_ind, adultos=1))
        except ErrorNegocio as e:
            resultados.append(e)
    hilos = [threading.Thread(target=intento) for _ in range(8)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert sum(isinstance(r, dict) for r in resultados) == 1
    assert db.uno("select count(*) n from pms_reserva_noches where activa and habitacion_id=%s", (m.h301,))["n"] == 3
    assert db.uno("select count(*) n from (select habitacion_id, noche from pms_reserva_noches where activa group by 1,2 having count(*)>1) x")["n"] == 0


# ---------- vencimiento ----------
def test_bloqueo_vencido_se_libera_y_la_habitacion_vuelve_a_estar_disponible(m):
    b = bloquear(m, tipo=m.tipo_ind, adultos=1)
    vencer(b["numero"])
    # la consulta pública ya no la ve ocupada (liberación perezosa, sin esperar al reloj programado)
    r = rw.buscar(m.A, m.hoy + D(days=5), m.hoy + D(days=7), 1, 0)
    assert any(p["numero"] == "301" and p["libre"] for p in r["plano"])
    w = db.uno("select * from pms_reservas_web")
    assert w["estado"] == "expirada"
    res = db.uno("select * from pms_reservas where id=%s", (w["reserva_id"],))
    assert res["estado"] == "cancelada" and "vencida" in res["cancelacion_motivo"] and res["opcion_vence_en"] is None
    assert db.uno("select count(*) n from pms_reserva_noches where reserva_id=%s and activa", (res["id"],))["n"] == 0
    assert db.uno("select count(*) n from pms_cargos where reserva_id=%s and not anulado", (res["id"],))["n"] == 0
    assert db.uno("select accion from pms_auditoria where accion='vencer_opcion'") is not None
    otra = bloquear(m, tipo=m.tipo_ind, adultos=1)                      # otro cliente ya puede tomarla
    assert otra["habitacion_id"] == m.h301
    with pytest.raises(ErrorNegocio, match="venció"):
        rw.completar_datos(b["numero"], b["token"], **DATOS)
    assert rw.consultar(b["numero"], b["token"])["estado"] == "expirada"


def test_liberar_vencidas_es_idempotente_y_solo_toca_lo_vencido(m):
    a, b = bloquear(m, desde=5), bloquear(m, desde=5)
    vencer(a["numero"])
    with db.tx() as cx:
        assert [x["reserva_id"] for x in vencimientos.liberar_vencidas(cx)] == [a["reserva_id"]]
    with db.tx() as cx:
        assert vencimientos.liberar_vencidas(cx) == []
    assert rw.consultar(b["numero"], b["token"])["estado"] == "bloqueada"


def test_la_opcion_de_recepcion_ahora_vence_a_las_48_horas(m):
    r = m.reservar(desde=3, noches=2, estado="opcion")
    h = db.uno("select extract(epoch from (opcion_vence_en - now()))/3600 h from pms_reservas where id=%s", (r["id"],))["h"]
    assert 47.9 < h <= 48
    conf = m.reservar(desde=10, noches=1, estado="confirmada")
    assert db.uno("select opcion_vence_en from pms_reservas where id=%s", (conf["id"],))["opcion_vence_en"] is None
    with db.tx() as cx:
        cx.execute("update pms_reservas set opcion_vence_en = now() - interval '1 minute' where id=%s", (r["id"],))
    with db.tx() as cx:
        assert [x["reserva_id"] for x in vencimientos.liberar_vencidas(cx)] == [r["id"]]      # la confirmada no se toca
    assert db.uno("select estado from pms_reservas where id=%s", (r["id"],))["estado"] == "cancelada"
    assert db.uno("select estado from pms_reservas where id=%s", (conf["id"],))["estado"] == "confirmada"


def test_confirmar_una_opcion_le_quita_el_vencimiento_y_volver_a_opcion_lo_reinicia(m):
    r = m.reservar(desde=3, noches=2, estado="opcion")
    reservas.modificar(m.rec, r["id"], estado="confirmada")
    assert db.uno("select opcion_vence_en from pms_reservas where id=%s", (r["id"],))["opcion_vence_en"] is None
    reservas.modificar(m.rec, r["id"], estado="opcion")
    assert db.uno("select opcion_vence_en from pms_reservas where id=%s", (r["id"],))["opcion_vence_en"] is not None


def test_las_opciones_antiguas_sin_fecha_no_vencen(m):
    r = m.reservar(desde=3, noches=2, estado="opcion")
    with db.tx() as cx:
        cx.execute("update pms_reservas set opcion_vence_en=null where id=%s", (r["id"],))
        assert vencimientos.liberar_vencidas(cx) == []
    assert db.uno("select estado from pms_reservas where id=%s", (r["id"],))["estado"] == "opcion"


def test_recepcion_no_puede_editar_una_opcion_ya_vencida(m):
    r = m.reservar(desde=3, noches=2, estado="opcion")
    with db.tx() as cx:
        cx.execute("update pms_reservas set opcion_vence_en = now() - interval '1 minute' where id=%s", (r["id"],))
    with pytest.raises(ErrorNegocio, match="no se puede modificar"):
        reservas.modificar(m.rec, r["id"], notas="tarde")


# ---------- datos, consentimiento y pago ----------
def test_sin_consentimiento_no_hay_datos_ni_pago(m):
    b = bloquear(m)
    with pytest.raises(ErrorNegocio, match="Ley 1581"):
        rw.completar_datos(b["numero"], b["token"], **{**DATOS, "acepta_tratamiento": False})
    with pytest.raises(ErrorNegocio, match="Faltan tus datos"):
        rw.iniciar_pago(b["numero"], b["token"])
    assert db.uno("select count(*) n from pms_huespedes where email=%s", (DATOS["email"],))["n"] == 0


def test_validacion_de_datos_del_huesped(m):
    b = bloquear(m)
    for malo in ({"email": "no-es-correo"}, {"nombres": ""}, {"apellidos": "<script>"}, {"telefono": "abc"}, {"nombres": "x" * 100}):
        with pytest.raises(ErrorNegocio):
            rw.completar_datos(b["numero"], b["token"], **{**DATOS, **malo})


def test_los_datos_guardan_huesped_y_consentimientos_con_version(m):
    b = bloquear(m)
    rw.completar_datos(b["numero"], b["token"], **DATOS, acepta_marketing=False)
    g = db.uno("select * from pms_huespedes where email=%s", (DATOS["email"],))
    cs = {c["finalidad"]: c for c in db.todos("select * from pms_consentimientos where huesped_id=%s", (g["id"],))}
    assert set(cs) == {"prestacion_servicio", "facturacion"} and all(c["aceptado"] and c["version"] for c in cs.values())
    assert db.uno("select huesped_id from pms_reservas where id=%s", (b["reserva_id"],))["huesped_id"] == g["id"]
    w = rw.consultar(b["numero"], b["token"])
    assert w["huesped"] == "Camila Prueba" and w["correo"] == "ca***@prueba-web.invalid"
    rw.completar_datos(b["numero"], b["token"], **{**DATOS, "nombres": "Cami"}, acepta_marketing=True)   # corregir datos: no duplica
    assert db.uno("select count(*) n from pms_huespedes where email=%s", (DATOS["email"],))["n"] == 1
    assert db.uno("select count(*) n from pms_consentimientos where finalidad='marketing'")["n"] == 1


def test_limite_de_bloqueos_activos_por_correo(m):
    for i in range(rw.LIMITE_ACTIVAS_POR_CORREO):
        b = bloquear(m, desde=5 + 3 * i)
        rw.completar_datos(b["numero"], b["token"], **DATOS)
    b = bloquear(m, desde=30)
    with pytest.raises(ErrorNegocio, match="bloqueos activos"):
        rw.completar_datos(b["numero"], b["token"], **DATOS)


def test_flujo_completo_bloqueada_pendiente_pagada_confirmada(m):
    b, p = llegar_a_pago(m)
    assert p["proveedor"] == "simulada" and p["monto"] == b["total"] and p["leyenda"] == "MODO PRUEBAS: no se cobra dinero"
    assert rw.consultar(b["numero"], b["token"])["estado"] == "pago_pendiente"
    assert rw.iniciar_pago(b["numero"], b["token"])["referencia"] == p["referencia"]       # pulsar «pagar» dos veces no crea dos cobros
    _, _, res = pagar(p["referencia"], p["monto"])
    assert res == {"resultado": "confirmada", "numero": b["numero"]}
    c = rw.consultar(b["numero"], b["token"])
    assert c["estado"] == "confirmada" and c["pagado"] == c["total"] == b["total"] and c["habitacion"]
    r = db.uno("select * from pms_reservas where id=%s", (b["reserva_id"],))
    assert r["estado"] == "confirmada" and r["opcion_vence_en"] is None and r["canal"] == "web"
    with db.tx() as cx:
        f = facturacion.resumen_cx(cx, r["id"])
    assert f["saldo"] == 0 and f["pagos"][0]["metodo"] == "pasarela"
    assert db.uno("select estado, pago_id from pms_pagos_pasarela")["estado"] == "aprobada"
    acciones = [a["accion"] for a in db.todos("select accion from pms_auditoria order by id")]
    assert acciones.index("pago_web_recibido") < acciones.index("confirmar_web")


def test_el_mismo_evento_dos_veces_se_procesa_una_sola_vez(m):
    b, p = llegar_a_pago(m)
    ev, firma, res = pagar(p["referencia"], p["monto"])
    assert res["resultado"] == "confirmada"
    assert rw.procesar_evento(ev, firma) == {"resultado": "duplicado"}
    ev2, f2 = PAS.evento(p["referencia"], p["monto"], "COP", True)                    # otro evento (otro id) para el mismo cobro
    assert rw.procesar_evento(ev2, f2)["resultado"] == "ya_procesado"
    assert db.uno("select count(*) n from pms_pagos")["n"] == 1


def test_firma_invalida_o_monto_distinto_no_confirman(m):
    b, p = llegar_a_pago(m)
    ev, firma = PAS.evento(p["referencia"], p["monto"], "COP", True)
    assert rw.procesar_evento(ev, "0" * 64) == {"resultado": "firma_invalida"}
    assert rw.procesar_evento({**ev, "monto": "1.00"}, firma) == {"resultado": "firma_invalida"}     # alterado tras firmar
    assert rw.consultar(b["numero"], b["token"])["estado"] == "pago_pendiente"
    _, _, res = pagar(p["referencia"], "1.00")                                                         # firmado bien, pero otro monto
    assert res["resultado"] == "monto_invalido"
    assert rw.consultar(b["numero"], b["token"])["pagado"] == 0
    assert db.uno("select estado from pms_pagos_pasarela")["estado"] == "requiere_revision"
    ev3, f3 = PAS.evento(p["referencia"], p["monto"], "USD", True)
    assert rw.procesar_evento(ev3, f3)["resultado"] == "ya_procesado"
    assert rw.procesar_evento(*PAS.evento("SIM-NOEXISTE", 5, "COP", True))["resultado"] == "referencia_desconocida"
    assert db.uno("select count(*) n from pms_eventos_pasarela where not firma_valida")["n"] == 2


def test_pago_rechazado_permite_reintentar_antes_de_vencer(m):
    b, p = llegar_a_pago(m)
    _, _, res = pagar(p["referencia"], p["monto"], aprobado=False)
    assert res["resultado"] == "rechazada" and rw.consultar(b["numero"], b["token"])["estado"] == "fallida"
    p2 = rw.iniciar_pago(b["numero"], b["token"])
    assert p2["referencia"] != p["referencia"]
    assert pagar(p2["referencia"], p2["monto"])[2]["resultado"] == "confirmada"
    assert db.uno("select count(*) n from pms_pagos")["n"] == 1


def test_pagar_extiende_el_bloqueo_al_menos_5_minutos(m):
    b = bloquear(m)
    rw.completar_datos(b["numero"], b["token"], **DATOS)
    with db.tx() as cx:
        cx.execute("update pms_reservas set opcion_vence_en = now() + interval '30 seconds' where id=%s", (b["reserva_id"],))
    p = rw.iniciar_pago(b["numero"], b["token"])
    assert 4 * 60 < rw.consultar(b["numero"], b["token"])["segundos"] <= 5 * 60 and p["vence_en"]


def test_pago_tardio_con_la_habitacion_libre_reubica_y_confirma(m):
    b, p = llegar_a_pago(m)
    vencer(b["numero"])
    with db.tx() as cx:
        vencimientos.liberar_vencidas(cx)
    assert rw.consultar(b["numero"], b["token"])["estado"] == "expirada"
    assert pagar(p["referencia"], p["monto"])[2]["resultado"] == "pago_tardio_reubicado"
    assert rw.consultar(b["numero"], b["token"])["estado"] == "confirmada"
    assert db.uno("select count(*) n from pms_reserva_noches where reserva_id=%s and activa", (b["reserva_id"],))["n"] == 2


def test_pago_tardio_con_la_habitacion_ya_vendida_queda_para_revision_sin_doble_venta(m):
    b, p = llegar_a_pago(m, tipo=m.tipo_ind, adultos=1)
    vencer(b["numero"])
    with db.tx() as cx:
        vencimientos.liberar_vencidas(cx)
    m.reservar(desde=5, noches=2, tipo=m.tipo_ind)                                    # recepción vendió la habitación mientras tanto
    assert pagar(p["referencia"], p["monto"])[2]["resultado"] == "pago_tardio_sin_reserva"
    assert rw.consultar(b["numero"], b["token"])["estado"] == "expirada"
    assert db.uno("select estado from pms_pagos_pasarela")["estado"] == "requiere_revision"
    assert db.uno("select count(*) n from pms_pagos")["n"] == 0
    assert db.uno("select count(*) n from (select habitacion_id, noche from pms_reserva_noches where activa group by 1,2 having count(*)>1) x")["n"] == 0


def test_el_cliente_puede_cancelar_su_bloqueo_y_libera_al_instante(m):
    b = bloquear(m, tipo=m.tipo_ind, adultos=1)
    rw.cancelar_bloqueo(b["numero"], b["token"])
    assert rw.consultar(b["numero"], b["token"])["estado"] == "cancelada"
    assert bloquear(m, tipo=m.tipo_ind, adultos=1)["habitacion_id"] == m.h301
    with pytest.raises(ErrorNegocio, match="ya no tiene un bloqueo"):
        rw.cancelar_bloqueo(b["numero"], b["token"])


def test_pagos_concurrentes_del_mismo_evento_confirman_una_vez(m):
    b, p = llegar_a_pago(m)
    ev, firma = PAS.evento(p["referencia"], p["monto"], "COP", True)
    out = []
    hilos = [threading.Thread(target=lambda: out.append(rw.procesar_evento(ev, firma)["resultado"])) for _ in range(5)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert sorted(out) == ["confirmada"] + ["duplicado"] * 4
    assert db.uno("select count(*) n from pms_pagos")["n"] == 1


# ---------- correo ----------
def test_correo_simulado_se_guarda_una_vez_con_numero_y_enlace(m, monkeypatch):
    monkeypatch.delenv("PMS_CORREO_PROVEEDOR", raising=False)
    b, p = llegar_a_pago(m)
    pagar(p["referencia"], p["monto"])
    c = rw.correo_enviado(b["numero"], b["token"])
    assert c["estado"] == "simulado" and c["proveedor"] == "simulado" and "no se envió" in c["detalle"]
    assert b["numero"] in c["cuerpo_html"] and b["numero"] in c["asunto"]
    assert f"?r={b['numero']}&amp;k={b['token']}" in c["cuerpo_html"]                       # el enlace «ver mi reserva» lleva el token
    assert "Ley 1581" in c["cuerpo_html"] and "MODO PRUEBAS" in c["cuerpo_html"]
    assert rw._enviar_confirmacion(db.uno("select id from pms_reservas_web")["id"]) is None          # idempotente
    assert db.uno("select count(*) n from pms_correos")["n"] == 1


def test_correo_real_solo_a_direcciones_de_la_lista_blanca(monkeypatch):
    enviados = []
    monkeypatch.setattr(correo, "_http_json", lambda url, cuerpo, cab: enviados.append((url, cuerpo["to"])) or 200)
    monkeypatch.setenv("PMS_CORREO_PROVEEDOR", "resend")
    monkeypatch.setenv("PMS_CORREO_API_KEY", "clave-falsa")
    monkeypatch.setenv("PMS_CORREO_REMITENTE", "reservas@ejemplo.invalid")
    assert correo.enviar("tercero@otro.invalid", "a", "<p>b</p>", "b")["estado"] == "simulado" and not enviados   # sin lista blanca: no sale
    monkeypatch.setenv("PMS_CORREO_PERMITIDOS", "prueba@ejemplo.invalid")
    assert correo.enviar("tercero@otro.invalid", "a", "<p>b</p>", "b")["estado"] == "simulado" and not enviados
    assert correo.enviar("PRUEBA@ejemplo.invalid", "a", "<p>b</p>", "b")["estado"] == "enviado"
    assert enviados == [("https://api.resend.com/emails", ["PRUEBA@ejemplo.invalid"])]
    monkeypatch.setattr(correo, "_http_json", lambda *a: (_ for _ in ()).throw(TimeoutError()))
    assert correo.enviar("prueba@ejemplo.invalid", "a", "<p>b</p>", "b") == {"proveedor": "resend", "estado": "error", "detalle": "TimeoutError"}
    monkeypatch.delenv("PMS_CORREO_API_KEY")
    assert correo.enviar("prueba@ejemplo.invalid", "a", "<p>b</p>", "b")["estado"] == "simulado"


def test_la_plantilla_escapa_html():
    _, html, _ = correo.construir({"hotel": "H", "nombre": "<b>x</b>", "numero": "PMS-2026-ABC234", "entrada": "1", "salida": "2",
                                   "habitacion": "1", "personas": "1", "total": "1", "enlace": "https://x/?r=1&k=2", "pruebas": False})
    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in html and "MODO PRUEBAS" not in html


# ---------- pasarela ----------
def test_wompi_verifica_el_checksum_sha256_de_sus_eventos(monkeypatch):
    monkeypatch.setenv("WOMPI_EVENTOS_SECRETO", "secreto-de-eventos")
    w = pasarela.PasarelaWompi()
    data = {"transaction": {"id": "123-abc", "status": "APPROVED", "amount_in_cents": 4950000, "reference": "ATM-1", "currency": "COP"}}
    props = ["transaction.id", "transaction.status", "transaction.amount_in_cents"]
    cs = hashlib.sha256(("123-abc" + "APPROVED" + "4950000" + "1700000000" + "secreto-de-eventos").encode()).hexdigest()
    crudo = {"event": "transaction.updated", "data": data, "timestamp": 1700000000, "signature": {"properties": props, "checksum": cs}}
    assert w.verificar_evento(crudo) and not w.verificar_evento({**crudo, "timestamp": 1})
    n = w.normalizar(crudo)
    assert n["tipo"] == "pago.aprobado" and n["monto"] == "49500.00" and n["referencia"] == "ATM-1"
    monkeypatch.delenv("WOMPI_EVENTOS_SECRETO")
    assert not pasarela.PasarelaWompi().verificar_evento(crudo)


# ---------- lo que ve el PMS interno ----------
def test_el_pms_interno_ve_la_reserva_web_su_pago_y_su_estado(m):
    b, p = llegar_a_pago(m)
    f = rw.listar_web(m.rec, m.A)
    assert len(f) == 1 and f[0]["numero_publico"] == b["numero"] and f[0]["estado"] == "pago_pendiente" and f[0]["pago_estado"] == "pendiente"
    assert f[0]["huesped"] == "Camila Prueba"
    pagar(p["referencia"], p["monto"])
    f = rw.listar_web(m.rec, m.A)[0]
    assert f["estado"] == "confirmada" and f["pagado"] == f["monto_total"] and f["correo_estado"] == "simulado" and f["pago_estado"] == "aprobada"
    lst = reservas.listar(m.rec, m.A)
    assert any(r["canal"] == "web" and r["estado"] == "confirmada" for r in lst)
    with pytest.raises(seguridad.PermisoDenegado):
        rw.listar_web(m.recb, m.A)                                                     # recepción de otro hotel no ve estas reservas
    with pytest.raises(seguridad.PermisoDenegado):
        rw.listar_web(m.hk1, m.A)                                                      # housekeeping no tiene la pantalla de reservas


def test_busqueda_publica_no_filtra_datos_internos(m):
    m.reservar(desde=5, noches=2, estado="confirmada")
    bloquear(m, desde=5)
    r = rw.buscar(m.A, m.hoy + D(days=5), m.hoy + D(days=7), 2, 0)
    assert set(r) == {"hotel", "noches", "tipos", "plano"}
    for h in r["plano"]:
        assert set(h) == {"habitacion_id", "numero", "planta", "tipo_id", "tipo", "metros", "vista", "libre", "total"}
    assert not any(p["libre"] for p in r["plano"] if p["tipo"] == "Doble")                 # las 2 dobles: una vendida, otra bloqueada
    assert "Ana" not in str(r) and "ficticia" not in str(r).lower()
    assert {h["id"] for h in rw.hoteles_publicos()} == {m.A, m.B}


def test_tablas_nuevas_con_rls_sin_politicas_ni_acceso_publico(m):
    nuevas = ("pms_reservas_web", "pms_pagos_pasarela", "pms_eventos_pasarela", "pms_correos")
    for t in nuevas:
        f = db.uno("select relrowsecurity r from pg_class where relname=%s", (t,))
        assert f and f["r"]
        assert db.uno("select count(*) n from pg_policies where tablename=%s", (t,))["n"] == 0

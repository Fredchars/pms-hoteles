"""Datos de prueba 100 % ficticios: 3 hoteles (Colombia COP, República Dominicana DOP, otro país PEN), cada uno con el
layout provisional de 18 habitaciones (3 plantas × 6), usuarios por rol, huéspedes inventados y reservas en todos los estados.
Uso:  python -m pms.semilla [--reiniciar]
Las contraseñas de prueba se generan al azar, se guardan con hash y se escriben SOLO en un archivo (nunca se imprimen)."""
from __future__ import annotations

import datetime as dt
import json
import os
import random
import secrets
import sys
from pathlib import Path

from . import bloqueos, config, db, facturacion, housekeeping, huespedes, reservas, tarifas
from .errores import ErrorNegocio
from .seguridad import actor_de, hash_clave
from .util import hoy_hotel

TABLAS = ["pms_auditoria", "pms_pagos", "pms_cargos", "pms_housekeeping", "pms_bloqueos", "pms_estancias", "pms_reserva_noches",
          "pms_reservas", "pms_consentimientos", "pms_huespedes", "pms_tarifas", "pms_camas", "pms_habitaciones",
          "pms_tipos_habitacion", "pms_usuarios", "pms_impuestos", "pms_hoteles"]

# Layout de prueba PROVISIONAL (plano de la maqueta V1.1): 3 plantas × 6 habitaciones.
TIPOS = [("Familiar Mar", 4, "Hasta 4 personas, vista al mar"), ("Triple Mar", 3, "Hasta 3 personas, vista al mar"),
         ("Doble matrimonial", 2, "Doble Monte y Doble Patio"), ("Individual", 1, "1 persona")]
HAB_PLANTA = [  # (sufijo, tipo, metros, vista, camas[(tipo, ancho, cant)])
    ("01", "Familiar Mar", 34, "Al mar", [("matrimonial", 150, 2)]),
    ("02", "Triple Mar", 28, "Al mar", [("matrimonial", 150, 1), ("individual", 90, 1)]),
    ("03", "Doble matrimonial", 22, "Interior (Doble Monte)", [("matrimonial", 150, 1)]),
    ("04", "Doble matrimonial", 22, "Interior (Doble Monte)", [("matrimonial", 150, 1)]),
    ("05", "Doble matrimonial", 22, "Interior (Doble Patio)", [("matrimonial", 150, 1)]),
    ("06", "Individual", 14, "Interior", [("individual", 90, 1)]),
]
HOTELES = [
    {"slug": "col", "nombre": "Hotel Brisa Demo (Colombia)", "pais": "Colombia", "moneda": "COP", "tz": "America/Bogota",
     "impuestos": [("Impuesto de ejemplo 1", 19)], "base": {"Familiar Mar": 520000, "Triple Mar": 430000, "Doble matrimonial": 320000, "Individual": 210000}},
    {"slug": "rd", "nombre": "Hotel Palma Demo (República Dominicana)", "pais": "República Dominicana", "moneda": "DOP",
     "tz": "America/Santo_Domingo", "impuestos": [("Impuesto de ejemplo 1", 18), ("Cargo por servicio de ejemplo", 10)],
     "base": {"Familiar Mar": 9500, "Triple Mar": 7800, "Doble matrimonial": 5800, "Individual": 3900}},
    {"slug": "pe", "nombre": "Hotel Mirador Demo (otro país)", "pais": "Perú (ejemplo)", "moneda": "PEN", "tz": "America/Lima",
     "impuestos": [("Impuesto de ejemplo", 18)], "base": {"Familiar Mar": 480, "Triple Mar": 390, "Doble matrimonial": 290, "Individual": 190}},
]
NOMBRES = ["Camila", "Mateo", "Valentina", "Santiago", "Luciana", "Sebastián", "Isabella", "Emiliano", "Renata", "Joaquín",
           "Antonella", "Tomás", "Mariana", "Gael", "Julieta", "Nicolás"]
APELLIDOS = ["Ficticio Alvarado", "Ejemplo Rivas", "Demo Quintero", "Prueba Salazar", "Inventado Mora", "Simulado Ortega",
             "Muestra Duarte", "Falso Cifuentes", "Piloto Barrios", "Sintético Lozano", "Maqueta Acosta", "Borrador Vega",
             "Test Montoya", "Ensayo Peña", "Modelo Castaño", "Boceto Herrera"]
CANALES = [("directo", 0, None), ("telefono", 0, None), ("whatsapp", 0, None), ("booking", 15, "BK"), ("airbnb", 3, "AB"), ("agencia", 10, "AG")]
SALIDA_CLAVES = Path(os.environ.get("PMS_SEED_SALIDA", "/workspace/.secrets/pms_usuarios_prueba.txt"))


def _usuarios_plan():
    plan = [("admin@pms-demo.test", "Administrador ATm (ficticio)", "administrador", None)]
    for h in HOTELES:
        s = h["slug"]
        plan += [(f"gerencia1.{s}@pms-demo.test", f"Gerente 1 {s.upper()} (ficticio)", "gerencia", s),
                 (f"gerencia2.{s}@pms-demo.test", f"Gerente 2 {s.upper()} (ficticio)", "gerencia", s),
                 (f"recepcion1.{s}@pms-demo.test", f"Recepción 1 {s.upper()} (ficticio)", "recepcion", s),
                 (f"recepcion2.{s}@pms-demo.test", f"Recepción 2 {s.upper()} (ficticio)", "recepcion", s),
                 (f"housekeeping1.{s}@pms-demo.test", f"Camarera 1 {s.upper()} (ficticio)", "housekeeping", s),
                 (f"housekeeping2.{s}@pms-demo.test", f"Camarera 2 {s.upper()} (ficticio)", "housekeeping", s)]
    return plan


def _claves_dadas() -> dict:
    try:
        return json.loads(os.environ.get("PMS_SEED_CLAVES", "") or "{}")
    except ValueError:
        return {}


def sembrar(reiniciar: bool = False, guardar_claves: bool = True) -> dict:
    """Crea los datos de prueba. Devuelve {correo: contraseña} (no imprimir). Si ya hay hoteles y no se pide reiniciar, no hace nada."""
    with db.tx() as cx:
        hay = cx.execute("select count(*) n from pms_hoteles").fetchone()["n"]
        if hay and not reiniciar:
            return {}
        if reiniciar:
            cx.execute("truncate " + ", ".join(TABLAS) + " restart identity cascade")
    dadas = _claves_dadas()
    claves = {}
    for email, *_ in _usuarios_plan():
        claves[email] = dadas.get(email) or secrets.token_urlsafe(9)
    # administrador de arranque (fila directa: aún no existe ningún usuario que pueda crearlo)
    with db.tx() as cx:
        u = cx.execute("insert into pms_usuarios (hotel_id, email, nombre, rol, clave_hash) values (null,%s,%s,'administrador',%s) returning *",
                       ("admin@pms-demo.test", "Administrador ATm (ficticio)", hash_clave(claves["admin@pms-demo.test"]))).fetchone()
    admin = actor_de(u)
    ids: dict[str, int] = {}
    rng = random.Random(42)
    for h in HOTELES:
        hid = config.crear_hotel(admin, h["nombre"], h["pais"], h["moneda"], h["tz"])
        ids[h["slug"]] = hid
        for nom, pct in h["impuestos"]:
            config.guardar_impuesto(admin, hid, nom, pct)
        tipo_id = {t[0]: config.crear_tipo(admin, hid, t[0], t[1], t[2]) for t in TIPOS}
        for planta in (1, 2, 3):
            for suf, tipo, m, vista, camas in HAB_PLANTA:
                config.crear_habitacion(admin, hid, f"{planta}{suf}", planta, tipo_id[tipo], m, vista, camas)
        for email, nombre, rol, slug in _usuarios_plan():
            if slug == h["slug"]:
                config.crear_usuario(admin, email, nombre, rol, claves[email], hid)
        _tarifas(admin, hid, h, tipo_id, hoy_hotel(None, hid))
    for h in HOTELES:
        _movimiento(ids[h["slug"]], h, rng)
    if guardar_claves and not dadas:
        SALIDA_CLAVES.parent.mkdir(parents=True, exist_ok=True)
        SALIDA_CLAVES.write_text("# Usuarios de PRUEBA del PMS (datos ficticios). NO subir a Git.\n" + "\n".join(
            f"{e}\t{c}" for e, c in claves.items()) + "\n", encoding="utf-8")
        os.chmod(SALIDA_CLAVES, 0o600)
    return claves


def _tarifas(admin, hid, h, tipo_id, hoy):
    d = dt.timedelta
    for nombre, precio in h["base"].items():
        t = tipo_id[nombre]
        tarifas.crear(admin, hid, t, "Temporada baja", hoy - d(days=240), hoy + d(days=19), precio, 1)
        tarifas.crear(admin, hid, t, "Temporada alta (puente)", hoy + d(days=20), hoy + d(days=49), round(precio * 1.3), 2)
        tarifas.crear(admin, hid, t, "Temporada baja", hoy + d(days=50), hoy + d(days=89), precio, 1)
        tarifas.crear(admin, hid, t, "Cierre por evento privado", hoy + d(days=90), hoy + d(days=92), precio, 1, cierre_ventas=True)
        tarifas.crear(admin, hid, t, "Temporada baja", hoy + d(days=93), hoy + d(days=500), precio, 1)


def _movimiento(hid, h, rng):
    with db.tx() as cx:
        us = {r["email"]: actor_de(r) for r in cx.execute("select * from pms_usuarios where hotel_id=%s", (hid,)).fetchall()}
        hoy = hoy_hotel(cx, hid)
        tipos = {t["nombre"]: t for t in cx.execute("select * from pms_tipos_habitacion where hotel_id=%s", (hid,)).fetchall()}
        habs = cx.execute("select * from pms_habitaciones where hotel_id=%s order by numero", (hid,)).fetchall()
    s = h["slug"]
    g1, g2 = us[f"gerencia1.{s}@pms-demo.test"], us[f"gerencia2.{s}@pms-demo.test"]
    r1 = us[f"recepcion1.{s}@pms-demo.test"]
    k1, k2 = us[f"housekeeping1.{s}@pms-demo.test"], us[f"housekeeping2.{s}@pms-demo.test"]
    d = dt.timedelta
    # huéspedes ficticios (la última ficha queda SIN consentimiento a propósito, para mostrar esa regla)
    gids = []
    for i in range(14):
        n, a = NOMBRES[(i + len(s)) % len(NOMBRES)], APELLIDOS[(i * 3 + len(s)) % len(APELLIDOS)]
        gid = huespedes.crear(r1, hid, n, a, "DOC-FICTICIO", f"FICT-{s.upper()}-{i + 1:04d}", f"huesped{i + 1}@ejemplo.invalid",
                              f"+00 000 000 {i + 1:04d}", "País de ejemplo")
        if i < 13:
            huespedes.registrar_consentimiento(r1, gid, "prestacion_servicio")
            huespedes.registrar_consentimiento(r1, gid, "facturacion")
            if i % 4 == 0:
                huespedes.registrar_consentimiento(r1, gid, "marketing")
        gids.append(gid)

    def lista(hab_ids):
        with db.tx() as cx:
            cx.execute("update pms_habitaciones set estado_limpieza='lista' where id = any(%s)", (hab_ids,))

    def reserva(tipo, entrada, noches, estado="confirmada", canal=0, adultos=None, **kw):
        t = tipos[tipo]
        cn, com, pref = CANALES[canal]
        ref = f"{pref}-{rng.randint(100000, 999999)}" if pref else None
        return reservas.crear(g1, hid, gids[rng.randrange(13)], t["id"], entrada, entrada + d(days=noches), adultos or min(2, t["capacidad"]),
                              0, estado, cn, com, ref, permitir_pasado=True, hoy=entrada if entrada < hoy else hoy, **kw)

    def pagar(res_id, fraccion=1.0, metodo="datafono"):
        r = facturacion.resumen(g1, res_id)
        monto = round(float(r["saldo"]) * fraccion, 2)
        if monto > 0:
            facturacion.registrar_pago(g1, res_id, metodo, monto, "pago simulado")

    todas = [x["id"] for x in habs]
    # bloqueo por mantenimiento (creado antes de vender): 306 durante 6 días
    hab306 = next(x for x in habs if x["numero"] == "306")
    bloqueos.crear(g1, hid, hab306["id"], hoy + d(days=3), hoy + d(days=8), "Reparación del aire acondicionado (ejemplo)")
    # historial: estancias terminadas en los últimos 60 días
    for _ in range(34):
        tipo = rng.choice(list(tipos))
        ent = hoy - d(days=rng.randint(3, 60))
        noches = rng.randint(1, 4)
        if ent + d(days=noches) > hoy:
            continue
        try:
            r = reserva(tipo, ent, noches, canal=rng.randrange(len(CANALES)))
            lista(todas)
            reservas.checkin(g1, r["id"], hoy=ent)
            if rng.random() < 0.4:
                facturacion.agregar_extra(g1, r["id"], "Minibar y lavandería (ejemplo)", 1, round(h["base"]["Individual"] * 0.2))
            pagar(r["id"])
            reservas.checkout(g1, r["id"], hoy=ent + d(days=noches))
            with db.tx() as cx:  # fechas históricas coherentes
                f = dt.datetime.combine(ent + d(days=noches), dt.time(11, 0), tzinfo=dt.timezone.utc)
                cx.execute("update pms_pagos set creado=%s where reserva_id=%s", (f, r["id"]))
                cx.execute("update pms_estancias set checkin_real=%s, checkout_real=%s where reserva_id=%s",
                           (dt.datetime.combine(ent, dt.time(20, 0), tzinfo=dt.timezone.utc), f, r["id"]))
                cx.execute("update pms_cargos set creado=%s where reserva_id=%s and tipo='extra'", (f, r["id"]))
        except ErrorNegocio:
            continue
    # una cancelación aprobada, un no-show
    r = reserva("Doble matrimonial", hoy - d(days=10), 2)
    reservas.solicitar_cancelacion(r1, r["id"], "El huésped canceló por viaje (ejemplo)")
    reservas.resolver_cancelacion(g2, r["id"], True, "Aprobada")
    r = reserva("Individual", hoy - d(days=6), 1, canal=3)
    reservas.no_show(r1, r["id"], hoy=hoy)
    # ahora: alojados hoy
    lista(todas)
    alojados = []
    for tipo, ent, noches in [("Familiar Mar", hoy - d(days=2), 4), ("Doble matrimonial", hoy - d(days=1), 3), ("Triple Mar", hoy - d(days=3), 3),
                              ("Individual", hoy - d(days=1), 2), ("Doble matrimonial", hoy - d(days=2), 2)]:
        r = reserva(tipo, ent, noches)
        reservas.checkin(g1, r["id"], hoy=ent)
        alojados.append(r)
    pagar(alojados[0]["id"], 0.5, "transferencia")
    pagar(alojados[1]["id"], 1.0, "efectivo")
    facturacion.agregar_extra(g1, alojados[0]["id"], "Desayunos adicionales (ejemplo)", 3, round(h["base"]["Individual"] * 0.08))
    d1 = facturacion.solicitar_descuento(r1, alojados[2]["id"], 10, "Cliente frecuente (ejemplo)")
    facturacion.solicitar_descuento(r1, alojados[0]["id"], 5, "Compensación por ruido (ejemplo)")
    facturacion.resolver_descuento(g2, d1, True, "OK")
    # llegadas de hoy y futuras
    reserva("Triple Mar", hoy, 2, canal=0)
    reserva("Doble matrimonial", hoy, 3, canal=3)
    reserva("Familiar Mar", hoy, 2, canal=5, adultos=4)
    reserva("Individual", hoy, 1, estado="opcion")
    pendiente = reserva("Doble matrimonial", hoy + d(days=2), 3, canal=1)
    reservas.solicitar_cancelacion(r1, pendiente["id"], "El huésped pidió cancelar por correo (ejemplo)")
    for tipo, desp, noches, est, canal in [("Familiar Mar", 4, 3, "confirmada", 4), ("Triple Mar", 5, 2, "confirmada", 3),
                                           ("Doble matrimonial", 7, 4, "confirmada", 0), ("Individual", 6, 2, "opcion", 2),
                                           ("Doble matrimonial", 12, 3, "consulta", 0), ("Familiar Mar", 25, 4, "confirmada", 3),
                                           ("Triple Mar", 30, 3, "confirmada", 0), ("Doble matrimonial", 35, 5, "confirmada", 5),
                                           ("Individual", 40, 3, "confirmada", 1), ("Doble matrimonial", 52, 3, "confirmada", 4)]:
        try:
            reserva(tipo, hoy + d(days=desp), noches, estado=est, canal=canal)
        except ErrorNegocio:
            pass
    # estados de limpieza para la demostración (habitaciones vacías); 106 queda fuera de servicio
    with db.tx() as cx:
        libres = [x["id"] for x in cx.execute(
            "select h.id from pms_habitaciones h where h.hotel_id=%s and h.estado_limpieza='lista' and not exists ("
            "select 1 from pms_reserva_noches n where n.habitacion_id=h.id and n.activa and n.noche=%s) order by h.numero desc",
            (hid, hoy)).fetchall()]
    sucias = libres[:2]
    for x in sucias:
        housekeeping.mover(k1, x, "sucia", "Salida de huésped (ejemplo)")
    if len(libres) > 2:
        housekeeping.mover(k1, libres[2], "sucia")
        housekeeping.mover(k1, libres[2], "en_limpieza")
    if len(libres) > 3:
        housekeeping.mover(k1, libres[3], "sucia")
        housekeeping.mover(k1, libres[3], "en_limpieza")
        housekeeping.mover(k1, libres[3], "inspeccion")
    candidatas = [x for x in habs if x["numero"] == "106"] + [x for x in habs if x["id"] in libres[4:]]
    for hab in candidatas:
        try:
            housekeeping.mover(k2, hab["id"], "fuera_de_servicio", "Fuga en el baño (ejemplo)")
            break
        except ErrorNegocio:
            continue


if __name__ == "__main__":
    reinicio = "--reiniciar" in sys.argv
    c = sembrar(reiniciar=reinicio)
    print(f"Semilla {'aplicada' if c else 'omitida (ya hay datos; use --reiniciar para rehacer)'}"
          + (f": {len(c)} usuarios de prueba. Contraseñas en {SALIDA_CLAVES} (no se imprimen)." if c else ""))
    db.cerrar_pool()

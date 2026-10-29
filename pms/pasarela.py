"""Pasarela de pago de la reserva web: una interfaz y dos adaptadores.

  · `PasarelaSimulada` (la que se usa hoy): NO cobra dinero. Imita el recorrido de una pasarela con «checkout alojado»:
    el PMS pide una referencia, el cliente va a una pantalla de pago y la «pasarela» le avisa al PMS con un evento FIRMADO
    (como un webhook). El PMS comprueba la firma, el monto y la moneda antes de confirmar nada.
  · `PasarelaWompi` (fase 2): la verificación del checksum SHA-256 de los eventos ya está escrita; crear el pago real
    y recibir el webhook necesitan las llaves de Wompi (no incluidas) y un receptor HTTP (ver docs/evaluacion-motor-reservas-web).

Evento normalizado (lo único que entiende el resto del PMS):
  {"id": "...", "tipo": "pago.aprobado" | "pago.rechazado", "referencia": "...", "monto": "123456.00", "moneda": "COP", "timestamp": 1700000000}
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from decimal import Decimal

from .errores import ErrorNegocio

LEYENDA_PRUEBAS = "MODO PRUEBAS: no se cobra dinero"
TIPOS = ("pago.aprobado", "pago.rechazado")


def _secreto() -> bytes:
    s = os.environ.get("PMS_PASARELA_SECRETO", "")
    if not s:
        try:
            import streamlit as st
            s = str(st.secrets.get("PMS_PASARELA_SECRETO", "")) or str(st.secrets.get("PMS_SESION_SECRETO", ""))
        except Exception:
            s = ""
    if not s:
        s = os.environ.get("PMS_SESION_SECRETO", "")
    if not s:
        base = os.environ.get("DATABASE_URL", "")
        s = hashlib.sha256(("pms-pasarela|" + base).encode()).hexdigest() if base else "pms-desarrollo-local"
    return hashlib.sha256(b"pasarela|" + s.encode()).digest()


def secreto_publico() -> bytes:
    """Misma clave derivada que usa el resto del PMS para firmar enlaces y números (nunca se imprime)."""
    return _secreto()


def _canonico(evento: dict) -> bytes:
    return json.dumps(evento, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


class PasarelaSimulada:
    nombre = "simulada"
    leyenda = LEYENDA_PRUEBAS

    def nueva_referencia(self) -> str:
        return "SIM-" + secrets.token_hex(6).upper()

    def firmar(self, evento: dict) -> str:
        return hmac.new(_secreto(), _canonico(evento), hashlib.sha256).hexdigest()

    def verificar_evento(self, evento: dict, firma: str) -> bool:
        try:
            return hmac.compare_digest(self.firmar(evento), str(firma or ""))
        except Exception:
            return False

    def normalizar(self, evento: dict) -> dict:
        return evento

    def evento(self, referencia: str, monto, moneda: str, aprobado: bool = True) -> tuple[dict, str]:
        """Lo que «enviaría» la pasarela simulada cuando el cliente pulsa «pagar» o «rechazar» en su pantalla de prueba."""
        ev = {"id": "EVT-" + secrets.token_hex(8), "tipo": "pago.aprobado" if aprobado else "pago.rechazado",
              "referencia": referencia, "monto": f"{Decimal(str(monto)):.2f}", "moneda": moneda, "timestamp": int(time.time())}
        return ev, self.firmar(ev)


class PasarelaWompi:
    """Esqueleto para la fase 2. Documentación de Wompi: eventos con `signature.properties` + `timestamp` + secreto de eventos → SHA-256."""
    nombre = "wompi"
    leyenda = ""

    def __init__(self):
        self.secreto_eventos = os.environ.get("WOMPI_EVENTOS_SECRETO", "")

    def nueva_referencia(self) -> str:
        return "ATM-" + secrets.token_hex(8).upper()

    def verificar_evento(self, crudo: dict, firma: str = "") -> bool:
        try:
            if not self.secreto_eventos:
                return False
            sig = crudo["signature"]
            partes = []
            for ruta in sig["properties"]:
                v = crudo["data"]
                for k in ruta.split("."):
                    v = v[k]
                partes.append(str(v))
            esperado = hashlib.sha256(("".join(partes) + str(crudo["timestamp"]) + self.secreto_eventos).encode()).hexdigest()
            return hmac.compare_digest(esperado, str(sig["checksum"]).lower()) and hmac.compare_digest(esperado, str(firma or sig["checksum"]).lower())
        except Exception:
            return False

    def normalizar(self, crudo: dict) -> dict:
        t = crudo["data"]["transaction"]
        estado = str(t.get("status", "")).upper()
        return {"id": f"{t['id']}:{estado}", "tipo": "pago.aprobado" if estado == "APPROVED" else "pago.rechazado",
                "referencia": t["reference"], "monto": f"{Decimal(t['amount_in_cents']) / 100:.2f}", "moneda": t["currency"],
                "timestamp": crudo.get("timestamp")}


def obtener(nombre: str | None = None):
    nombre = (nombre or os.environ.get("PMS_PASARELA", "simulada")).lower()
    if nombre == "simulada":
        return PasarelaSimulada()
    if nombre == "wompi":
        return PasarelaWompi()
    raise ErrorNegocio("Pasarela de pago no configurada.")

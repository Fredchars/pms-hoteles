"""Correo de confirmación de la reserva web. Por defecto SIMULADO: no se envía nada, se guarda en `pms_correos` y se muestra en pantalla.

Proveedores listos (adaptadores): `resend` y `brevo` (HTTP). Solo se envía de verdad si TODAS estas variables existen:
  PMS_CORREO_PROVEEDOR=resend|brevo · PMS_CORREO_API_KEY=… · PMS_CORREO_REMITENTE=… · PMS_CORREO_PERMITIDOS=a@x.com,b@y.com
`PMS_CORREO_PERMITIDOS` es una lista blanca obligatoria durante el prototipo: a cualquier otra dirección se le simula (nunca se escribe a terceros).
La clave no se imprime ni se guarda en la base."""
from __future__ import annotations

import html
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

PLANTILLA = Path(__file__).resolve().parent / "plantillas" / "correo_confirmacion.html"
AVISO_SIMULADO = "Correo simulado: no se envió"
AVISO_PRUEBAS = ('<p style="font-size:12px;color:#7a5b00;background:#fff4cc;border-radius:6px;padding:8px;margin:14px 0 0">'
                 "Prototipo en MODO PRUEBAS: datos ficticios y no se cobró dinero.</p>")


def construir(datos: dict) -> tuple[str, str, str]:
    """(asunto, html, texto). `datos`: hotel, nombre, numero, entrada, salida, habitacion, personas, total, enlace, pruebas(bool)."""
    asunto = f"Reserva confirmada {datos['numero']} · {datos['hotel']}"
    cuerpo = PLANTILLA.read_text(encoding="utf-8")
    vals = {k: html.escape(str(v)) for k, v in datos.items() if k != "pruebas"}
    vals["asunto"] = html.escape(asunto)
    vals["aviso_pruebas"] = AVISO_PRUEBAS if datos.get("pruebas", True) else ""
    for k, v in vals.items():
        cuerpo = cuerpo.replace("{{" + k + "}}", v)
    texto = (f"Hola {datos['nombre']}, tu reserva en {datos['hotel']} está confirmada.\n\nNúmero de reserva: {datos['numero']}\n"
             f"Entrada: {datos['entrada']}\nSalida: {datos['salida']}\nHabitación: {datos['habitacion']}\n"
             f"Huéspedes: {datos['personas']}\nTotal pagado: {datos['total']}\n\nVer mi reserva: {datos['enlace']}\n")
    return asunto, cuerpo, texto


def _permitidos() -> set[str]:
    return {e.strip().lower() for e in os.environ.get("PMS_CORREO_PERMITIDOS", "").split(",") if e.strip()}


def _http_json(url: str, cuerpo: dict, cabeceras: dict) -> int:
    req = urllib.request.Request(url, data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json", **cabeceras},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:       # noqa: S310 (URL fija de los proveedores)
        return r.status


def enviar(destinatario: str, asunto: str, cuerpo_html: str, texto: str) -> dict:
    """Devuelve {proveedor, estado('simulado'|'enviado'|'error'), detalle}. Nunca lanza: un fallo de correo no debe deshacer una reserva pagada."""
    prov = os.environ.get("PMS_CORREO_PROVEEDOR", "simulado").lower()
    clave, remit = os.environ.get("PMS_CORREO_API_KEY", ""), os.environ.get("PMS_CORREO_REMITENTE", "")
    if prov not in ("resend", "brevo") or not clave or not remit:
        return {"proveedor": "simulado", "estado": "simulado", "detalle": AVISO_SIMULADO}
    if destinatario.strip().lower() not in _permitidos():
        return {"proveedor": "simulado", "estado": "simulado",
                "detalle": AVISO_SIMULADO + " (destinatario fuera de la lista de prueba permitida)"}
    try:
        if prov == "resend":
            st = _http_json("https://api.resend.com/emails", {"from": remit, "to": [destinatario], "subject": asunto,
                                                             "html": cuerpo_html, "text": texto}, {"Authorization": f"Bearer {clave}"})
        else:
            st = _http_json("https://api.brevo.com/v3/smtp/email", {"sender": {"email": remit}, "to": [{"email": destinatario}],
                                                                  "subject": asunto, "htmlContent": cuerpo_html, "textContent": texto},
                            {"api-key": clave})
        return {"proveedor": prov, "estado": "enviado", "detalle": f"HTTP {st}"}
    except urllib.error.HTTPError as e:
        return {"proveedor": prov, "estado": "error", "detalle": f"HTTP {e.code}"}
    except Exception as e:                                    # sin red, tiempo agotado…
        return {"proveedor": prov, "estado": "error", "detalle": type(e).__name__}


def correo_valido(e: str) -> bool:
    return bool(re.match(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$", e or "")) and len(e) <= 120


def enmascarar(e: str) -> str:
    u, _, d = (e or "").partition("@")
    return (u[:2] + "***@" + d) if d else ""

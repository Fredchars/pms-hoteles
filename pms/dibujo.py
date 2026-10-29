"""Dibujo del plano de planta (HTML puro, fondo blanco) compartido por el PMS y la reserva web.
Disposición provisional (layout de prueba): las habitaciones con vista al mar van en la fila del mar; las demás, al otro lado del
pasillo central. Solo se dibujan habitaciones que existen en la base; las zonas comunes son rótulos sin datos."""
from __future__ import annotations

import html

CSS = """
.st-key-pms_plano_planta, [class*="st-key-rw_plano_planta"] {border:2px solid #9fb3c8 !important;border-radius:14px;background:#fbfcfd;padding:.6rem !important}
.pl-mar {background:linear-gradient(90deg,#d6ecfa,#bfe0f6,#d6ecfa);border-radius:10px;text-align:center;color:#0b4f7c;font-size:.82rem;
         font-weight:700;letter-spacing:.45em;padding:.45rem;margin-bottom:.2rem}
.pl-mar small {display:block;letter-spacing:.05em;font-weight:500;font-size:.7rem;color:#2f6f9a}
.pl-pasillo {background:repeating-linear-gradient(90deg,#eef2f6,#eef2f6 18px,#f7f9fb 18px,#f7f9fb 36px);border:1px dashed #b8c4d0;
             border-radius:8px;text-align:center;color:#62748a;font-size:.72rem;font-weight:600;letter-spacing:.22em;padding:.35rem;margin:.1rem 0}
.pl-comun {border:2px dashed #c3ccd6;border-radius:12px;min-height:9.5rem;display:flex;flex-direction:column;align-items:center;
           justify-content:center;color:#62748a;font-size:.75rem;font-weight:700;text-align:center;background:#fff;padding:.4rem}
.pl-comun span {font-weight:400;font-size:.68rem}
.pl-hab {position:relative;line-height:1.2;min-height:9.5rem}
.pl-hab .m2 {position:absolute;top:.45rem;right:.6rem;font-size:.72rem;color:#52606d}
.pl-hab .vm {display:inline-block;background:#0b7fc2;color:#fff;font-size:.62rem;font-weight:700;letter-spacing:.05em;border-radius:0 0 8px 0;
             padding:.1rem .45rem;margin:-.55rem 0 .25rem -.7rem}
.pl-hab .ti {font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#334e68}
.pl-camas {display:flex;gap:.45rem;flex-wrap:wrap;margin:.4rem 0 .25rem}
.pl-cama {display:flex;flex-direction:column;align-items:center;font-size:.62rem;color:#52606d}
.pl-cama b {display:flex;gap:2px;justify-content:center;align-items:flex-start;border:2px solid #4a6fa5;border-radius:5px;background:#e9f0fa;
            height:1.55rem;padding:2px}
.pl-cama b i {display:block;background:#8fb0dd;border-radius:3px;width:.8rem;height:.5rem}
.pl-hab .e {font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.03em;margin-top:.2rem}
.rw-libre .e {color:#17693c} .rw-sel .e {color:#1a56a8} .rw-no .e {color:#7b8794}
.pl-hab .pr {font-size:.95rem;font-weight:700;color:#102a43}
.pl-hab .pr span {font-size:.68rem;font-weight:400;color:#52606d}
.pl-hab .cap {position:absolute;bottom:.45rem;right:.6rem;font-size:.72rem;color:#52606d}
.pms-room-capacidad .pl-cama b, .rw-no .pl-cama b {border-color:#b5bfca;background:#f1f3f5}
.pms-room-capacidad .pl-cama b i, .rw-no .pl-cama b i {background:#cbd2d9}
"""


def camas_por_habitacion(cx, ids: list[int]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {i: [] for i in ids}
    if ids:
        for c in cx.execute("select habitacion_id, tipo, ancho_cm, cantidad from pms_camas where habitacion_id = any(%s) order by id",
                            (list(ids),)).fetchall():
            out.setdefault(c["habitacion_id"], []).append(c)
    return out


def camas_html(camas: list[dict]) -> str:
    """Un icono por cama (cantidad expandida): matrimonial/sofá cama con dos almohadas, individual/litera/cuna con una; ancho a escala."""
    piezas = []
    for c in camas or []:
        doble = c["tipo"] in ("matrimonial", "sofa_cama")
        ancho = c.get("ancho_cm") or (150 if doble else 90)
        px = max(26, min(64, round(ancho * 0.36)))
        rot = f"{ancho} cm" if c.get("ancho_cm") else c["tipo"].replace("_", " ")
        if c["tipo"] == "litera":
            rot = "litera " + rot
        alm = "<i></i><i></i>" if doble else "<i></i>"
        piezas += [f'<span class="pl-cama"><b style="width:{px}px">{alm}</b>{html.escape(rot)}</span>'] * int(c.get("cantidad") or 1)
    return f'<div class="pl-camas">{"".join(piezas)}</div>' if piezas else '<div class="pl-camas" style="font-size:.7rem;color:#9aa5b1">Sin camas registradas</div>'


def tipologia(tipo: str, vista: str | None) -> str:
    """«Interior (Doble Monte)» → «Doble Monte»; si no hay paréntesis, el nombre del tipo."""
    if vista and "(" in vista and vista.endswith(")"):
        return vista[vista.index("(") + 1:-1]
    return tipo


def tarjeta(clase: str, numero: str, tipo: str, vista: str | None, vista_mar: bool, metros, camas: list[dict], precio: str,
            capacidad, estado: str) -> str:
    """Habitación dibujada. `clase` es la clase de estado (p. ej. «pms-room pms-room-disponible»)."""
    vm = '<span class="vm">🌊 VISTA MAR</span><br>' if vista_mar else ""
    return (f'<div class="{clase} pl-hab">{vm}<span class="m2">{metros or "—"} m²</span>'
            f'<div class="n">{html.escape(str(numero))}</div><div class="ti">{html.escape(tipologia(tipo, vista))}</div>'
            f'{camas_html(camas)}<div class="pr">{precio}</div><div class="e">{html.escape(estado)}</div>'
            f'<span class="cap">👥 {capacidad or "—"}</span></div>')


def filas(habitaciones: list[dict], clave_mar: str = "vista_mar") -> tuple[list[dict], list[dict]]:
    """(lado mar, lado opuesto) en orden de número."""
    orden = sorted(habitaciones, key=lambda h: str(h["numero"]))
    return [h for h in orden if h.get(clave_mar)], [h for h in orden if not h.get(clave_mar)]


MAR = '<div class="pl-mar">🌊 M A R<small>Fachada con vista al mar</small></div>'
PASILLO = '<div class="pl-pasillo">⇤ PASILLO CENTRAL · SALIDA DE EMERGENCIA ⇥</div>'
COMUN_MAR = '<div class="pl-comun">ZONA COMÚN<span>Frente al mar (rótulo del layout de prueba)</span></div>'
ESCALERA = '<div class="pl-comun">ESCALERA · ASCENSOR<span>Circulación vertical</span></div>'

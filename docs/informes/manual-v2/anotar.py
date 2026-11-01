"""Dibuja recuadros numerados sobre las capturas (crudas/ + cajas.json) y guarda en img/. Prototipo diseñado para ATm Consulting."""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
CRUDAS, IMG = AQUI / "crudas", AQUI / "img"
CAP = AQUI.parents[1] / "capturas"
COLOR = (230, 57, 70)
FUENTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Capturas antiguas de la mini web (base local), con cajas puestas a mano: archivo -> [(n, x0, y0, x1, y1)]
WEB = json.loads((AQUI / "cajas_web.json").read_text()) if (AQUI / "cajas_web.json").exists() else {}


def anotar(src, cajas, dst, recorte_alto=None):
    im = Image.open(src).convert("RGB")
    W, H = im.size
    if recorte_alto and H > recorte_alto:
        im = im.crop((0, 0, W, recorte_alto)); H = recorte_alto
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FUENTE, 22)
    for z in cajas:
        n, (x0, y0, x1, y1) = z["n"], z["box"]
        x0, y0, x1, y1 = max(2, x0), max(2, y0), min(W - 3, x1), min(H - 3, y1)
        if x1 - x0 < 6 or y1 - y0 < 6:
            continue
        d.rectangle([x0, y0, x1, y1], outline=COLOR, width=3)
        r = 17
        cx, cy = x0 + r - 2, y0 + r - 2
        if x0 >= 2 * r + 10:          # fuera del recuadro, a la izquierda, para no tapar el rótulo
            cx, cy = x0 - r - 4, y0 + r
        if z.get("pos") == "derecha":
            cx = x1 - r + 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=COLOR, outline="white", width=2)
        t = str(n)
        tw = d.textlength(t, font=f)
        d.text((cx - tw / 2, cy - 13), t, font=f, fill="white")
    im.save(dst, optimize=True)


def main():
    IMG.mkdir(exist_ok=True)
    cajas = json.loads((CRUDAS / "cajas.json").read_text())
    ajustes = json.loads((AQUI / "ajustes.json").read_text()) if (AQUI / "ajustes.json").exists() else {}
    for nombre, zs in cajas.items():
        a = ajustes.get(nombre, {})
        zs = [z for z in zs if z["n"] not in a.get("quitar", [])]
        for n, box in a.get("cajas", {}).items():
            zs = [z for z in zs if z["n"] != int(n)] + [{"n": int(n), "box": box}]
        for z in zs:
            if str(z["n"]) in a.get("derecha", []):
                z["pos"] = "derecha"
        anotar(CRUDAS / f"{nombre}.png", sorted(zs, key=lambda z: z["n"]), IMG / f"{nombre}.png", a.get("alto"))
    for arch, d in WEB.items():
        anotar(CAP / arch, [{"n": z[0], "box": z[1:5]} for z in d["cajas"]], IMG / ("w_" + arch), d.get("alto"))
    print("anotadas", len(cajas) + len(WEB))


if __name__ == "__main__":
    main()

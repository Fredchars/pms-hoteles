"""Suite v2: reutiliza la pantalla app/paginas/facturacion.py del PMS (misma lógica, misma base)."""
from pathlib import Path

_F = Path(__file__).resolve().parents[2] / "app" / "paginas" / "facturacion.py"
exec(compile(_F.read_text(encoding="utf-8"), str(_F), "exec"), globals())

"""Suite v2: reutiliza la pantalla app/paginas/plano.py del PMS (misma lógica, misma base)."""
from pathlib import Path

_F = Path(__file__).resolve().parents[2] / "app" / "paginas" / "plano.py"
exec(compile(_F.read_text(encoding="utf-8"), str(_F), "exec"), globals())

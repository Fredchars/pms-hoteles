"""Tarea programada (GitHub Actions, cada 5 min): libera las opciones y los bloqueos web vencidos de TODOS los hoteles.
La disponibilidad no depende de esta tarea (también se liberan «perezosamente» al consultar); esta tarea mantiene el estado al día
aunque nadie esté entrando. Imprime solo conteos; no imprime secretos."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pms import db, vencimientos  # noqa: E402


def main():
    if not os.environ.get("DATABASE_URL"):
        sys.exit("Falta DATABASE_URL")
    with db.tx() as cx:
        lib = vencimientos.liberar_vencidas(cx)
    web = sum(1 for x in lib if x.get("web"))
    print(f"Liberadas {len(lib)} opción(es) vencida(s), {web} de la reserva web.", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()

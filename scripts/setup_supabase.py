"""Prepara las tablas pms_* en el proyecto Supabase (se ejecuta desde GitHub Actions, workflow supabase.yml).

1) En UNA transacción: crea las 17 tablas pms_* (si no existen), índices, activa RLS y revoca anon/authenticated.
2) Si no hay hoteles (o PMS_RESEMBRAR=si): carga los datos ficticios de prueba con las contraseñas de PMS_SEED_CLAVES.
Solo toca tablas con prefijo pms_. No imprime la cadena de conexión ni contraseñas."""
import os
import sys
from pathlib import Path

import psycopg

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("Falta DATABASE_URL")
    esquema = (RAIZ / "db" / "01_esquema_pms.sql").read_text() + "\n" + (RAIZ / "db" / "02_rls_pms.sql").read_text()
    with psycopg.connect(url, prepare_threshold=None) as cx:      # el bloque with confirma al salir (una sola transacción)
        cx.execute(esquema)
    print("Esquema pms_* + RLS aplicados (1 transacción)")

    from pms import db, semilla
    if not os.environ.get("PMS_SEED_CLAVES"):
        sys.exit("Falta PMS_SEED_CLAVES (JSON correo→contraseña de los usuarios de prueba)")
    n = db.uno("select count(*) n from pms_hoteles")["n"]
    reiniciar = os.environ.get("PMS_RESEMBRAR") == "si"
    if n and not reiniciar:
        print(f"Ya hay {n} hoteles: no se siembra (use resembrar=true para rehacer los datos ficticios)")
    else:
        claves = semilla.sembrar(reiniciar=reiniciar, guardar_claves=False)
        print(f"Datos ficticios sembrados: {len(claves)} usuarios")
    for t in semilla.TABLAS:
        print(f"  {t}: {db.uno(f'select count(*) n from {t}')['n']} filas")
    db.cerrar_pool()


if __name__ == "__main__":
    main()

"""Prepara las tablas pms_* en el proyecto Supabase (se ejecuta desde GitHub Actions, workflow supabase.yml).

1) En UNA transacción: crea las 17 tablas pms_* (si no existen), índices, activa RLS y revoca anon/authenticated.
2) Si no hay hoteles (o PMS_RESEMBRAR=si): genera los datos ficticios en una base local temporal y los copia en una sola transacción.
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

    if not os.environ.get("PMS_SEED_CLAVES"):
        sys.exit("Falta PMS_SEED_CLAVES (JSON correo→contraseña de los usuarios de prueba)")
    reiniciar = os.environ.get("PMS_RESEMBRAR") == "si"
    with psycopg.connect(url, prepare_threshold=None) as cx:
        n = cx.execute("select count(*) from pms_hoteles").fetchone()[0]
    if n and not reiniciar:
        print(f"Ya hay {n} hoteles: no se siembra (use resembrar=true para rehacer los datos ficticios)")
        return
    local = os.environ.get("PMS_SEED_LOCAL_URL")
    if not local:
        sys.exit("Falta PMS_SEED_LOCAL_URL (base PostgreSQL temporal donde se genera la semilla; evita miles de viajes a Supabase)")
    if local == url or not any(h in local for h in ("@localhost", "@127.0.0.1")):
        sys.exit("PMS_SEED_LOCAL_URL debe ser una base local temporal distinta de DATABASE_URL")
    # 1) La semilla se genera en una base temporal local del ejecutor (rápido) ...
    with psycopg.connect(local, autocommit=True) as cl:
        cl.execute("drop schema if exists public cascade; create schema public")
        cl.execute(esquema)
    os.environ["DATABASE_URL"] = local
    from pms import db, semilla
    claves = semilla.sembrar(reiniciar=False, guardar_claves=False)
    db.cerrar_pool()
    # 2) ... y se copia a Supabase en UNA transacción (solo tablas pms_*).
    orden = list(reversed(semilla.TABLAS))                    # primero las tablas de las que otras dependen
    with psycopg.connect(local) as cl, psycopg.connect(url, prepare_threshold=None) as cx:
        if reiniciar or n:
            cx.execute("truncate " + ", ".join(semilla.TABLAS) + " restart identity cascade")
        for t in orden:
            with cl.cursor().copy(f"copy {t} to stdout") as origen, cx.cursor().copy(f"copy {t} from stdin") as destino:
                for bloque in origen:
                    destino.write(bloque)
        for t in orden:
            cx.execute("select setval(pg_get_serial_sequence(%s, 'id'), greatest(coalesce((select max(id) from " + t + "), 0), 1), "
                       "(select count(*) > 0 from " + t + "))", (t,))
    print(f"Datos ficticios sembrados: {len(claves)} usuarios")
    with psycopg.connect(url, prepare_threshold=None) as cx:
        for t in semilla.TABLAS:
            print(f"  {t}: {cx.execute(f'select count(*) from {t}').fetchone()[0]} filas")


if __name__ == "__main__":
    main()

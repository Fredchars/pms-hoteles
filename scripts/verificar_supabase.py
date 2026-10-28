"""Verifica las tablas pms_* en Supabase: existen (17), RLS activo sin políticas, anon/authenticated sin privilegios,
la API REST pública (clave anon) no devuelve filas, contraseñas solo con hash, y que las demás tablas del proyecto
(ATLAS, simulador, etc.) siguen intactas. Sale con código 1 si algo falla. No imprime secretos."""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

RAIZ = Path(__file__).resolve().parent.parent
TABLAS = re.findall(r"create table if not exists (\w+)", (RAIZ / "db" / "01_esquema_pms.sql").read_text())
AJENAS = ["pedidos", "ledger", "eventos"]        # tablas de ATLAS que NO deben tocarse
fallos = []


def ok(cond, msg):
    print(("OK   " if cond else "FALLA") + " " + msg)
    if not cond:
        fallos.append(msg)


def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("Falta DATABASE_URL")
    with psycopg.connect(url, row_factory=dict_row, prepare_threshold=None) as cx:
        ok(len(TABLAS) == 17, f"el esquema define {len(TABLAS)} tablas pms_")
        filas = {r["relname"]: r for r in cx.execute(
            "select c.relname, c.relrowsecurity, (select count(*) from pg_policies p where p.tablename = c.relname) as politicas "
            "from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and c.relkind = 'r' "
            "and c.relname like 'pms\\_%%'").fetchall()}
        ok(set(filas) == set(TABLAS), "las tablas pms_ de la base son exactamente las del esquema")
        for t in TABLAS:
            if t not in filas:
                ok(False, f"tabla {t} existe")
                continue
            ok(filas[t]["relrowsecurity"], f"RLS activo en {t}")
            ok(filas[t]["politicas"] == 0, f"{t} sin políticas (nadie entra por la API pública)")
            for rol in ("anon", "authenticated"):
                p = cx.execute("select has_table_privilege(%s, %s, 'select') s", (rol, f"public.{t}")).fetchone()
                ok(not p["s"], f"{rol} sin SELECT en {t}")
        n = cx.execute("select count(*) n from pms_usuarios").fetchone()["n"]
        malos = cx.execute("select count(*) n from pms_usuarios where clave_hash not like '$2%%'").fetchone()["n"]
        ok(n > 0 and malos == 0, f"{n} usuarios, todos con contraseña en hash bcrypt")
        print(f"     hoteles: {cx.execute('select count(*) n from pms_hoteles').fetchone()['n']} · reservas: "
              f"{cx.execute('select count(*) n from pms_reservas').fetchone()['n']}")
        dobles = cx.execute("select count(*) n from (select habitacion_id, noche from pms_reserva_noches where activa "
                            "group by 1,2 having count(*)>1) x").fetchone()["n"]
        ok(dobles == 0, "no hay doble venta (ninguna habitación vendida dos veces la misma noche)")
        for t in AJENAS:
            r = cx.execute("select relrowsecurity from pg_class c join pg_namespace n on n.oid = c.relnamespace "
                           "where n.nspname = 'public' and c.relname = %s", (t,)).fetchone()
            ok(r is not None and r["relrowsecurity"], f"tabla ajena {t} presente y con RLS (no se tocó)")
        otras = [r["relname"] for r in cx.execute(
            "select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='r' "
            "and c.relname not like 'pms\\_%%' order by 1").fetchall()]
        print(f"     tablas de otros proyectos en 'public' (no tocadas): {len(otras)}")

    base, anon = os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_ANON_KEY", "")
    if base and anon:
        for t in TABLAS:
            req = urllib.request.Request(f"{base}/rest/v1/{t}?select=*&limit=1", headers={"apikey": anon, "Authorization": f"Bearer {anon}"})
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    cuerpo = json.loads(resp.read() or b"[]")
                    ok(cuerpo == [], f"API REST pública /{t}: HTTP {resp.status}, 0 filas")
            except urllib.error.HTTPError as e:
                ok(e.code in (401, 403, 404), f"API REST pública /{t}: HTTP {e.code} (acceso denegado)")
    else:
        print("AVISO sin SUPABASE_URL/SUPABASE_ANON_KEY: se omite la prueba de la API REST")
    if fallos:
        sys.exit(f"{len(fallos)} verificaciones fallaron")
    print("Todo correcto")


if __name__ == "__main__":
    main()

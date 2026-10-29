"""Marca a TODOS los usuarios para que creen su propia contraseña en el próximo ingreso (debe_cambiar_clave=true).
Opcional: si existe PMS_ADMIN_HASH (hash bcrypt) reemplaza la contraseña de admin@pms-demo.test, y si existe PMS_CLAVES_HASH
(JSON {correo: hash bcrypt}, nunca claves en claro) reemplaza la contraseña de esos usuarios; cambiar la contraseña cierra sus sesiones anteriores. Se ejecuta desde GitHub Actions (workflow supabase.yml, opción «marcar_cambio_clave»).
Solo toca pms_usuarios. No imprime contraseñas ni hashes."""
import json
import os
import sys

import psycopg

ADMIN = "admin@pms-demo.test"


def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("Falta DATABASE_URL")
    h = os.environ.get("PMS_ADMIN_HASH", "").strip()
    if h and not h.startswith("$2"):
        sys.exit("PMS_ADMIN_HASH no parece un hash bcrypt")
    with psycopg.connect(url, prepare_threshold=None) as cx:       # una sola transacción
        cx.execute("alter table pms_usuarios add column if not exists debe_cambiar_clave boolean not null default false")
        n = cx.execute("update pms_usuarios set debe_cambiar_clave=true").rowcount
        print(f"Usuarios marcados para crear su contraseña al primer ingreso: {n}")
        hashes = json.loads(os.environ.get("PMS_CLAVES_HASH", "") or "{}")
        if h:
            hashes[ADMIN] = h
        if any(not v.startswith("$2") for v in hashes.values()):
            sys.exit("PMS_CLAVES_HASH debe contener solo hashes bcrypt")
        r = 0
        for email, hh in hashes.items():
            k = cx.execute("update pms_usuarios set clave_hash=%s where lower(email)=%s", (hh, email.lower())).rowcount
            if k:
                cx.execute("insert into pms_auditoria (usuario_email, accion, entidad, entidad_id, despues) "
                           "select email, 'clave_temporal', 'usuario', id::text, '{\"debe_cambiar_clave\": true}'::jsonb "
                           "from pms_usuarios where lower(email)=%s", (email.lower(),))
            r += k
        if hashes:
            print(f"Contraseñas temporales reemplazadas: {r} usuario(s)")


if __name__ == "__main__":
    main()

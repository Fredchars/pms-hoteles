"""Marca a TODOS los usuarios para que creen su propia contraseña en el próximo ingreso (debe_cambiar_clave=true).
Opcional: si existe PMS_ADMIN_HASH (hash bcrypt, nunca la clave en claro) reemplaza la contraseña de admin@pms-demo.test, lo que
además cierra sus sesiones anteriores. Se ejecuta desde GitHub Actions (workflow supabase.yml, opción «marcar_cambio_clave»).
Solo toca pms_usuarios. No imprime contraseñas ni hashes."""
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
        if h:
            r = cx.execute("update pms_usuarios set clave_hash=%s where lower(email)=%s", (h, ADMIN)).rowcount
            if r:
                cx.execute("insert into pms_auditoria (usuario_email, accion, entidad, entidad_id, despues) "
                           "select email, 'clave_temporal', 'usuario', id::text, '{\"debe_cambiar_clave\": true}'::jsonb "
                           "from pms_usuarios where lower(email)=%s", (ADMIN,))
            print(f"Contraseña temporal del administrador reemplazada: {r} usuario(s)")


if __name__ == "__main__":
    main()

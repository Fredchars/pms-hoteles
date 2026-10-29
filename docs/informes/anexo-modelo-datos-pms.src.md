# PMS Hotelero · Piloto — Anexo A · Modelo de datos

*Prototipo diseñado para ATm Consulting · versión 1.1 · 29 de octubre de 2026 · fuente: `db/01_esquema_pms.sql` y `db/02_rls_pms.sql`*

## 1. Vista general por dominio
21 tablas con prefijo `pms_` en el esquema `public` de Supabase (proyecto *atlas-selleragent*), agrupadas en 7 dominios con un color cada uno. Las flechas van del dominio referenciado al que lo usa y llevan los nombres de las columnas FK. `pms_auditoria` no tiene FK: recibe una fila por cada acción importante.

![Vista general por dominio](img-er/01-vista-general-dominios.png)

## 2. Diagrama ER completo
Todas las tablas y columnas, agrupadas por dominio. Notación pata de gallo: **pata** = muchos, **barra** = uno, **círculo** = opcional; `?` = la columna admite nulos. Las líneas punteadas finas son `hotel_id` y las columnas de usuario (quién creó/aprobó), para no tapar las relaciones de negocio.

![ER completo](img-er/02-er-completo.png)

## 3. Diagramas por dominio
Cada diagrama muestra solo las columnas PK/FK/UK (el resto está en §4), las relaciones internas con su cardinalidad y un recuadro con las FK hacia o desde otros dominios.

### 3.1 Organización y acceso
Tablas: `pms_hoteles`, `pms_usuarios`, `pms_impuestos`.

![Organización y acceso](img-er/03-dominio-1-organizacion-y-acceso.png)

### 3.2 Catálogos y tarifas
Tablas: `pms_tipos_habitacion`, `pms_tarifas`.

![Catálogos y tarifas](img-er/03-dominio-2-catalogos-y-tarifas.png)

### 3.3 Inventario y plano
Tablas: `pms_habitaciones`, `pms_camas`, `pms_bloqueos`, `pms_housekeeping`.

![Inventario y plano](img-er/03-dominio-3-inventario-y-plano.png)

### 3.4 Reservas (núcleo)
Tablas: `pms_huespedes`, `pms_consentimientos`, `pms_reservas`, `pms_reserva_noches`, `pms_estancias`.

![Reservas (núcleo)](img-er/03-dominio-4-reservas-nucleo.png)

### 3.5 Facturación y pagos
Tablas: `pms_cargos`, `pms_pagos`.

![Facturación y pagos](img-er/03-dominio-5-facturacion-y-pagos.png)

### 3.6 Reserva web
Tablas: `pms_reservas_web`, `pms_pagos_pasarela`, `pms_eventos_pasarela`, `pms_correos`.

![Reserva web](img-er/03-dominio-6-reserva-web.png)

### 3.7 Auditoría
Tablas: `pms_auditoria`.

![Auditoría](img-er/03-dominio-7-auditoria.png)

## 4. Diccionario de datos
{{DICCIONARIO}}

## 5. Tabla de relaciones
{{RELACIONES}}

## 6. Cómo fluye una reserva por las tablas

![Ciclo de vida de una reserva](img-er/04-ciclo-vida-reserva.png)

1. **Huésped:** `pms_huespedes` + `pms_consentimientos` (finalidad, versión del texto, fecha).
2. **Reserva:** `pms_reservas` (estado, canal, personas, fechas; `opcion_vence_en` si es opción) y una fila de `pms_reserva_noches` por noche con habitación y **precio congelado**.
3. **Cuenta:** `pms_cargos` (noches, extras, descuentos con aprobación e impuestos congelados en jsonb) y `pms_pagos`.
4. **Check-in/out:** `pms_estancias`; el check-out deja la habitación `sucia` y se registra en `pms_housekeeping`.
5. **Cancelación / no-show:** las noches pasan a `activa = false` y la habitación queda libre.
6. **Reserva web:** `pms_reservas_web` (número público, hash del token, estado, vencimiento) → `pms_pagos_pasarela` → `pms_eventos_pasarela` (idempotencia) → `pms_pagos` (método `pasarela`) → `pms_correos`.
7. Toda acción importante queda en `pms_auditoria`.

### 6.1 Reglas de integridad
- `ux_pms_noche_habitacion` (habitacion_id, noche) **where activa**: sin doble venta.
- `ux_pms_noche_reserva` (reserva_id, noche) where activa.
- `ux_pms_reservas_ref_externa` (hotel_id, canal, referencia_externa): evita duplicar reservas de canales.
- Checks: fechas de salida > entrada, porcentajes 0–100, montos ≥ 0, estados en listas cerradas.

### 6.2 Índices
`ix_pms_reservas_fechas`, `ix_pms_reservas_opcion_vence`, `ix_pms_noches_hotel`, `ix_pms_hk_hab`, `ix_pms_cargos_reserva`, `ix_pms_pagos_reserva`, `ix_pms_aud_hotel`, `ix_pms_rweb_hotel`, `ix_pms_rweb_ip`, `ix_pms_pasarela_rweb`, `ix_pms_correos_reserva`.

### 6.3 Funciones y triggers
`pms_auditoria_inmutable()` con el trigger `pms_auditoria_no_update` (before update or delete): la auditoría es de solo agregar.

### 6.4 RLS
`db/02_rls_pms.sql` activa RLS en todas las tablas `pms_*` **sin políticas** y revoca todo a `anon` y `authenticated` (tablas y secuencias). Resultado: la API REST pública de Supabase no devuelve nada; solo el servidor de las apps accede con `DATABASE_URL`.

### 6.5 Migraciones
El esquema es idempotente (`create … if not exists`, `alter … add column if not exists`): `debe_cambiar_clave`, `vista_mar`, `opcion_vence_en` y el método de pago `pasarela` se agregaron sin borrar datos.

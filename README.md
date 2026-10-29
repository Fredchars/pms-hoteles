# PMS hotelero · piloto

*Prototipo diseñado para ATm Consulting.* Sistema sencillo para gestionar hoteles: reservas, calendario, check-in/check-out, limpieza (housekeeping), bloqueos por mantenimiento, facturación simple con comprobante PDF, reportes y auditoría.

> **Todos los datos son ficticios.** Correos, pagos e integraciones están simulados (la pantalla siempre lo avisa). El comprobante PDF **no es una factura legal**.

## Qué incluye
- 3 hoteles de prueba (Colombia/COP, República Dominicana/DOP y otro país/PEN), cada uno con 18 habitaciones provisionales (3 plantas × 6), su moneda local y sus impuestos genéricos (nombre y %).
- 4 roles: recepción, gerencia, housekeeping y administrador. Descuentos y cancelaciones los aprueba gerencia (quien pide no aprueba).
- Precio congelado por noche, sin doble venta (índices únicos + bloqueos de concurrencia), consentimiento de datos (Ley 1581), auditoría que no se puede editar.
- **Plano de habitaciones** (recepción, gerencia; administrador solo consulta): cada planta dibujada con colores por estado en las fechas elegidas (disponible, ocupada, en opción, bloqueada, fuera de servicio, seleccionada, capacidad insuficiente), filtros (hotel, planta, fechas, adultos, niños, tipo, solo vista al mar, ocultar no disponibles), detalle con camas y desglose de precio, y «Continuar con la reserva» que prellena Reservas. Usa la misma regla de disponibilidad (`pms/disponibilidad.py`), de tarifas (`pms/tarifas.py`) y de capacidad que Reservas. La vista al mar es la columna `vista_mar` de `pms_habitaciones` (migración idempotente en `db/01_esquema_pms.sql`; se aplica con el workflow de Supabase ANTES de desplegar el código).
- Fondo blanco, aviso permanente de datos ficticios y marca «Prototipo diseñado para ATm Consulting».

## Estructura
| Carpeta | Contenido |
|---|---|
| `app/` | Interfaz Streamlit (`Inicio.py` y `paginas/`) |
| `pms/` | Reglas de negocio y acceso a datos |
| `db/` | SQL: 17 tablas `pms_*` y seguridad (RLS) |
| `tests/` | 90 pruebas (reglas críticas, plano de habitaciones e interfaz) |
| `scripts/` | Preparar/verificar Supabase, capturas, pruebas de interfaz, generación de documentos |
| `docs/` | Diseño aprobado, instructivo por rol, guía de pruebas, checklist, capturas |
| `.github/workflows/` | Pruebas, preparar/verificar Supabase y respaldo cifrado semanal |

## Correr en local
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
# Necesita un PostgreSQL local vacío (nunca uses una base real):
export DATABASE_URL=postgresql://usuario:clave@localhost:5432/pms_demo
psql "$DATABASE_URL" -f db/01_esquema_pms.sql -f db/02_rls_pms.sql
python -m pms.semilla            # datos ficticios; las contraseñas se guardan en un archivo local (no se imprimen)
export PMS_MODO_DEMO=si          # solo local: panel de acceso rápido
streamlit run app/Inicio.py
```
Pruebas: `PMS_TEST_PG_URL=postgresql://.../pms_test python -m pytest` (se niegan a correr en un servidor que no sea local).

## Variables / secretos
| Nombre | Para qué |
|---|---|
| `DATABASE_URL` | Conexión a PostgreSQL/Supabase (solo en secretos, nunca en el código) |
| `PMS_SESION_SECRETO` | Clave para firmar la sesión |
| `PMS_MODO_DEMO` | `si` solo en local; en producción debe ser `no` |
| `PMS_ENTORNO` | `produccion` apaga siempre el acceso de demostración |

Ejemplo en `.streamlit/secrets.toml.example`. **Nunca subir `secrets.toml`, `.env` ni claves.**

## Primer ingreso y contraseñas temporales
- Cada usuario tiene la bandera `debe_cambiar_clave` (tabla `pms_usuarios`). Si está activa, tras iniciar sesión la app muestra **solo** la pantalla «Crea tu contraseña nueva» (mínimo 10 caracteres, con confirmación y distinta de la temporal); ninguna otra página está disponible hasta guardarla. Al guardar se baja la bandera, se audita (`cambio_clave`, `clave_inicial_creada`) y la persona entra.
- En **Configuración → Usuarios → Generar contraseña temporal** (solo administrador) se crea una contraseña aleatoria segura que se muestra **una sola vez**, se activa la bandera, se cierran las sesiones anteriores de esa persona y se audita (`clave_temporal`) sin guardar la clave en claro. Si el administrador cambia la contraseña de otra persona con «Cambiar contraseña», esa persona también debe crear la suya.
- La semilla de datos ficticios deja a todos los usuarios con la bandera activa. Para marcar a los usuarios ya existentes en Supabase: workflow **Preparar y verificar Supabase (PMS)** con la opción `marcar_cambio_clave` (ejecuta `scripts/marcar_cambio_clave.py`; opcionalmente reemplaza la contraseña del administrador con el hash del secreto `PMS_ADMIN_HASH`, sin pasar claves en claro).

## Base de datos (Supabase)
Solo tablas con prefijo `pms_` en el proyecto compartido. El workflow **Preparar y verificar Supabase (PMS)** las crea con RLS, siembra los datos ficticios y verifica que la API pública no devuelve nada y que las tablas de otros proyectos no se tocan. Se ejecuta a mano desde la pestaña Actions. La migración de la columna `debe_cambiar_clave` es idempotente (`alter table … add column if not exists` en `db/01_esquema_pms.sql`) y se aplica con ese mismo workflow.

## Respaldo
El workflow **Respaldo semanal** (domingos) vuelca las tablas `pms_*`, las cifra con AES-256 (secreto `BACKUP_PASSPHRASE`) y guarda el archivo 30 días como artefacto. Instrucciones de restauración dentro del archivo `LEEME.txt` del respaldo.

## Despliegue
Ver `docs/despliegue-streamlit-cloud.md` (paso manual en Streamlit Community Cloud).

## Documentos
- `docs/diseno-piloto-pms.*` diseño aprobado · `docs/instructivo-pms-por-rol.*` · `docs/guia-de-pruebas-pms.*` · `docs/checklist-pruebas-pms.xlsx`

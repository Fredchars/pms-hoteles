# PMS hotelero · piloto

*Prototipo diseñado para ATm Consulting.* Sistema sencillo para gestionar hoteles: reservas, calendario, check-in/check-out, limpieza (housekeeping), bloqueos por mantenimiento, facturación simple con comprobante PDF, reportes y auditoría.

> **Todos los datos son ficticios.** Correos, pagos e integraciones están simulados (la pantalla siempre lo avisa). El comprobante PDF **no es una factura legal**.

## Qué incluye
- 3 hoteles de prueba (Colombia/COP, República Dominicana/DOP y otro país/PEN), cada uno con 18 habitaciones provisionales (3 plantas × 6), su moneda local y sus impuestos genéricos (nombre y %).
- 4 roles: recepción, gerencia, housekeeping y administrador. Descuentos y cancelaciones los aprueba gerencia (quien pide no aprueba).
- Precio congelado por noche, sin doble venta (índices únicos + bloqueos de concurrencia), consentimiento de datos (Ley 1581), auditoría que no se puede editar.
- Fondo blanco, aviso permanente de datos ficticios y marca «Prototipo diseñado para ATm Consulting».

## Estructura
| Carpeta | Contenido |
|---|---|
| `app/` | Interfaz Streamlit (`Inicio.py` y `paginas/`) |
| `pms/` | Reglas de negocio y acceso a datos |
| `db/` | SQL: 17 tablas `pms_*` y seguridad (RLS) |
| `tests/` | 51 pruebas de reglas críticas |
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

## Base de datos (Supabase)
Solo tablas con prefijo `pms_` en el proyecto compartido. El workflow **Preparar y verificar Supabase (PMS)** las crea con RLS, siembra los datos ficticios y verifica que la API pública no devuelve nada y que las tablas de otros proyectos no se tocan. Se ejecuta a mano desde la pestaña Actions.

## Respaldo
El workflow **Respaldo semanal** (domingos) vuelca las tablas `pms_*`, las cifra con AES-256 (secreto `BACKUP_PASSPHRASE`) y guarda el archivo 30 días como artefacto. Instrucciones de restauración dentro del archivo `LEEME.txt` del respaldo.

## Despliegue
Ver `docs/despliegue-streamlit-cloud.md` (paso manual en Streamlit Community Cloud).

## Documentos
- `docs/diseno-piloto-pms.*` diseño aprobado · `docs/instructivo-pms-por-rol.*` · `docs/guia-de-pruebas-pms.*` · `docs/checklist-pruebas-pms.xlsx`

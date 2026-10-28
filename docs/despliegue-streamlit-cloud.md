# Despliegue en Streamlit Community Cloud (paso manual)

*Prototipo diseñado para ATm Consulting.* Este paso lo hace una persona con acceso a la cuenta de GitHub `Fredchars` (el repositorio es privado).

1. Entra a <https://share.streamlit.io> e inicia sesión con GitHub. Autoriza el acceso a repositorios privados si lo pide.
2. Pulsa **Create app** → **Deploy a public app from GitHub**.
3. Repositorio: `Fredchars/pms-hoteles` · Rama: `main` · Archivo principal: `app/Inicio.py`.
4. En **Advanced settings** elige Python 3.13 y pega los secretos (formato TOML) con estas 4 claves:
   ```toml
   DATABASE_URL = "(cadena del pooler de Supabase)"
   PMS_SESION_SECRETO = "(texto largo al azar)"
   PMS_MODO_DEMO = "no"
   PMS_ENTORNO = "produccion"
   ```
   ATm Consulting tiene ese bloque ya preparado en un archivo seguro (no está en el repositorio ni en Drive).
5. Pulsa **Deploy**. Al terminar, abre la URL y prueba el ingreso con un usuario de prueba.
6. La base ya está lista en Supabase (tablas `pms_*` con datos ficticios). Los usuarios de prueba y sus contraseñas se entregan aparte.
7. Si la app «se duerme» por falta de uso (plan gratuito), se despierta con un clic.

**Importante:** en producción `PMS_MODO_DEMO` debe ser `no` (y `PMS_ENTORNO=produccion` lo fuerza). Los datos son ficticios; no cargar datos reales de huéspedes en el piloto.

# PMS Hotelero · Piloto — Guía de continuidad y respaldo

*Prototipo diseñado para ATm Consulting · versión 1.0 · 29 de octubre de 2026 · este documento no contiene secretos, solo dónde viven*

## 1. Cómo encaja todo
- **GitHub** `Fredchars/pms-hoteles` (público): código, documentos y tareas automáticas (Actions). Cada push a `main` redespliega las dos apps.
- **Streamlit Community Cloud** (cuenta GitHub *fredchars*): `pms-hoteles-atm` (PMS interno, `app/Inicio.py`) y `pms-reservas-atm` (mini web, `reserva_web/Reservas.py`).
- **Supabase Free**, proyecto *atlas-selleragent*: solo las tablas `pms_*` son del PMS. El proyecto es compartido; **no tocar** tablas de otros proyectos (ATLAS, `sim_*`, `agora_*`). El proyecto *pqrs-beta* es exclusivo del PQRS.
- **Google Drive**, carpeta del proyecto: documentos y archivo de usuarios de prueba.

## 2. Inventario de cuentas (sin secretos)
| Servicio | Cuenta / recurso | Para qué |
|---|---|---|
| GitHub | Fredchars · `pms-hoteles` | Código, Actions, secretos del repositorio |
| Streamlit Cloud | workspace *fredchars* | Hospedaje de las 2 apps |
| Supabase | proyecto *atlas-selleragent* | Base PostgreSQL |
| Google Drive | carpeta «PMS Hoteles - Piloto» | Documentos |

### 2.1 Dónde viven los secretos (solo los nombres)
| Secreto | Dónde vive |
|---|---|
| `DATABASE_URL` | Secretos de cada app en Streamlit (Settings → Secrets) y secretos del repositorio en GitHub |
| `PMS_SESION_SECRETO`, `PMS_MODO_DEMO`, `PMS_ENTORNO` | Secretos de la app en Streamlit |
| `PMS_PASARELA_SECRETO`, `PMS_WEB_URL` | Secretos de la mini web en Streamlit |
| `BACKUP_PASSPHRASE` | Secreto del repositorio en GitHub + gestor de contraseñas de ATm |
| `PMS_ADMIN_HASH` (opcional) | Secreto del repositorio (solo un hash, nunca una clave en claro) |
| Contraseñas temporales de prueba | Archivo .txt en Drive (cada usuario la reemplaza al entrar) |

Nunca subir `secrets.toml`, `.env` ni claves al repositorio. Plantillas: `.streamlit/secrets.toml.example` y `reserva_web/secrets.toml.example`.

## 3. Mantener el piloto encendido
- **Streamlit** duerme las apps tras horas sin visitas; se despiertan con un clic.
- **Supabase Free** se pausa tras ~7 días sin actividad; la tarea de liberar vencidos (cada 5 min) y el respaldo semanal lo mantienen activo. Si se pausa, entre a supabase.com y pulse *Restore*.
- **GitHub Actions** programadas se pausan tras 60 días sin actividad del repositorio; reactívelas en la pestaña Actions.

## 4. Volver a publicar una app en Streamlit (restaurar)
1. Entre a https://share.streamlit.io con GitHub (Fredchars).
2. Si la app vieja existe y quiere la misma URL, bórrela primero (⋮ → Delete).
3. **Create app → Deploy a public app from GitHub**.
4. Repositorio `Fredchars/pms-hoteles`, rama `main`, archivo `app/Inicio.py` y App URL `pms-hoteles-atm` (para la mini web: `reserva_web/Reservas.py` y `pms-reservas-atm`).
5. Advanced settings: Python 3.13. En Secrets pegue el bloque TOML guardado de forma segura (ver 2.1). En producción `PMS_MODO_DEMO = "no"` y `PMS_ENTORNO = "produccion"`.
6. **Deploy**, espere 3–5 minutos y compruebe que carga la pantalla de ingreso blanca con la marca ATm.

## 5. Volver a preparar Supabase con GitHub Actions
1. GitHub → repositorio → **Actions → «Preparar y verificar Supabase (PMS)» → Run workflow**.
2. El flujo crea o migra las 21 tablas `pms_*` (idempotente), aplica RLS, siembra los datos ficticios si faltan, marca a los usuarios para crear contraseña y verifica que la API pública no devuelve nada y que otras tablas no se tocaron.
3. Verde = listo. Ejecútelo **antes** de desplegar código que cambie el esquema.
4. Proyecto Supabase nuevo: créelo (plan Free), actualice `DATABASE_URL` en GitHub y en Streamlit, y ejecute este workflow.

## 6. Respaldos
### 6.1 La frase del respaldo
`BACKUP_PASSPHRASE` cifra el archivo (AES-256). Sin ella el respaldo no se puede abrir. Guárdela en el gestor de contraseñas de ATm.

### 6.2 Qué se guarda
Cada domingo a las 3:45 a. m. (hora de Colombia) el workflow **«Respaldo semanal de las tablas del PMS (cifrado)»** hace `pg_dump` de `public.pms_*` (estructura + datos), agrega `CONTEO.txt` y `LEEME.txt` y produce `pms_AAAAMMDD_HHMM.tar.gz.gpg`, guardado **30 días** como artefacto `respaldo-pms`. También se puede lanzar a mano (Run workflow).

### 6.3 Descargar
1. https://github.com/Fredchars/pms-hoteles/actions → «Respaldo semanal…» → ejecución más reciente en verde.
2. En **Artifacts** pulse `respaldo-pms` y descomprima el ZIP.

> Como el repositorio es público, los artefactos los puede listar cualquiera, pero están cifrados: sin la frase no se leen.

### 6.4 Descifrar
```
gpg -d pms_AAAAMMDD_HHMM.tar.gz.gpg | tar xz      # pide la frase
```

### 6.5 Restaurar
1. En una base nueva (recomendado) o tras borrar solo las tablas `pms_*`: `zcat respaldo/pms.sql.gz | psql "$DATABASE_URL"`.
2. `python scripts/setup_supabase.py` para reaplicar RLS y revocaciones (no duplica datos).
3. Ejecute «Preparar y verificar Supabase (PMS)» y compruebe el ingreso.

## 7. Conectar correo real y pasarela real (más adelante)
- **Correo:** definir `PMS_CORREO_PROVEEDOR` (resend o brevo), `PMS_CORREO_API_KEY`, `PMS_CORREO_REMITENTE` y `PMS_CORREO_PERMITIDOS` en los secretos de la mini web. Sin lista de permitidos, el correo sigue simulado.
- **Pasarela (Wompi en Colombia):** cuenta de comercio a nombre del hotel, completar `PasarelaWompi` y montar un receptor de webhooks fuera de Streamlit. Ver `docs/reserva-web.md` y la evaluación del motor de reservas web.

## 8. Insertar la reserva en la web del hotel
```html
<iframe src="https://pms-reservas-atm.streamlit.app/?embed=true&hotel=ID" width="100%" height="1000" style="border:0" title="Reservas"></iframe>
```

## 9. Seguridad antes de usar datos reales
- Pasar a plan de pago (app privada) o a otro hospedaje; el mismo código sirve.
- Rol de base con permisos mínimos para la mini web; captcha real.
- Revisar política de datos (Ley 1581), aviso de privacidad y retención.
- Rotar `PMS_SESION_SECRETO` y `DATABASE_URL`; borrar el secreto de contraseñas antiguas de resiembra si ya no se usa.
- Borrar los usuarios y datos ficticios antes de cargar datos reales.

## 10. Rutina de mantenimiento
| Frecuencia | Tarea |
|---|---|
| Semanal | Revisar que el respaldo del domingo esté en verde |
| Mensual | Descargar un respaldo y probar que se descifra; revisar Actions pausadas |
| Por cambio | Ejecutar pruebas (automático) y el workflow de Supabase si cambió el esquema |
| Trimestral | Rotar secretos y revisar usuarios activos |

## 11. Si algo falla
| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| «No se pudo conectar con la base de datos» | Supabase pausado o `DATABASE_URL` mal | Restaurar el proyecto en Supabase; revisar secretos |
| «Error inesperado (Tipo)» | Fallo de código | Ver registros en Streamlit (Manage app → Logs); *Reboot app* |
| App no actualiza tras un push | Caché de Streamlit | *Reboot app* en share.streamlit.io |
| Opciones que no se liberan | Action pausada | Reactivar «Liberar opciones…»; igual se liberan al consultar |
| Respaldo en rojo | Falta secreto | Revisar `DATABASE_URL` y `BACKUP_PASSPHRASE` en GitHub |

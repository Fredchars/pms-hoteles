# Reserva web (prototipo) · guía técnica

*Prototipo diseñado para ATm Consulting · datos ficticios · pago y correo SIMULADOS.*

## Qué hay
| Pieza | Archivo | Real / simulado |
|---|---|---|
| Mini web pública | `reserva_web/Reservas.py` (app Streamlit aparte, `pms-reservas-atm`) | real |
| API mínima del servidor | `pms/reserva_web.py` (buscar, bloquear, datos+consentimiento, pago, consulta) | real |
| Vencimiento de opciones y bloqueos | `pms/vencimientos.py`, `scripts/liberar_vencidos.py`, workflow `liberar-vencidos.yml` | real |
| Pasarela | `pms/pasarela.py` → `PasarelaSimulada` (firma HMAC-SHA256); `PasarelaWompi` = esqueleto | **simulada** |
| Correo | `pms/correo.py` + `pms/plantillas/correo_confirmacion.html` | **simulado** (adaptadores Resend/Brevo listos) |
| Vista interna | `app/paginas/reservas_web.py` («🌐 Reservas web») | real |

## Flujo y estados
`bloqueada` (15 min) → `pago_pendiente` → `pagada` → `confirmada`; alternativas: `fallida` (se puede reintentar), `expirada` (venció el reloj), `cancelada` (el cliente se arrepintió). Cada reserva web es una reserva del PMS en `opcion` con canal `web` y `opcion_vence_en`; al aprobarse el pago pasa a `confirmada` y se registra el pago (método `pasarela`). Número público `PMS-AAAA-XXXXXX` (alfabeto sin 0/O/1/I/L), único por hotel y canal.

## Seguridad
- La mini web **no** tiene sesión del PMS ni acceso a sus páginas; solo importa `pms/reserva_web.py`. La búsqueda pública devuelve únicamente número, planta, tipo, vista, libre/no libre y precio.
- El enlace de la reserva lleva un token = HMAC-SHA256(secreto del servidor, número); en la base solo se guarda su hash. `consultar` devuelve el correo enmascarado.
- Límites: ≤ 8 bloqueos por dirección IP y hora, ≤ 3 bloqueos activos por IP y ≤ 2 por correo (solo hashes, no direcciones en claro) + verificación aritmética. No es un captcha comercial.
- Validación de entradas: fechas (≤ 30 noches, ≤ 365 días), personas 1–8, nombres/correo/teléfono saneados.
- Pagos: los eventos se aceptan solo con firma válida, monto y moneda correctos y son idempotentes (`pms_eventos_pasarela`, único por proveedor+evento). Un pago tardío intenta recuperar las mismas habitaciones; si no están libres queda en `requiere_revision`.
- Consentimiento (Ley 1581 de 2012): casilla obligatoria + aviso de privacidad; se guarda en `pms_consentimientos` con versión.
- Credencial de servidor: la mini web usa la misma `DATABASE_URL` del PMS (RLS activo, anon/authenticated sin acceso). **Paso a producción:** crear un rol de base de datos con permisos mínimos solo para estas 4 tablas y las de lectura necesarias.

## Despliegue de la mini web (Streamlit Community Cloud)
1. share.streamlit.io → New app → repositorio `Fredchars/pms-hoteles`, rama `main`, archivo `reserva_web/Reservas.py`, subdominio `pms-reservas-atm`, **pública**.
2. Advanced settings → Secrets: ver `reserva_web/secrets.toml.example`.
3. Antes del primer despliegue (o de cualquier cambio de esquema): ejecutar el workflow **Preparar y verificar Supabase (PMS)** (aditivo y sin tocar datos del piloto).
4. Comprobar: abrir la URL y recorrer el flujo; o ejecutar el workflow **Verificar reserva web** y `python scripts/e2e_navegador_reserva_web.py https://pms-reservas-atm.streamlit.app`.

## Incrustar en la página del hotel
```html
<iframe src="https://pms-reservas-atm.streamlit.app/?embed=true&hotel=ID" width="100%" height="1000" style="border:0" title="Reservas"></iframe>
<!-- o un enlace: -->
<a href="https://pms-reservas-atm.streamlit.app/?hotel=ID" target="_blank" rel="noopener">Reservar</a>
```
`ID` = número del hotel en el PMS (parámetro opcional: sin él se elige el hotel en la pantalla). `embed=true` oculta la barra y el pie de Streamlit y solo funciona en apps públicas de `*.streamlit.app`.

## Correo real (opcional, apagado por defecto)
Definir `PMS_CORREO_PROVEEDOR` (`resend` o `brevo`), `PMS_CORREO_API_KEY`, `PMS_CORREO_REMITENTE` y `PMS_CORREO_PERMITIDOS` (lista separada por comas). **Si el destinatario no está en esa lista, el correo se queda simulado.** Plantilla de ejemplo: `docs/plantilla_correo_confirmacion.html`.

## Fase 2: pasar a Wompi (pasos)
1. Cuenta de comercio Wompi (llaves públicas/privadas y secreto de eventos en sandbox primero).
2. Completar `PasarelaWompi` (crear transacción/enlace de pago, verificar `signature.checksum` — confirmar el algoritmo exacto con la documentación vigente) y redirigir al checkout alojado en lugar de `vista_checkout`.
3. **Receptor de webhooks fuera de Streamlit** (Streamlit no recibe POST externos): p. ej. una función serverless o un servicio pequeño (FastAPI) que llame a `reserva_web.procesar_evento(evento, firma, proveedor="wompi")`.
4. Correo real con dominio verificado; rol de base con permisos mínimos; captcha real (Cloudflare Turnstile / hCaptcha); política de devoluciones; términos y condiciones.

## Limitaciones del prototipo
- Streamlit Community Cloud duerme la app tras ~12 h sin visitas (primer acceso lento) y no recibe webhooks.
- La tarea programada de GitHub Actions puede retrasarse (mínimo 5 min) y se pausa tras 60 días sin actividad del repositorio; la disponibilidad no depende de ella.
- Una reserva web = una habitación por toda la estancia.
- Las opciones antiguas (sin `opcion_vence_en`) no se tocan.
- Un visitante público podría bloquear habitaciones del inventario piloto (mitigado con límites; en producción usar captcha real y un hotel/inventario aparte).
- `pms_auditoria` es de solo agregar: las pruebas dejan filas de auditoría aunque se borren sus datos.

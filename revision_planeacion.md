# Revisión de la planeación "StayCore PMS" frente a nuestro plan del piloto

Fecha: 28 de octubre de 2026
Archivos revisados (carpeta de Drive "Planeación CLAUDE"): copias en `/workspace/pms-hoteles/referencia/`
1. Informe de planificación · StayCore PMS.md (informe de concepción, 15 secciones)
2. fases.html (hoja de fases, pagos y conectividad con agencias en línea, con diagramas)
3. manual.html (manual de usuario de las 10 pantallas)
4. pms V1.1.html (maqueta visual navegable de las 10 pantallas)

---

## 1. ¿Qué es StayCore?

**Un producto de software por suscripción (SaaS) para varios alojamientos**, no un sistema para un solo hotel. Está pensado para tres tipos de negocio: **hostels** (se vende la cama), **apartamentos turísticos** y **hoteles rurales pequeños** (se vende la habitación). El informe recomienda empezar vendiendo a hostels.

**Idea central del informe:** lo difícil de un PMS no es la pantalla bonita, sino el modelo de datos. Tres principios que repite:
- Se vende el **tipo** de habitación; la habitación física concreta se asigna después (hasta el check-in).
- El **precio de cada noche se congela** al vender y nunca se recalcula.
- El inventario (cuántas hay) y las tarifas (cuánto cuestan) viven separados.

**Alcance por fases (12 meses):**
- **Fase 1, meses 0-4: núcleo del PMS.** Planning (calendario de cintas), plano del edificio, reservas, housekeeping, tarifas y restricciones, promociones, folio con cobro manual, reportes, varios hoteles en el mismo sistema, auditoría y usuarios/roles.
- **Fase 2, meses 4-7: pagos.** Pasarela, cobros diferidos, conciliación. Menciona Wompi y Mercado Pago (Colombia/LATAM), Stripe/Adyen/Redsys (Europa) y PayPal.
- **Fase 3, meses 7-12: distribución.** Conexión con Airbnb, Booking, Expedia, Hostelworld y Despegar mediante un "channel manager" externo (costo de referencia del informe: unos US$130 al mes por propiedad).
- Regla de corte: no se pasa de fase hasta que un hotel real haya operado un mes completo.

**Las 10 pantallas:** Dashboard, Planning, Plano/Disponibilidad, Reservas, Housekeeping, Tarifas e inventario, Promos y cupones, CRM·Inbox (WhatsApp/Telegram/correo con copiloto de IA), Reportes, Integraciones.

**Roles (4):** Recepción, Housekeeping, Revenue/Comercial, Dirección/Admin.

**Stack propuesto:** PostgreSQL 16 con seguridad por filas (RLS) para separar clientes; backend NestJS, Django, .NET o Go (a elegir según el equipo); frontend React con TypeScript; librería de calendario de pago (Bryntum, vis-timeline o dhtmlxScheduler); Redis y cola de trabajos; almacenamiento tipo S3; hosting en Railway, Render o Fly.io. No es Streamlit ni Supabase.

**Modelo de datos del informe (nombres en inglés):** Organization → Property → UnitType → Unit → Bed; `inventory_day`, `rate_day`, `booking` + `booking_unit` + `booking_night`, huéspedes, folios con líneas de cargo y de pago, housekeeping, planes tarifarios, promociones, roles, auditoría y un `outbox_event`.

**La maqueta "pms V1.1"** es una página HTML estática, sin base de datos ni servidor. Todo es de ejemplo: el hotel ficticio "Mirador del Mar · Altea" (España), 18 habitaciones en 3 plantas (Familiar Mar, Triple Mar, Doble Monte/Patio, Individual), precios en euros, y integraciones simuladas como "Conectado" (Channex, Stripe, WhatsApp, Holded, Nuki, etc.). Sirve como diseño visual de referencia, pero no como código reutilizable.

---

## 2. Qué coincide con nuestro plan

- Mismos módulos base: reservas, calendario/disponibilidad de habitaciones, tarifas por tipo, housekeeping, folio con cargos y pagos, reportes de ocupación, huéspedes, roles y auditoría.
- Misma secuencia: primero un núcleo sencillo con cobro manual; pagos y agencias en línea después. El informe también deja fuera la contabilidad completa y el restaurante.
- Vender por **tipo de habitación** y asignar la habitación física después.
- Al hacer check-out la habitación pasa sola a "sucia" (lo dice el manual).
- Cargos y pagos como líneas separadas, y registro de auditoría que no se puede apagar.
- Comprobante/folio como documento aparte de la factura legal. El informe deja la facturación fiscal a integraciones externas.
- Pruebas contra dobles ventas de la misma habitación (el informe pide una prueba de concurrencia).
- Hotel piloto real y pruebas con usuarios. El informe lo pide expresamente en su punto 14.

## 3. Qué tiene de más y de menos frente a nuestro plan

**De más en StayCore (no está en nuestro plan):**
- Varios hoteles y varios clientes en el mismo sistema (multi-tenant con RLS).
- Hostels con camas (nivel "Cama" dentro de la habitación).
- Planning arrastrable (tape chart) y plano visual del edificio por plantas con suplementos (vista al mar, planta, adulto/niño extra, recargo de fin de semana).
- Promociones y cupones con simulador; reglas de restricción (estancia mínima, cerrado a la llegada/salida, stop-sell).
- CRM/Inbox con WhatsApp, Telegram, correo y copiloto de IA.
- Pagos en línea, tokenización, webhooks, cuentas conectadas con comisión (fase 2).
- Conexión con agencias en línea (OTAs) con cola, debounce y manejo de sobreventa (fase 3).
- Check-in en línea, cerraduras inteligentes, ERP (Holded), precios dinámicos (PriceLabs).
- Rol extra: Revenue/Comercial.
- Dashboard con KPIs avanzados (ADR, RevPAR, pickup, mix por canal) e informes programados por correo.

**De menos en StayCore (sí está en nuestro plan y ellos no lo detallan):**
- **Ley 1581 (Colombia):** no la nombran. Su cumplimiento normativo es solo español (RD 933/2021, Veri*Factu, tasa turística). Sí hablan de consentimientos por finalidad, cifrado de documentos y retención con borrado, pero sin el marco colombiano.
- **Comprobante PDF simple y facturación DIAN:** su facturación fiscal es la española.
- **Check-in/check-out como flujo propio:** existe en el manual ("Flujos diarios") pero no hay tabla de estancias explícita; la reserva pasa a "Alojado".
- Moneda y pasarela colombiana en la maqueta (usa euros, Stripe y Redsys). El informe sí menciona Wompi/PSE en el texto.

## 4. Riesgos e incoherencias que veo

1. **Alcance imposible para plan gratuito.** StayCore necesita Redis, trabajos en cola, almacenamiento tipo S3 y hosting de backend (Railway/Render/Fly.io). Eso no cabe en Streamlit Community Cloud + Supabase Free. Calculan 12 meses de desarrollo; nuestro piloto es una fracción de eso.
2. **Stack distinto.** React + backend propio frente a Streamlit + Supabase. No se pueden "adoptar" tal cual. Además Streamlit **no soporta arrastrar y soltar** barras de reserva: el Planning tendría que ser de solo lectura (rejilla de colores) y editar con formularios.
3. **Mercado equivocado para nuestro usuario.** El informe dice que el mercado inicial es una decisión pendiente (punto 14: España frente a Colombia). La maqueta y las normas están en clave España. Para ATm (Colombia) habría que sustituir esos elementos.
4. **Maqueta con integraciones "Conectado" que no existen.** Si se muestra al cliente sin aclararlo, repite el error de "correos simulados sin avisarlo". También trae cifras inventadas (1.284 reservas, 4 pendientes de partes de viajeros, "Veri*Factu plazo 01/01/2027"). Esos datos son de ejemplo y no deben tomarse como hechos.
5. **Incoherencia interna menor.** La Fase 1 del informe no incluye CRM/Inbox, IA ni Integraciones, pero el manual y la maqueta las muestran como parte de las 10 pantallas. Conviene decir claramente cuáles entran en cada fase.
6. **El propio informe duda de que convenga construir.** Recomienda evaluar seriamente si el proyecto debe existir, porque ya hay productos maduros (Cloudbeds, Mews, QloApps). Para un piloto de demostración está bien, pero conviene decirle al usuario esa advertencia.
7. **Seguridad y datos personales.** El informe exige cifrar documentos de identidad, registrar cada consulta de datos personales, borrado automático y contratos con proveedores (incluida la IA). Eso es más de lo que un piloto gratuito debe prometer. En el piloto: solo datos ficticios.
8. **Respaldos.** El informe pide recuperación a un punto en el tiempo y pruebas de restauración. Eso no lo da el plan gratuito de Supabase como tal (por verificar). Nuestro respaldo cifrado con GitHub Actions es una alternativa más modesta, y hay que decirlo así.
9. **Legal Colombia (observación mía, no está en los archivos; por verificar con asesoría):** DIAN (factura electrónica), registro de huéspedes extranjeros ante Migración Colombia, y Registro Nacional de Turismo del hotel. El piloto debe decir que no emite factura DIAN.
10. **Estado ("Previo al inicio de desarrollo").** No hay código, solo planeación y maqueta. No existe nada ya construido que se pueda reutilizar.

---

## 5. Recomendación: enfoque híbrido

**No adoptar StayCore completo; seguir nuestro plan (piloto de un solo hotel en Streamlit + Supabase) pero incorporar las decisiones de modelo de datos que el informe considera caras de corregir después.** Usar la maqueta V1.1 como referencia visual de pantallas.

### Cambios al alcance mínimo
**Añadir (barato, y evita rehacer el modelo):**
- Precio congelado por noche en cada reserva.
- Campos `canal` (por defecto "directo"), comisión, neto y referencia externa única en la reserva, aunque todo sea manual.
- Estados de reserva del informe: consulta → opción → confirmada → alojado → salida; más cancelada y no-show.
- Bloqueos de habitación por mantenimiento (fuera de servicio).
- Housekeeping con estados: sucia → en limpieza → inspección → lista (+ fuera de servicio).
- Restricciones simples en tarifas: estancia mínima y cierre de ventas.
- Dashboard simple del día: llegadas, salidas, ocupación e ingresos.
- Aviso visible de que correos, pagos e integraciones son simulados.

**Dejar fuera del piloto (como ya dijimos, y añadir):**
- Multihotel/SaaS, hostel con camas, promos y cupones, CRM/WhatsApp/IA, pasarelas de pago, conexión con agencias, cerraduras, ERP, check-in en línea.
- Planning con arrastrar y soltar (en Streamlit será una rejilla de solo lectura).

**Roles:** mantener 3 (recepción, gerencia, housekeeping). Gerencia hace también de "revenue"; dejar el 4.º rol como futuro.

### Cambios a las tablas `pms_`
Pasamos de 12 a unas 15 tablas:
- `pms_hoteles`, `pms_usuarios`, `pms_tipos_habitacion`, `pms_habitaciones`, `pms_huespedes`, `pms_estancias`, `pms_housekeeping`, `pms_cargos`, `pms_pagos`, `pms_auditoria`: se mantienen.
- `pms_tarifas`: añadir temporada (fechas), estancia mínima y cierre de ventas.
- `pms_reservas`: añadir `canal`, `comision`, `neto`, `referencia_externa` (única), estado ampliado y `hotel_id`.
- **Nueva `pms_reserva_noches`:** una fila por noche con el precio congelado y la habitación asignada. Con una restricción de unicidad (habitación + noche) la base de datos impide vender dos veces la misma habitación en la misma noche. Es más sencillo que la solución avanzada del informe y no exige extensiones especiales.
- **Nueva `pms_consentimientos`:** Ley 1581, un registro por finalidad, con fecha, texto aceptado y versión.
- **Nueva `pms_bloqueos`:** habitaciones fuera de servicio por fechas y motivo.
- **Nueva (opcional) `pms_inventario_dia`:** solo si queremos reportes rápidos. Para 18 habitaciones se puede calcular la disponibilidad desde las noches reservadas.
- `pms_cargos` y `pms_pagos` deben ser líneas independientes con su estado (nunca un "pagado" sí/no). `pms_auditoria` solo se escribe y no se edita ni borra.
- Todas con `hotel_id`, para no rehacer nada si luego hay más de un hotel.
- Omitimos la tabla de eventos de salida ("outbox") hasta que haya integraciones.

**Plan gratuito:** sigue cabiendo; con 18 habitaciones y datos de prueba el espacio es mínimo.

**Costos si pasa a producción:** el informe solo da un dato: el channel manager unos US$130/mes por propiedad (fase 3). Mi estimado de US$25-50/mes para un hotel con Supabase Pro sigue valiendo para el alcance mínimo, sin canales ni WhatsApp.

---

## 6. Preguntas esenciales para el usuario (máximo 3)

1. **¿Para qué mercado es el piloto: Colombia (hotel con facturación DIAN, pesos, Ley 1581) o replicar el caso de StayCore (España, euros, hostels/apartamentos)?** Y, ¿un hotel con habitaciones, o hostel con camas?
2. **¿Quiere que el piloto se parezca a la maqueta "pms V1.1" (las 10 pantallas) o solo usarla como inspiración para un alcance más corto?** Importante: Streamlit no permite arrastrar reservas ni copiar ese diseño exacto.
3. **¿Hay un hotel o equipo real que lo pruebe (cuántas habitaciones), y el piloto es solo demostración con datos ficticios?**

# Informe de planificación · StayCore PMS
## Sistema de gestión de alojamientos (hostels, apartamentos turísticos y hoteles rurales pequeños)

**Versión:** 1.0 · Documento de cierre de la fase de concepción
**Estado:** Previo al inicio de desarrollo
**Ámbito:** Producto SaaS multipropiedad en la nube

---

## 1. Resumen ejecutivo

Este documento consolida las decisiones, los criterios y las advertencias acumuladas durante la fase de concepción de un PMS (Property Management System) en modalidad SaaS, dirigido a tres verticales de alojamiento que comparten un mismo núcleo funcional pero difieren en su unidad de venta: hostels con camas en dormitorio compartido, apartamentos turísticos y hoteles rurales pequeños.

La tesis central del proyecto es que esos tres verticales pueden servirse con un único producto siempre que el modelo de inventario sea genérico desde el primer día, y que el fracaso de la mayoría de los PMS nuevos no viene de la interfaz ni del número de funcionalidades, sino de un modelo de datos que no soporta la realidad operativa del sector: inventario por tipo frente a unidad física, precios congelados en el momento de la venta, y concurrencia entre canales de distribución.

El desarrollo se plantea en tres fases secuenciales. La primera entrega un PMS operativo y vendible con cobro manual y sin conectividad con agencias en línea. La segunda incorpora pasarelas de pago. La tercera, la distribución automatizada hacia OTAs. Esta secuencia no es una concesión al presupuesto: responde a que ni los pagos ni la distribución pueden construirse de forma fiable sobre un inventario que todavía no ha demostrado serlo en producción.

La recomendación transversal más importante del informe es que, antes de escribir código propio, se evalúe seriamente si el proyecto debe existir. Para operar unos pocos alojamientos propios, el mercado ofrece soluciones maduras (Cloudbeds, Mews, o QloApps como opción de código abierto autoalojada). Construir desde cero solo se justifica si el objetivo es un producto SaaS con un nicho y una propuesta de valor diferenciada.

---

## 2. Alcance y posicionamiento

### 2.1 Los tres verticales y su diferencia esencial

| Vertical | Unidad vendible | Particularidad operativa |
|---|---|---|
| **Hostel** | La cama dentro de un dormitorio | Inventario agregado por tipo de dormitorio; género del dormitorio como atributo; alta rotación; estancias cortas; cliente joven e internacional |
| **Apartamento turístico** | El alojamiento completo | Sin recepción física; check-in autónomo con cerradura inteligente; limpieza entre estancias con inspección; normativa local de vivienda turística |
| **Hotel rural pequeño** | La habitación, asignada por tipo | Volumen bajo, ADR alto; venta telefónica frecuente; fuerte peso de la elección visual de habitación (vistas, planta) |

### 2.2 Secuencia comercial recomendada

Entrar primero por **hostels**: es donde el dolor operativo es mayor (gestión de camas, no de habitaciones), donde la competencia especializada es menor, y donde el modelo de inventario más complejo obliga a construir bien el núcleo. Una vez validado ahí, apartamentos turísticos y hoteles rurales se cubren con un subconjunto del mismo modelo, no con excepciones en el código.

### 2.3 Fuera de alcance en esta planificación

Restaurante y punto de venta, spa y actividades, gestión de personal y nóminas, contabilidad completa (se integra, no se construye), y motor de reservas público con diseño personalizable por cliente (se entrega un motor estándar embebible).

---

## 3. Modelo de dominio y de datos

Esta sección concentra aproximadamente el setenta por ciento del éxito técnico del proyecto. Un error aquí es irrecuperable sin migración de datos en producción.

### 3.1 Jerarquía

```
Organization (tenant)
  └── Property
        └── UnitType          ← lo que realmente se vende
              └── Unit        ← la habitación o apartamento físico
                    └── Bed   ← solo si UnitType.sells_beds = true
```

El principio rector: **se vende el `UnitType`, nunca la `Unit`**. La asignación a una unidad física concreta es una decisión operativa posterior, que recepción puede cambiar hasta el check-in. Entender y respetar esto evita la mayor parte de los errores de diseño y de uso del sistema.

### 3.2 Tablas núcleo

**`inventory_day`** — una fila por tipo de unidad y fecha. Es la única fuente de verdad sobre disponibilidad.

| Campo | Propósito |
|---|---|
| `unit_type_id`, `date` | Clave compuesta |
| `units_total` | Inventario físico del tipo |
| `units_ooo` | Fuera de servicio (avería, obra) |
| `units_sold` | Vendidas |
| `units_held` | Retenidas temporalmente (opciones, pagos en curso) |
| `overbook_allow` | Margen de sobreventa autorizado |
| `stop_sell` | Cierre total de ventas |

Con restricción de integridad: `CHECK (units_sold <= units_total - units_ooo + overbook_allow)`.

**`rate_day`** — una fila por tipo, plan tarifario y fecha, con precio por ocupación, estancia mínima y máxima, CTA (cerrado a la llegada), CTD (cerrado a la salida) y cierre.

La separación entre inventario y tarifa es deliberada y no negociable: permite cerrar ventas sin tocar precios, y cambiar precios sin tocar inventario.

**`booking` + `booking_unit` + `booking_night`** — la reserva es una cabecera con N estancias, y cada estancia se descompone en noches. Cada noche almacena el precio con el que se vendió. **Ese precio nunca se recalcula.** Cambiar la tarifa pública mañana no puede alterar ninguna reserva existente; si procede un ajuste, se hace explícitamente desde el folio y queda auditado.

### 3.3 Generación del calendario

Pre-generar veinticuatro meses de `inventory_day` y `rate_day` mediante un job diario. No generar filas bajo demanda: introduce latencia impredecible en el motor de reservas y complica el bloqueo pesimista.

### 3.4 Ciclo de vida de la reserva

```
consulta → opción → confirmada → alojado → salida realizada
                 ↘ cancelada    ↘ no-show
```

Cada transición escribe en un log de eventos inmutable con usuario, timestamp y valor anterior. El log no se puede desactivar ni editar.

### 3.5 Resto del dominio

Huéspedes con deduplicación por documento, correo y teléfono; perfiles de CRM con historial, preferencias, idioma y consentimientos; folios con líneas de cargo y de pago tipadas e independientes (nunca un campo booleano «pagado»); tablero de housekeeping con estados de limpieza e incidencias; planes tarifarios con relación padre-hijo y ajuste porcentual; motor de promociones y cupones; roles y permisos; y auditoría transversal.

---

## 4. Funcionalidades del producto

### 4.1 Mapa de pantallas

| Grupo | Pantalla | Propósito |
|---|---|---|
| Operativa | **Dashboard** | KPIs del negocio y centro de alertas accionables |
| Operativa | **Planning (tape chart)** | Calendario de cintas: asignación, cambios y bloqueos |
| Operativa | **Plano / Disponibilidad** | Selección visual de habitación sobre el plano del edificio |
| Operativa | **Reservas** | Listado maestro y ficha completa |
| Operativa | **Housekeeping** | Tablero kanban de limpieza y mantenimiento |
| Comercial | **Tarifas e inventario** | Rejilla editable de precios y restricciones |
| Comercial | **Promos y cupones** | Motor de reglas comerciales con simulador |
| Comercial | **CRM · Inbox** | Bandeja omnicanal con copiloto de IA |
| Análisis | **Reportes** | Rendimiento, pace, producción por canal, caja |
| Sistema | **Integraciones** | Estado de salud de cada conexión externa |

### 4.2 Detalle funcional por pantalla

**Dashboard.** Seis indicadores (ocupación, ADR, RevPAR o RevPAB según vertical, ingreso del mes, pickup a siete días y tasa de cancelación), gráfico combinado de ocupación y ADR a catorce días, donut de mix por canal con ADR neto de comisión, listas de llegadas y salidas del día, y centro de alertas. Las alertas son accionables: cada una enlaza a la pantalla donde se resuelve, con el filtro ya aplicado. Las rojas bloquean operativa (riesgo de sobreventa, cobro rechazado); las ámbar son plazos (documentación legal pendiente).

**Planning.** Filas de unidades y camas agrupadas por tipo, columnas de días, barras de reserva con código de color por estado. Soporta arrastre para asignar, mover entre unidades, alargar o acortar estancias, y crear bloqueos sobre celdas vacías. Al alargar, se recalculan únicamente las noches nuevas con la tarifa vigente. Es imprescindible usar una librería de calendario virtualizada y no construirla: es el componente que más tiempo consume si se aborda desde cero.

**Plano / Disponibilidad.** Buscador por fechas y ocupantes, KPIs del rango, alzado del edificio por plantas, plano de planta con las habitaciones y sus estados, panel de detalle con desglose de precio noche a noche y tabla comparativa por número de ocupantes, y barra de carrito para selección multi-habitación. Los suplementos modelados incluyen vista, planta, ocupantes adicionales diferenciando adulto y niño, y recargo de fin de semana.

**Reservas.** Filtros combinables reflejados en la URL para poder compartir vistas, ficha con pestañas de estancia, huéspedes y documentación, folio y pagos, comunicaciones y registro de cambios, y acciones en bloque.

**Housekeeping.** Cinco columnas de estado, tarjetas con tipo de servicio y prioridad según llegadas tempranas, asignación de responsable, reporte de incidencias con fotografía, y vistas por día y por planta. Diseñado para móvil.

**Tarifas e inventario.** Rejilla con filas de disponibilidad (calculada, no editable), precio, estancia mínima, CTA, CTD y stop-sell. Edición por celda o por rango arrastrado, aplicación selectiva por día de la semana, panel de cambios pendientes con publicación explícita, y reglas de yield automáticas con simulación del efecto.

**Promos y cupones.** Tipos de descuento (porcentaje, importe fijo, noches gratis), ventana de reserva y ventana de estancia como conceptos separados, condiciones de antelación, acumulabilidad con prioridad numérica, límites de uso, y simulador obligatorio antes de activar.

**CRM · Inbox.** Conversaciones unificadas de WhatsApp, Telegram y correo por huésped, notas internas no visibles para el cliente, sugerencias del copiloto como borrador editable, y panel con ficha del huésped, reserva vinculada, historial y estado de la documentación legal.

**Reportes.** Rendimiento, pace y pickup, producción por canal con comisión e ingreso neto, cancelaciones y no-shows, caja y cobros, y mercados y segmentos. Todo informe es navegable hasta la reserva que origina el dato, y exportable o programable por correo.

**Integraciones.** Una tarjeta por conexión con estado, última sincronización, errores recientes con posibilidad de reintento, y configuración de credenciales, mapeos y webhooks.

### 4.3 Marco común de interfaz

Selector de propiedad en la barra superior que cambia el contexto de todas las pantallas; buscador global con atajo de teclado; botón de sincronización manual de canales; tema claro y oscuro como preferencia por usuario; contadores de trabajo pendiente en los ítems del menú; y convención de color consistente en todo el producto (azul confirmado, verde correcto o alojado, ámbar atención, rojo bloqueo o error, violeta canal externo, gris histórico).

### 4.4 Roles

| Rol | Acceso | Restricciones |
|---|---|---|
| Recepción | Operativa completa e Inbox | Sin edición de tarifas ni promociones; descuentos limitados; sin exportación masiva |
| Housekeeping | Solo tablero de limpieza | Sin precios, sin datos de pago, sin CRM |
| Revenue / Comercial | Tarifas, promos, reportes, distribución | Lectura en operativa; sin acceso a documentos de identidad |
| Dirección / Admin | Todo, configuración y auditoría | Único que anula registros y modifica facturas emitidas |

---

## 5. Arquitectura y stack técnico propuesto

### 5.1 Decisiones estructurales

| Decisión | Propuesta | Razón |
|---|---|---|
| Base de datos | PostgreSQL 16 o superior | `btree_gist` para restricciones de exclusión sobre rangos, RLS nativo para multi-tenancy, tipos de rango de fechas, madurez transaccional |
| Topología de servicio | Monolito modular | Microservicios al inicio multiplican el coste operativo sin resolver ningún problema real a esta escala. La modularidad se logra con límites de módulo bien definidos, no con despliegues separados |
| Backend | NestJS, Django, .NET o Go | Cualquiera sirve; decide la experiencia del equipo, no la moda |
| Frontend | React con TypeScript y TanStack Query | Gestión de estado de servidor resuelta; tipado necesario en un dominio con tantas reglas |
| Calendario | Librería virtualizada de terceros | Bryntum, vis-timeline o dhtmlxScheduler. No construir el tape chart |
| Caché y colas | Redis y un worker de colas | BullMQ, Celery o Hangfire según el stack |
| Almacenamiento | Objetos compatibles con S3 | Documentos, fotografías de incidencias, exportaciones |
| Infraestructura | PaaS gestionado al inicio | Railway, Render o Fly.io. Kubernetes solo cuando el volumen lo imponga |

### 5.2 Multi-tenancy

Tabla compartida con columna `tenant_id` y aislamiento mediante Row Level Security de PostgreSQL. Puntos críticos de implementación: la política debe declararse con `FORCE ROW LEVEL SECURITY` para que aplique también al propietario de la tabla; la aplicación debe conectarse con un rol que no sea superusuario, porque los superusuarios ignoran RLS; el `tenant_id` debe establecerse por sesión o transacción mediante `set_config`; y debe ser la primera columna de todos los índices compuestos.

Base de datos dedicada únicamente para clientes de nivel Enterprise con requisitos contractuales de aislamiento físico. Introducir esa complejidad antes de tener ese cliente es trabajo perdido.

### 5.3 Arquitectura de integración en tres capas

```
┌─────────────────────────────────────────────────────┐
│  Proveedores externos                               │
│  OTAs · Channel manager · Pasarelas · ERP · IA      │
└─────────────────────────────────────────────────────┘
                        ↕
┌─────────────────────────────────────────────────────┐
│  Capa anticorrupción (adaptadores propios)          │
│  Mapeo · Traducción · Firma · Deduplicación · Cola  │
└─────────────────────────────────────────────────────┘
                        ↕
┌─────────────────────────────────────────────────────┐
│  Núcleo de dominio                                  │
│  Inventario · Reservas · Folio · Operativa · Audit  │
└─────────────────────────────────────────────────────┘
```

El dominio nunca conoce a un proveedor concreto. Si se cambia de channel manager o de pasarela, se reescribe un adaptador y nada más. Si el proveedor se filtra al dominio, el cambio se convierte en un proyecto completo.

---

## 6. Retos técnicos previstos y cómo sortearlos

### 6.1 Concurrencia en la venta del último recurso

**El reto.** Dos reservas simultáneas sobre la última cama disponible, llegando por caminos distintos (motor directo y canal externo) y resolviéndose en milisegundos.

**La solución.** Tres mecanismos acumulativos, no alternativos. Primero, bloqueo pesimista con `SELECT ... FOR UPDATE` sobre la fila de `inventory_day` antes de decrementar, dentro de la misma transacción que crea la reserva. Segundo, la restricción `CHECK` en base de datos como red de seguridad: si la lógica de aplicación falla, la base de datos rechaza la operación. Tercero, para la asignación a unidad física, una restricción de exclusión con `btree_gist`:

`EXCLUDE USING gist (unit_id WITH =, stay_range WITH &&)`

que hace matemáticamente imposible que dos estancias solapen en la misma unidad.

### 6.2 Reintentos y mensajes duplicados

**El reto.** Toda integración entrante (pasarelas, canales, webhooks) entregará el mismo evento más de una vez. Es una garantía del protocolo, no una anomalía.

**La solución.** Clave de idempotencia con índice único en toda operación que cree o modifique estado: referencia externa de la reserva para los canales, identificador de transacción para los pagos. El flujo correcto es comprobar existencia antes de procesar, y si ya existe, responder éxito sin volver a aplicar nada.

### 6.3 Publicación de disponibilidad sin agotar cuotas

**El reto.** Los canales imponen límites estrictos. Despegar, por ejemplo, limita a cinco peticiones por segundo, sesenta por minuto y cuatro mil por día, por cliente y por hotel, y prohíbe actualizaciones concurrentes de disponibilidad o tarifas sobre el mismo hotel. Su documentación advierte expresamente del riesgo de que un PMS resincronice un año entero tras cada edición menor [Source](https://channel.despegar.com/portal/documentation/integrating).

**La solución.** Una tubería de salida con cinco etapas. Patrón outbox, escribiendo el evento en la misma transacción que el cambio de negocio. Debounce de treinta a sesenta segundos para agrupar ediciones consecutivas. Coalescing de rangos de fechas contiguos con el mismo valor en un solo mensaje. Diff contra el último estado publicado para descartar lo que no cambió. Y cola serializada por hotel, con un único worker activo por propiedad.

### 6.4 La ventana de doble venta

**El reto.** Entre que un canal vende y el PMS se entera transcurre un tiempo durante el cual el inventario está desactualizado. Con push o webhook son segundos; con pull periódico, minutos; con sincronización iCal puede llegar a doce horas según la frecuencia de sondeo de la plataforma, sin que el gestor pueda configurarlo [Source](https://rentalsunited.com/blog/airbnb-calendar-sync/).

**La solución.** Priorizar siempre push sobre pull y descartar iCal para uso comercial. Mantener una reserva de seguridad: no publicar la última unidad disponible simultáneamente en todos los canales. Y aceptar que la ventana no se elimina, solo se reduce, por lo que hace falta detección y gestión activa de la sobreventa.

**Regla de comportamiento ante sobreventa.** Si llega una reserva de un canal y el inventario ya está agotado, **la reserva se acepta igualmente**. El canal ya la vendió y rechazarla no la deshace; devolver un error solo provoca reintentos indefinidos. Se crea, se marca como sobreventa, y se levanta alerta en el dashboard para que recepción reubique antes de la llegada.

### 6.5 Mapeo entre modelos de inventario incompatibles

**El reto.** Cada canal modela el inventario de forma distinta, y ninguno coincide exactamente con el modelo interno.

| Canal | Modelo | Implicación |
|---|---|---|
| Airbnb | Listing igual a unidad física; sin concepto de cama vendible en dormitorio | Los dormitorios compartidos no encajan de forma nativa |
| Despegar | Allotment por habitación y plan tarifario, mensajes OTA en XML | Requiere descubrir la estructura remota antes de sincronizar |
| Booking y Expedia | Tipo de habitación con allotment, restricciones completas | Encaje natural |
| Hostelworld | Modela camas en dormitorio | El único que encaja de forma nativa con hostels |

**La solución.** Una tabla de mapeo por tenant que absorba todas las diferencias, con campos como referencia externa, indicador de si el canal vende la unidad completa, modelo de pago, modelo de comisión y qué restricciones soporta. El dominio no debe enterarse de que los canales son distintos.

### 6.6 Acceso restringido a determinados canales

**El reto.** Airbnb no tiene API pública. El acceso se concede solo a socios aprobados, y actualmente no se aceptan nuevas solicitudes de acceso ni de partnership [Source](https://hospitable.com/airbnb-partnerships). Los socios deben superar una revisión de seguridad de datos y de calidad de la API, y cumplir estándares de integración, técnicos y de rendimiento [Source](https://news.airbnb.com/announcing-our-2025-preferred-software-partners). En la cohorte de 2025 figuran treinta y dos empresas en todo el mundo.

**La solución.** Integrar un channel manager white-label que ya sea socio certificado. Con una sola API se alcanza Airbnb, Booking, Expedia, Hostelworld, Despegar y decenas más. La integración directa con un canal concreto se plantea solo cuando el volumen justifique eliminar el coste del intermediario.

### 6.7 Alcance regulatorio de los pagos

**El reto.** Manipular datos de tarjeta dispara requisitos de cumplimiento desproporcionados para un equipo pequeño.

**La solución.** Que el dato de tarjeta no entre nunca en el sistema. Captura exclusiva mediante checkout alojado o widget del proveedor, y almacenamiento únicamente del token devuelto. Esto mantiene el alcance de cumplimiento en el nivel más simple posible y permite igualmente los cobros diferidos que la operativa hotelera necesita (no-show, penalización, daños, cargos al check-out).

### 6.8 Rendimiento del tape chart y del motor de disponibilidad

**El reto.** Un planning de treinta días con ciento cincuenta unidades son cuatro mil quinientas celdas, más las barras de reserva, renderizadas con interacción de arrastre fluida.

**La solución.** Virtualización de filas y columnas, librería especializada, consulta agregada única al backend (no una por fila), y caché en Redis de la disponibilidad por tipo y rango con invalidación dirigida al cambiar `inventory_day`.

### 6.9 Datos de huésped incompletos en reservas de canal

**El reto.** Las OTAs entregan un nombre y un canal de mensajería, no documentación de identidad ni datos de los acompañantes, que la normativa española exige comunicar.

**La solución.** Un flujo de check-in en línea propio: tras la confirmación se envía un enlace al huésped por su canal, se recoge allí la documentación y la firma, y de ahí se alimenta la comunicación a la administración. Es simultáneamente una obligación resuelta y una función de valor del producto.

### 6.10 Diferencias en quién cobra

**El reto.** Mezclar en el mismo saldo las reservas que cobra la plataforma y las que cobra el alojamiento desalinea la conciliación contable. Airbnb, por ejemplo, cobra al huésped y liquida al anfitrión normalmente veinticuatro horas después del check-in [Source](https://www.igms.com/airbnb-payment-methods/), de modo que la reserva entra pagada y no debe generar saldo pendiente.

**La solución.** Campo de modelo de pago en el mapeo de canal, con los estados «cobra la plataforma» y «cobra el alojamiento». Solo los extras vendidos directamente pasan por la pasarela propia.

---

## 7. Integraciones previstas

### 7.1 Pagos

| Proveedor | Ámbito | Observaciones |
|---|---|---|
| **Wompi (Bancolombia)** | Colombia | Tarjetas, Nequi, transferencia Bancolombia y PSE. Dispone de fuentes de pago para tokenización y de API de dispersión a terceros |
| **Mercado Pago** | LATAM | Ofrece Split Payments específicamente para plataformas con modelo marketplace, dividiendo el cobro entre vendedor y plataforma [Source](https://www.mercadopago.com.pe/developers/en/news/2024/01/23/New-Split-Payments-documentation) |
| **Stripe / Adyen / Redsys** | Europa | Para el mercado español, con tokenización y autenticación reforzada |
| **PayPal** | Internacional | Complementario para reservas prepagadas; su modelo de disputas es desfavorable al comercio y no encaja bien con cobros diferidos |

**Validación de webhooks.** Wompi notifica mediante POST a una URL de eventos distinta por entorno, y espera respuesta HTTP 200; en caso contrario reintenta un máximo de tres veces en veinticuatro horas, a los treinta minutos, a las tres horas y a las veinticuatro horas. La integridad se verifica con un checksum SHA256 presente en la cabecera `X-Event-Checksum`, calculado concatenando los valores de los campos listados en el propio evento, el timestamp y el secreto de eventos; si no coincide, el evento debe ignorarse [Source](https://docs.wompi.co/docs/colombia/eventos/).

Dos advertencias que rompen integraciones en producción: la lista de campos que entra en el checksum puede variar, por lo que debe leerse del evento y no codificarse de forma fija; y el secreto de eventos no es la llave privada de la cuenta.

**Decisión estructural sobre custodia de fondos.** Debe tomarse antes de elegir proveedor y consultarse con asesoría legal y fiscal.

El modelo recomendado es el de **cuentas conectadas**: cada alojamiento tiene su propia cuenta de comercio, el SaaS actúa como plataforma y cobra su comisión mediante split, y el dinero va directo al alojamiento. No se custodian fondos ajenos, no se asumen contracargos y no se adquiere la condición de agregador de pagos, figura que en varios países exige licencia.

El modelo alternativo, de **cuenta única propia**, es operativamente más sencillo al principio y mucho más caro después: convierte a la empresa en intermediario financiero, con riesgo de contracargo, obligaciones de prevención de blanqueo y una carga contable considerable.

### 7.2 Distribución

Conexión mediante channel manager white-label (Channex, Beds24 u otro con certificación vigente en los canales objetivo). Coste de referencia en torno a los ciento treinta dólares mensuales por propiedad, repercutible al cliente.

Para una eventual integración directa con Despegar, su interfaz usa mensajes OTA 2013B en XML sobre HTTPS, con un subconjunto acotado de la especificación y una operación por hotel. La autenticación combina una clave de API propia del channel manager, entregada solo tras certificar, con credenciales por propiedad que el hotel genera desde su extranet [Source](https://channel.despegar.com/portal/documentation). Dispone de entorno sandbox con hoteles de prueba y comportamientos simulados por mes del año para ejercitar los caminos de error [Source](https://channel.despegar.com/portal/documentation/integrating).

### 7.3 Mensajería y CRM

WhatsApp Business Platform, Telegram Bot API y correo transaccional (Postmark o equivalente). En WhatsApp conviene tener presente que la respuesta libre solo es posible durante un periodo limitado tras el último mensaje del cliente, que fuera de él se requieren plantillas aprobadas, y que la facturación es por mensaje entregado con tarifa variable según categoría y mercado. Las condiciones cambian con frecuencia y deben consultarse en la documentación oficial vigente antes de diseñar cualquier campaña.

### 7.4 Inteligencia artificial

Copiloto de respuestas en el Inbox, resumen de conversaciones, sugerencias de precio y clasificación de incidencias. Principios de diseño: la IA produce borradores, no envía por su cuenta salvo en respuestas automáticas a preguntas frecuentes explícitamente habilitadas; los datos enviados al proveedor deben estar delimitados y justificados por una base legal; y toda sugerencia aplicada queda registrada como acción del usuario que la aceptó, no del sistema.

### 7.5 ERP y contabilidad

Envío de facturas, cobros y asientos al software administrativo del cliente (Holded u otros). Puntos de atención: mapeo de cuentas y de tipos impositivos, y conciliación mensual obligatoria. Conviene exponer además una API pública propia para que clientes con ERP no soportado puedan integrarse.

### 7.6 Otros

Cerraduras inteligentes con códigos ligados a la estancia, que deben caducar al check-out y regenerarse si la reserva cambia; y herramientas de precios dinámicos como fuente de recomendaciones.

---

## 8. Cumplimiento normativo (mercado español)

Esta sección es orientativa y debe contrastarse con asesoría especializada y con las fuentes oficiales, porque los plazos y los campos exigidos han cambiado varias veces.

**Registro documental de viajeros.** El Real Decreto 933/2021 establece obligaciones de registro y comunicación de datos de viajeros para establecimientos de hospedaje, con remisión por servicio web a la plataforma habilitada. El sistema debe marcar en la ficha de reserva los huéspedes con documentación incompleta y los ya comunicados, y generar alerta cuando se aproxime el plazo.

**Facturación verificable.** El marco de sistemas informáticos de facturación con registro verificable afecta a la emisión de facturas. Los plazos de adaptación han sido modificados por normativa posterior y deben confirmarse en la sede electrónica de la Agencia Tributaria antes de comprometer fechas de desarrollo.

**Protección de datos.** Cifrado de documentos de identidad en reposo, control de acceso por rol, registro de cada consulta a datos personales, plazos de retención con borrado automático, gestión de consentimientos de marketing separados por finalidad, y contratos de encargado de tratamiento con cada proveedor, incluido el de inteligencia artificial.

**Tasa turística.** Variable por comunidad autónoma y municipio. Debe modelarse como concepto separado del precio, con posibilidad de exenciones por edad y por duración de estancia, y con criterio configurable sobre si se recauda por adelantado o en destino.

---

## 9. Plan de fases

### Fase 1 · Núcleo PMS (meses 0 a 4)

**Entrega.** Un PMS completo y vendible, con cobro manual y sin conectividad automática con canales.

**Contenido.** Modelo de dominio e inventario por tipo; reservas con máquina de estados completa; Planning, Plano, Reservas y Housekeeping; tarifas, restricciones y promociones; folio con cargos y pagos registrados a mano; reportes básicos; multi-tenancy con RLS; auditoría inmutable; y gestión de usuarios y roles.

**Cómo se cobra en esta fase.** Efectivo, datáfono y transferencia se registran en el folio. Los enlaces de pago se generan fuera del sistema y se pegan a mano.

**Cómo entran las reservas.** Venta directa, teléfono y walk-in. Las reservas de OTA se cargan manualmente.

### Fase 2 · Pagos (meses 4 a 7)

**Entrega.** Cobro automatizado y conciliación.

**Contenido.** Pasarela con checkout alojado; tokenización de medios de pago; recepción de webhooks firmados e idempotentes; cobros diferidos por no-show, penalización y daños; enlaces de pago y depósitos de garantía; conciliación y exportación al ERP; y arquitectura de cuentas conectadas con split.

**Qué desbloquea.** Prepago, garantía real de la reserva, aplicación automática de la política de cancelación, y cierre de caja sin hojas de cálculo.

### Fase 3 · Distribución OTA (meses 7 a 12)

**Entrega.** Inventario sincronizado con los canales de venta.

**Contenido.** Integración del channel manager; asistente de mapeo entre tipos locales y códigos remotos; cola de publicación de disponibilidad y tarifas con debounce, coalescing y diff; recepción idempotente de reservas entrantes; guardia y gestión de sobreventa; check-in en línea para completar datos legales; y registro de comisión por reserva con cálculo de ADR neto.

**Qué desbloquea.** Airbnb, Booking, Expedia, Hostelworld y Despegar sin recarga manual ni riesgo sistemático de doble venta.

### Regla de corte entre fases

No se pasa a la siguiente fase hasta que la anterior tenga **al menos un alojamiento real operando en producción durante un mes completo**. Integrar canales sobre un inventario que todavía falla multiplica los errores en lugar de sumarlos.

---

## 10. Ganchos obligatorios en la fase 1

Son decisiones baratas de tomar ahora y muy caras de introducir después, porque obligan a migrar datos ya en producción. Deben construirse en la fase 1 aunque todavía no sirvan para nada.

| Gancho | Qué se construye | Lo habilita en |
|---|---|---|
| Fuente única de inventario | `inventory_day` con bloqueo pesimista y restricción de integridad | Fase 3 |
| Patrón outbox | Tabla de eventos escrita en la misma transacción que el cambio de negocio, con worker que la drena. Inicialmente solo alimenta el log de auditoría | Fases 2 y 3 |
| Referencia externa e idempotencia | Campos con índice único en reserva y en movimiento de folio, aunque todo se cree a mano | Fases 2 y 3 |
| Canal y comisión en la reserva | Campos de canal, importe de comisión e importe neto desde el día uno, con valor por defecto «directo» | Fase 3 |
| Folio con líneas tipadas | Cargos y pagos como líneas independientes con estado propio | Fase 2 |
| Modelo de pago por canal | Campo que distingue si cobra la plataforma o el alojamiento | Fase 3 |
| Bóveda de credenciales | Almacén cifrado de secretos por tenant y entorno, aunque solo guarde el SMTP | Fases 2 y 3 |
| Receptor genérico de webhooks | Endpoint que verifica firma, deduplica y encola, respondiendo 200 de inmediato | Fases 2 y 3 |
| Precios congelados | Cada noche almacena el importe con el que se vendió | Las tres |

De todos ellos, el **patrón outbox** merece mención especial: es la pieza que parece prescindible mientras no hay integraciones, y la que, si falta, obliga a reescribir la capa de acceso a datos cuando llegan.

---

## 11. Estrategia de pruebas

### 11.1 Por nivel

**Unitarias.** Concentradas en el motor de precios (suplementos, ocupantes adicionales, recargos, impuestos), el motor de promociones (ventanas, acumulabilidad, prioridad) y la máquina de estados de la reserva. Son reglas puras y densas: es donde las pruebas unitarias rinden más.

**De integración con base de datos.** Imprescindibles para verificar las restricciones de exclusión, los `CHECK` de inventario y, muy especialmente, las políticas de RLS. Debe existir una prueba que intente explícitamente leer datos de otro tenant y confirme que falla.

**De concurrencia.** No bastan las pruebas manuales. Hay que lanzar N peticiones simultáneas sobre la última unidad disponible y verificar que exactamente una tiene éxito. Esta prueba debe formar parte de la integración continua, no ejecutarse una sola vez.

**De contrato con proveedores.** Grabar y reproducir las respuestas de cada API externa, incluidos los caminos de error. El sandbox de Despegar, por ejemplo, permite provocar deliberadamente escenarios de timeout, datos vacíos y stop-sell según el mes consultado.

**De extremo a extremo.** Los recorridos críticos: reservar desde el plano, hacer check-in completo, cobrar, cambiar de habitación en el planning y cerrar caja.

### 11.2 Escenarios específicos del dominio que deben probarse

Cambio de horario de verano en el cálculo de noches. Reservas que cruzan fin de año. Estancias de una sola noche con CTA o CTD activos. Modificación de una reserva que reduce noches ya pagadas. Cancelación parcial de una reserva multi-habitación. Sobreventa provocada por una unidad puesta fuera de servicio después de vender. Webhook de pago que llega antes que la respuesta síncrona del checkout. Webhook duplicado con el mismo identificador. Reserva de canal que llega para un tipo que ya no existe en el mapeo. Y redondeo e impuestos en el desglose noche a noche, que debe sumar exactamente el total.

### 11.3 Datos de prueba

Mantener tres juegos de datos semilla, uno por vertical, con un hostel de camas, un apartamento y un hotel rural. Toda funcionalidad nueva debe validarse contra los tres antes de considerarse terminada: es el mecanismo que impide que el producto se convierta en tres productos distintos con un código común.

### 11.4 Pruebas con usuario real

Un alojamiento piloto desde el final de la fase 1, con acompañamiento presencial durante la primera semana de uso. El valor de observar a una recepcionista real usando el planning en hora punta es superior al de cualquier batería de pruebas automatizadas para detectar problemas de diseño.

---

## 12. Consideraciones para la implementación y la operación

### 12.1 Puesta en marcha de cada cliente

El proceso de alta determina en buena medida la retención. Debe cubrir la carga de la estructura de la propiedad, la importación de reservas existentes desde el sistema anterior (habitualmente hojas de cálculo o un PMS legado), la carga inicial de tarifas para al menos doce meses, la formación del equipo, y un periodo de doble registro durante el cual el cliente mantiene su sistema anterior en paralelo.

### 12.2 Observabilidad

Métricas de primer nivel desde el primer día: latencia del motor de disponibilidad, tasa de respuestas de límite de peticiones excedido por canal, antigüedad del evento más viejo pendiente en la cola de outbox, número de reservas en sobreventa activa, y tasa de error de webhooks por proveedor. Alertas sobre las dos últimas dirigidas a una persona concreta, no a un canal genérico.

### 12.3 Copias de seguridad y recuperación

Recuperación a punto en el tiempo sobre PostgreSQL, con prueba de restauración ejecutada periódicamente y documentada. Una copia de seguridad que nunca se ha restaurado no es una copia de seguridad.

### 12.4 Degradación controlada

Definir de antemano el comportamiento ante caída de cada dependencia. Si cae el channel manager, se encola y se avisa, y transcurrido un umbral se cierran ventas en los canales afectados antes que seguir vendiendo a ciegas. Si cae la pasarela, se permite registrar el cobro manualmente. Si cae el proveedor de IA, el Inbox funciona sin sugerencias. Ninguna de estas caídas puede impedir hacer un check-in.

### 12.5 Documentación

El manual de usuario ya redactado debe convertirse en ayuda contextual dentro del producto, con acceso desde la cabecera de cada pantalla al capítulo correspondiente. La documentación separada del producto se desactualiza y nadie la lee.

---

## 13. Riesgos de proyecto y mitigación

| Fase | Riesgo | Mitigación |
|---|---|---|
| 1 | Modelo de inventario mal planteado | Validar con los tres verticales antes de escribir la primera migración |
| 1 | Condiciones de carrera al vender | Bloqueo pesimista más restricción en base de datos, con prueba de carga concurrente automatizada |
| 1 | Sobredimensionar el alcance inicial | Lista cerrada de funcionalidades de fase 1, con cualquier adición sujeta a retirar otra |
| 2 | Alcance de cumplimiento de pagos más amplio del necesario | Checkout alojado o widget del proveedor, sin excepciones |
| 2 | Webhooks duplicados o falsificados | Verificación de firma obligatoria y deduplicación antes de aplicar |
| 2 | Pagos pendientes que no resuelven | Política explícita de retención de inventario y liberación automática al expirar |
| 3 | Mapeo incorrecto de tipos | Asistente obligatorio con vista previa y confirmación explícita del cliente |
| 3 | Cuota de peticiones agotada | Debounce, coalescing y diff desde el primer envío; monitorización como métrica principal |
| 3 | Datos legales incompletos en reservas de canal | Check-in en línea enviado automáticamente tras la confirmación |
| 3 | Canal en error vendiendo a ciegas | Cierre automático de ventas tras un umbral de tiempo en fallo |
| Transversal | Construir conectores propios antes de tener clientes | Channel manager white-label; integración directa solo con volumen que lo justifique |
| Transversal | Divergencia funcional entre verticales | Juegos de datos semilla de los tres verticales en la integración continua |

---

## 14. Decisiones pendientes antes de iniciar el desarrollo

Son las que condicionan la arquitectura y no pueden posponerse.

Primera, el **mercado objetivo inicial**, porque determina qué marco normativo y qué pasarelas se implementan primero. El cumplimiento español y el colombiano llevan a decisiones distintas.

Segunda, el **modelo de custodia de fondos**, con asesoría legal previa, porque afecta a la elección de proveedor y a la estructura societaria.

Tercera, el **stack concreto**, que debe decidirse por la experiencia real del equipo y no por preferencia teórica. Un equipo que domina Django entregará antes y mejor con Django que con Go.

Cuarta, el **channel manager**, que conviene seleccionar y probar en sandbox durante la fase 1 aunque no se integre hasta la fase 3, porque su modelo de datos influye en cómo se diseña la tabla de mapeo.

Quinta, el **alojamiento piloto**, idealmente comprometido antes de escribir la primera línea de código. Desarrollar sin un usuario real esperando es la vía más rápida a construir el producto equivocado.

---

## 15. Aviso

Los plazos indicados son orientativos y dependen del tamaño y la experiencia del equipo. Las condiciones de acceso de cada agencia en línea, las tarifas y las reglas de las pasarelas de pago, los precios de la mensajería y las obligaciones legales aplicables cambian con frecuencia y deben verificarse en la documentación oficial vigente antes de comprometer fechas o decisiones de arquitectura. Las referencias normativas de este documento no constituyen asesoramiento legal ni fiscal y deben contrastarse con un profesional cualificado.

---

*Documento elaborado como cierre de la fase de concepción. Acompaña al manual de usuario y al conjunto de maquetas de interfaz entregados previamente.*

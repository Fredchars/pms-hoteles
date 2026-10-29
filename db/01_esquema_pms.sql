-- PMS hotelero (piloto) · tablas propias con prefijo pms_ dentro del proyecto Supabase atlas-selleragent.
-- No modifica ninguna otra tabla (ATLAS, sim_*, agora_*). Idempotente: se puede aplicar varias veces.
-- Prototipo diseñado para ATm Consulting.

create table if not exists pms_hoteles (
  id bigserial primary key,
  nombre text not null,
  pais text not null,
  moneda char(3) not null,
  zona_horaria text not null default 'America/Bogota',
  activo boolean not null default true,
  creado timestamptz not null default now()
);

create table if not exists pms_impuestos (
  id bigserial primary key,
  hotel_id bigint not null references pms_hoteles(id),
  nombre text not null,
  porcentaje numeric(6,3) not null check (porcentaje >= 0 and porcentaje <= 100),
  activo boolean not null default true,
  creado timestamptz not null default now(),
  unique (hotel_id, nombre)
);

create table if not exists pms_usuarios (
  id bigserial primary key,
  hotel_id bigint references pms_hoteles(id),          -- null = acceso a todos los hoteles (administrador)
  email text not null unique,
  nombre text not null,
  rol text not null check (rol in ('recepcion','gerencia','housekeeping','administrador')),
  clave_hash text not null,
  activo boolean not null default true,
  creado timestamptz not null default now(),
  ultimo_acceso timestamptz,
  debe_cambiar_clave boolean not null default false     -- true = en el próximo ingreso debe crear su propia contraseña
);
-- Migración idempotente (bases creadas antes de esta columna): se puede ejecutar cuantas veces se quiera.
alter table pms_usuarios add column if not exists debe_cambiar_clave boolean not null default false;

create table if not exists pms_tipos_habitacion (
  id bigserial primary key,
  hotel_id bigint not null references pms_hoteles(id),
  nombre text not null,
  capacidad int not null check (capacidad > 0),
  descripcion text,
  activo boolean not null default true,
  unique (hotel_id, nombre)
);

create table if not exists pms_habitaciones (
  id bigserial primary key,
  hotel_id bigint not null references pms_hoteles(id),
  numero text not null,
  planta int not null default 1,
  tipo_id bigint not null references pms_tipos_habitacion(id),
  metros int,
  vista text,
  estado_limpieza text not null default 'lista'
    check (estado_limpieza in ('sucia','en_limpieza','inspeccion','lista','fuera_de_servicio')),
  activo boolean not null default true,
  unique (hotel_id, numero)
);

-- Plano de habitaciones: atributo «vista al mar» (migración idempotente; solo la primera vez rellena según el texto de «vista»)
do $$
begin
  if not exists (select 1 from information_schema.columns where table_schema = current_schema()
                 and table_name = 'pms_habitaciones' and column_name = 'vista_mar') then
    alter table pms_habitaciones add column vista_mar boolean not null default false;
    update pms_habitaciones set vista_mar = true where vista ~* '(^|[^[:alpha:]])mar([^[:alpha:]]|$)';
  end if;
end $$;

create table if not exists pms_camas (
  id bigserial primary key,
  hotel_id bigint not null references pms_hoteles(id),
  habitacion_id bigint not null references pms_habitaciones(id),
  tipo text not null check (tipo in ('matrimonial','individual','litera','sofa_cama','cuna')),
  ancho_cm int,
  cantidad int not null default 1 check (cantidad > 0)
);

create table if not exists pms_tarifas (
  id bigserial primary key,
  hotel_id bigint not null references pms_hoteles(id),
  tipo_id bigint not null references pms_tipos_habitacion(id),
  temporada text not null,
  fecha_desde date not null,
  fecha_hasta date not null,                            -- inclusive
  precio_noche numeric(14,2) not null check (precio_noche >= 0),
  estancia_minima int not null default 1 check (estancia_minima >= 1),
  cierre_ventas boolean not null default false,
  activo boolean not null default true,
  creado timestamptz not null default now(),
  check (fecha_hasta >= fecha_desde)
);

create table if not exists pms_huespedes (
  id bigserial primary key,
  hotel_id bigint not null references pms_hoteles(id),
  nombres text not null,
  apellidos text not null,
  tipo_documento text,
  numero_documento text,
  email text,
  telefono text,
  pais text,
  anonimizado boolean not null default false,
  creado timestamptz not null default now()
);

create table if not exists pms_consentimientos (
  id bigserial primary key,
  hotel_id bigint not null references pms_hoteles(id),
  huesped_id bigint not null references pms_huespedes(id),
  finalidad text not null check (finalidad in ('prestacion_servicio','facturacion','marketing')),
  aceptado boolean not null,
  texto text not null,
  version text not null,
  fecha timestamptz not null default now(),
  revocado_en timestamptz,
  registrado_por bigint references pms_usuarios(id)
);

create table if not exists pms_reservas (
  id bigserial primary key,
  hotel_id bigint not null references pms_hoteles(id),
  codigo text not null,
  huesped_id bigint not null references pms_huespedes(id),
  tipo_id bigint not null references pms_tipos_habitacion(id),
  fecha_entrada date not null,
  fecha_salida date not null,                           -- noche de salida NO incluida
  adultos int not null default 1 check (adultos >= 1),
  ninos int not null default 0 check (ninos >= 0),
  estado text not null default 'confirmada'
    check (estado in ('consulta','opcion','confirmada','alojado','salida','cancelada','no_show')),
  canal text not null default 'directo',
  comision_pct numeric(6,3) not null default 0 check (comision_pct >= 0 and comision_pct <= 100),
  comision_monto numeric(14,2) not null default 0,
  neto numeric(14,2) not null default 0,
  referencia_externa text,
  notas text,
  cancelacion_estado text check (cancelacion_estado in ('solicitada','aprobada','rechazada')),
  cancelacion_motivo text,
  cancelacion_solicitada_por bigint references pms_usuarios(id),
  cancelacion_resuelta_por bigint references pms_usuarios(id),
  cancelacion_resuelta_en timestamptz,
  creado_por bigint references pms_usuarios(id),
  creado timestamptz not null default now(),
  unique (hotel_id, codigo),
  check (fecha_salida > fecha_entrada)
);
create unique index if not exists ux_pms_reservas_ref_externa
  on pms_reservas (hotel_id, canal, referencia_externa) where referencia_externa is not null;
create index if not exists ix_pms_reservas_fechas on pms_reservas (hotel_id, fecha_entrada, fecha_salida);

create table if not exists pms_reserva_noches (
  id bigserial primary key,
  hotel_id bigint not null references pms_hoteles(id),
  reserva_id bigint not null references pms_reservas(id),
  noche date not null,
  tipo_id bigint not null references pms_tipos_habitacion(id),
  habitacion_id bigint not null references pms_habitaciones(id),
  precio numeric(14,2) not null check (precio >= 0),    -- precio congelado al vender; nunca se recalcula
  activa boolean not null default true,                 -- false = noche liberada (cancelación, cambio de fechas, no-show)
  creado timestamptz not null default now()
);
-- REGLA CLAVE: una habitación no puede tener dos noches activas iguales (no hay doble venta, ni con concurrencia).
create unique index if not exists ux_pms_noche_habitacion
  on pms_reserva_noches (habitacion_id, noche) where activa;
create unique index if not exists ux_pms_noche_reserva
  on pms_reserva_noches (reserva_id, noche) where activa;
create index if not exists ix_pms_noches_hotel on pms_reserva_noches (hotel_id, noche);

create table if not exists pms_estancias (
  id bigserial primary key,
  hotel_id bigint not null references pms_hoteles(id),
  reserva_id bigint not null unique references pms_reservas(id),
  habitacion_id bigint not null references pms_habitaciones(id),
  checkin_real timestamptz not null default now(),
  checkout_real timestamptz,
  usuario_checkin bigint references pms_usuarios(id),
  usuario_checkout bigint references pms_usuarios(id)
);

create table if not exists pms_housekeeping (
  id bigserial primary key,
  hotel_id bigint not null references pms_hoteles(id),
  habitacion_id bigint not null references pms_habitaciones(id),
  estado_anterior text,
  estado_nuevo text not null,
  usuario_id bigint references pms_usuarios(id),
  nota text,
  creado timestamptz not null default now()
);
create index if not exists ix_pms_hk_hab on pms_housekeeping (habitacion_id, creado);

create table if not exists pms_bloqueos (
  id bigserial primary key,
  hotel_id bigint not null references pms_hoteles(id),
  habitacion_id bigint not null references pms_habitaciones(id),
  fecha_desde date not null,
  fecha_hasta date not null,                            -- inclusive
  motivo text not null,
  activo boolean not null default true,
  creado_por bigint references pms_usuarios(id),
  creado timestamptz not null default now(),
  liberado_por bigint references pms_usuarios(id),
  liberado_en timestamptz,
  check (fecha_hasta >= fecha_desde)
);

create table if not exists pms_cargos (
  id bigserial primary key,
  hotel_id bigint not null references pms_hoteles(id),
  reserva_id bigint not null references pms_reservas(id),
  tipo text not null check (tipo in ('noche','extra','descuento')),
  descripcion text not null,
  cantidad numeric(10,2) not null default 1,
  precio_unitario numeric(14,2) not null,
  monto numeric(14,2) not null,                          -- cantidad x precio (negativo en descuentos)
  impuestos jsonb not null default '[]'::jsonb,          -- impuestos congelados al crear: [{"nombre","porcentaje"}]
  noche date,
  estado text not null default 'aprobado' check (estado in ('aprobado','pendiente','rechazado')),
  solicitado_por bigint references pms_usuarios(id),
  aprobado_por bigint references pms_usuarios(id),
  resuelto_en timestamptz,
  motivo text,
  anulado boolean not null default false,
  anulado_por bigint references pms_usuarios(id),
  creado timestamptz not null default now()
);
create index if not exists ix_pms_cargos_reserva on pms_cargos (reserva_id);

create table if not exists pms_pagos (
  id bigserial primary key,
  hotel_id bigint not null references pms_hoteles(id),
  reserva_id bigint not null references pms_reservas(id),
  metodo text not null check (metodo in ('efectivo','datafono','transferencia','otro')),
  monto numeric(14,2) not null check (monto > 0),
  referencia text,
  anulado boolean not null default false,
  anulado_por bigint references pms_usuarios(id),
  creado_por bigint references pms_usuarios(id),
  creado timestamptz not null default now()
);
create index if not exists ix_pms_pagos_reserva on pms_pagos (reserva_id);

create table if not exists pms_auditoria (
  id bigserial primary key,
  hotel_id bigint,
  usuario_id bigint,
  usuario_email text,
  accion text not null,
  entidad text not null,
  entidad_id text,
  antes jsonb,
  despues jsonb,
  creado timestamptz not null default now()
);
create index if not exists ix_pms_aud_hotel on pms_auditoria (hotel_id, creado desc);

-- La auditoría solo se agrega: nadie puede editarla ni borrarla.
create or replace function pms_auditoria_inmutable() returns trigger language plpgsql as $f$
begin
  raise exception 'pms_auditoria es de solo agregar: no se puede editar ni borrar';
end $f$;
drop trigger if exists pms_auditoria_no_update on pms_auditoria;
create trigger pms_auditoria_no_update before update or delete on pms_auditoria
  for each row execute function pms_auditoria_inmutable();

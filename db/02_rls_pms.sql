-- RLS activado SIN políticas + revocación a los roles de la API pública (anon/authenticated):
-- la API REST de Supabase no ve nada; solo el servidor de la app (conexión directa DATABASE_URL) accede.
do $rls$
declare t text;
begin
  for t in select tablename from pg_tables where schemaname = 'public' and tablename like 'pms\_%' loop
    execute format('alter table public.%I enable row level security', t);
    if exists (select 1 from pg_roles where rolname = 'anon') then
      execute format('revoke all on table public.%I from anon, authenticated', t);
    end if;
  end loop;
  if exists (select 1 from pg_roles where rolname = 'anon') then
    for t in select sequencename from pg_sequences where schemaname = 'public' and sequencename like 'pms\_%' loop
      execute format('revoke all on sequence public.%I from anon, authenticated', t);
    end loop;
  end if;
end $rls$;

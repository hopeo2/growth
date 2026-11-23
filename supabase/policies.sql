-- ============================================================================
-- Growly — Supabase setup
-- ============================================================================
-- Run this once in the Supabase SQL editor *after* the Drizzle schema has been
-- pushed (`npm run db:push` or `npm run db:migrate`). It wires the application
-- tables to Supabase Auth and locks them down with Row Level Security.
--
-- The web app talks to Postgres directly through `DATABASE_URL` (the pooler
-- connection owned by the `postgres` role), so it is not subject to RLS. RLS
-- here protects against anyone using the public anon key directly.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Link public.profiles to auth.users
-- ----------------------------------------------------------------------------

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'profiles_id_fkey'
  ) then
    alter table public.profiles
      add constraint profiles_id_fkey
      foreign key (id) references auth.users (id) on delete cascade;
  end if;
end
$$;

-- ----------------------------------------------------------------------------
-- 2. Auto-create a profile row whenever a user signs up
-- ----------------------------------------------------------------------------

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, display_name)
  values (
    new.id,
    lower(coalesce(new.email, '')),
    nullif(new.raw_user_meta_data ->> 'display_name', '')
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ----------------------------------------------------------------------------
-- 3. Admin helper
-- ----------------------------------------------------------------------------

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.profiles
    where id = auth.uid()
      and role = 'admin'
      and status = 'active'
  );
$$;

-- ----------------------------------------------------------------------------
-- 4. Row Level Security
-- ----------------------------------------------------------------------------

alter table public.profiles enable row level security;
alter table public.instagram_accounts enable row level security;
alter table public.growth_settings enable row level security;
alter table public.targets enable row level security;
alter table public.jobs enable row level security;
alter table public.activity_logs enable row level security;
alter table public.account_stats_daily enable row level security;
alter table public.service_settings enable row level security;
alter table public.workers enable row level security;

-- users can read/update their own profile; admins can read/update all
drop policy if exists profiles_select_own on public.profiles;
create policy profiles_select_own on public.profiles
  for select using (id = auth.uid() or public.is_admin());

drop policy if exists profiles_insert_self on public.profiles;
create policy profiles_insert_self on public.profiles
  for insert with check (id = auth.uid() or public.is_admin());

drop policy if exists profiles_update_own on public.profiles;
create policy profiles_update_own on public.profiles
  for update using (id = auth.uid() or public.is_admin())
  with check (id = auth.uid() or public.is_admin());

-- accounts and everything that hangs off them: owner or admin
do $$
declare
  t text;
begin
  foreach t in array array[
    'instagram_accounts', 'jobs', 'activity_logs', 'account_stats_daily'
  ] loop
    execute format('drop policy if exists %I_owner on public.%I', t, t);
    execute format(
      'create policy %I_owner on public.%I for all using (user_id = auth.uid() or public.is_admin()) with check (user_id = auth.uid() or public.is_admin())',
      t, t
    );
  end loop;
end
$$;

-- settings and targets are reached through their account
do $$
declare
  t text;
begin
  foreach t in array array['growth_settings', 'targets'] loop
    execute format('drop policy if exists %I_owner on public.%I', t, t);
    execute format(
      $f$create policy %I_owner on public.%I for all
        using (
          public.is_admin()
          or exists (
            select 1 from public.instagram_accounts a
            where a.id = %I.account_id and a.user_id = auth.uid()
          )
        )
        with check (
          public.is_admin()
          or exists (
            select 1 from public.instagram_accounts a
            where a.id = %I.account_id and a.user_id = auth.uid()
          )
        )$f$,
      t, t, t, t
    );
  end loop;
end
$$;

-- service settings: readable by anyone signed in, writable by admins
drop policy if exists service_settings_select on public.service_settings;
create policy service_settings_select on public.service_settings
  for select using (auth.role() = 'authenticated' or public.is_admin());

drop policy if exists service_settings_admin on public.service_settings;
create policy service_settings_admin on public.service_settings
  for all using (public.is_admin()) with check (public.is_admin());

-- workers: admins only
drop policy if exists workers_admin on public.workers;
create policy workers_admin on public.workers
  for all using (public.is_admin()) with check (public.is_admin());

-- ----------------------------------------------------------------------------
-- 5. Seed the singleton service settings row
-- ----------------------------------------------------------------------------

insert into public.service_settings (id)
values ('global')
on conflict (id) do nothing;

# Supabase setup

This folder holds the SQL that is **not** part of the Drizzle schema: the link
to Supabase Auth, the signup trigger, Row Level Security, and seed rows.

## Order of operations

1. **Create the schema** (from the repo root). Drizzle owns every table:

   ```bash
   npm run db:push        # quick path
   # or, for versioned migrations:
   npm run db:generate && npm run db:migrate
   ```

   This creates `profiles`, `instagram_accounts`, `growth_settings`, `targets`,
   `jobs`, `activity_logs`, `account_stats_daily`, `service_settings`, and
   `workers`, plus their enums.

2. **Wipe and recreate (optional).** If Drizzle complains about a dirty type:

   ```bash
   npx drizzle-kit drop
   ```

3. **Apply `policies.sql`** in the Supabase dashboard → SQL Editor. It is
   idempotent; re-run it whenever you change the tables it references.

## What `policies.sql` does

- **`profiles.id` → `auth.users.id`** — foreign key with `on delete cascade`, so
  deleting a Supabase user removes their app data.
- **`on_auth_user_created` trigger** — mirrors new `auth.users` rows into
  `public.profiles` with a lowercased email. The app also self-heals profiles in
  `ensureProfile`, so accounts created before the trigger still work.
- **`public.is_admin()`** — `security definer` helper used by the policies.
- **Row Level Security** on every table:
  - a user can read/update their own profile (admins: any);
  - accounts and everything hanging off them (`jobs`, `activity_logs`,
    `account_stats_daily`) are visible to the owner or an admin;
  - `growth_settings` and `targets` are reached through their account;
  - `service_settings` is world-readable when signed in, admin-writable;
  - `workers` is admin-only.
- **Seed** — inserts the singleton `service_settings` row (`id = 'global'`).

## Why RLS matters here

The web app connects with `DATABASE_URL` as the `postgres` role, which is
**not** subject to RLS — the app enforces ownership in `src/server/*.server.ts`.
RLS is the safety net for the public `anon` key: without it, anyone holding the
anon key (it ships in the browser bundle) could read other users' tables through
Supabase's auto-generated REST API. Enable RLS and never expose the
`service_role` key to the browser.

## Connection strings

| Purpose | Role | Port |
| --- | --- | --- |
| App runtime | connection pooler | `6543` |
| `drizzle-kit` (DDL) | direct or session pooler | `5432` / `5432` |

If migrations hang or fail through the transaction pooler, switch
`DATABASE_URL` to the direct connection just for `db:push`/`db:migrate`.

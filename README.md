# Growly

A self-hosted Instagram growth platform. Users connect an Instagram account,
pick growth settings and targets, and a Python worker runs
[InstaPy](https://github.com/InstaPy/InstaPy) on their behalf and streams the
activity back to a dashboard.

Three parts:

| Part | What it is |
| --- | --- |
| **User panel** | Sign up, connect an account, tune growth settings, manage targets, watch analytics and activity logs. |
| **Admin panel** | Manage users, accounts, jobs, and global service settings. |
| **Automation worker** | A Python process that claims jobs and drives InstaPy (`worker/`). |

## Stack

- **Web**: [TanStack Start](https://tanstack.com/start) (React 19, Vite, Tailwind v4, TypeScript)
- **Data + Auth**: [Supabase](https://supabase.com) (Postgres + GoTrue), accessed with [Drizzle ORM](https://orm.drizzle.team)
- **Queue**: the Postgres `jobs` table using `SELECT … FOR UPDATE SKIP LOCKED` — no Redis, no cron
- **Worker**: Python + [InstaPy](https://github.com/InstaPy/InstaPy) in headless Firefox

Deploy target: **Supabase free tier + any Docker host** (an Iranian cloud such
as Liara, a cheap VPS, or a global PaaS). See [`DEPLOYMENT.md`](./DEPLOYMENT.md).

## How it fits together

```
browser ─► TanStack Start server fns ─► Postgres (Supabase)
                    │                        ▲
                    │ enqueue job            │ claim / progress / events
                    ▼                        │
              jobs table ──────────────────► worker (python -m worker)
                                             └─► InstaPy ─► Instagram
```

The browser never holds Instagram credentials in a usable form. Passwords are
encrypted with AES-256-GCM (`src/lib/crypto.server.ts`) and decrypted only inside
the worker (`worker/crypto.py`), which shares the wire format
`v1.<iv>.<ciphertext>.<tag>` (unpadded base64url).

## Repository layout

```
src/
  db/            Drizzle schema, types, lazy connection
  lib/           env, crypto, Supabase clients, auth helpers, middleware
  server/        server-only services (accounts, settings, targets, jobs, …)
  functions/     createServerFn RPC wrappers used by routes
  routes/        file-based routes (user panel, admin panel, worker API)
  components/    UI primitives, charts, app shell
worker/          Python InstaPy worker (see worker/README.md)
supabase/        Auth linkage, trigger, RLS, seed (see supabase/README.md)
deploy/          systemd units, Caddyfile, VPS bootstrap script
instapy-00/      vendored InstaPy checkout
Dockerfile       web app image        Dockerfile.worker  worker image
docker-compose.yml  web + worker      netlify.toml       Netlify web app
render.yaml      Render alternative   .githooks/         secret-scan pre-commit
```

## Quickstart (local)

Prerequisites: Node 22+, Python 3.11+, Firefox + geckodriver, a Supabase project.

```bash
# 1. Web app
cp .env.example .env          # fill in Supabase keys + secrets
npm install
npm run db:push               # create tables in Supabase
# then run supabase/policies.sql in the Supabase SQL editor
npm run dev                   # http://localhost:3000

# 2. Worker (second terminal)
python3 -m venv .venv && source .venv/bin/activate
pip install -r instapy-00/requirements.txt
pip install -r worker/requirements.txt
python -m worker
```

Sign up, then add an account under **Accounts**. Emails listed in `ADMIN_EMAILS`
are promoted to admin on first login.

## Deploy

**Web app on Netlify** (free, no credit card, no domain needed) — the repo has a
`netlify.toml`:

1. Push the repo to GitHub, then Netlify → **Add new site → Import an existing
   project** → pick the repo.
2. Add the env vars listed at the top of `netlify.toml` (Supabase keys +
   secrets). Set `DATABASE_POOL_MAX=1`.
3. Deploy, then set `APP_ORIGIN` to the `https://<site>.netlify.app` URL and
   redeploy.

**Worker** needs Firefox and a long-running process, so it goes on a VPS:

```bash
cp .env.example .env
# set WORKER_API_URL to the Netlify URL, plus the two shared secrets
docker compose up -d worker
```

Or run the whole stack on one Docker host instead:

```bash
cp .env.example .env
docker compose up -d --build   # web on :3000 + worker
```

Full walkthrough (including the Iran/Instagram proxy requirement) is in
[`DEPLOYMENT.md`](./DEPLOYMENT.md).

## Scripts

| Command | Purpose |
| --- | --- |
| `npm run dev` | Dev server on :3000 |
| `npm run build` | Production build into `.output/` |
| `npm start` | Run the built server |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run check` | Biome lint + format check |
| `npm run db:push` | Push the Drizzle schema |
| `npm run db:generate` / `db:migrate` | Versioned migrations |

## Environment

All variables are documented in [`.env.example`](./.env.example). The essentials:

| Variable | Used by | Notes |
| --- | --- | --- |
| `DATABASE_URL` | web | Supabase pooler connection string |
| `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` | browser | bundled at build time |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` | web | server fallback to the `VITE_*` values |
| `SUPABASE_SERVICE_ROLE_KEY` | web | server-only, never ship to the browser |
| `CREDENTIALS_ENCRYPTION_KEY` | web + worker | base64 of 32 random bytes |
| `WORKER_API_TOKEN` | web + worker | bearer token for `/api/worker/*` |
| `APP_ORIGIN` | web + worker | public origin / worker API base |
| `ADMIN_EMAILS` | web | comma-separated bootstrap admins |

## Documentation

- [`DEPLOYMENT.md`](./DEPLOYMENT.md) — Supabase + Oracle Cloud walkthrough
- [`worker/README.md`](./worker/README.md) — the automation worker
- [`supabase/README.md`](./supabase/README.md) — schema, trigger, RLS

## License

InstaPy is GPL-3.0; the vendored checkout in `instapy-00/` keeps its license.
Automating Instagram can violate Instagram's Terms of Service — use at your own
risk and respect rate limits.

# Deploying Growly

Growly runs on free/cheap infrastructure and is **host-agnostic**: the same two
containers work on a plain VPS, an Iranian cloud, or a global PaaS.

| Piece | Runs where | Cost |
| --- | --- | --- |
| Database + Auth | **Supabase** (free project) | $0 |
| Web app | any VPS / PaaS that runs Docker | $0–cheap |
| Automation worker | a host with ≥1 GB RAM that can reach Instagram (via proxy) | $0–cheap |

The web app is a Node server; the worker runs InstaPy in headless Firefox. They
talk over the internal HTTP API (`/api/worker/*`) and share Supabase Postgres.

> **Two hard constraints when you're in Iran**
>
> 1. **Instagram is blocked in Iran**, and Instagram blocks many Iranian
>    datacenter IPs. The worker must reach Instagram through an **HTTP(S)
>    proxy**. You can set one per account (Accounts → proxy) or globally with
>    `WORKER_DEFAULT_PROXY`. InstaPy only speaks HTTP(S) proxies — not SOCKS —
>    so use an HTTP proxy, or run a tiny local `gost`/`3proxy` that converts
>    SOCKS→HTTP.
> 2. **Most US clouds (Oracle, AWS, GCP, Azure) won't accept Iranian accounts
>    or cards.** The options below are picked to avoid that.

---

## 1. Pick a host (options that work from Iran)

You don't need Oracle. Anything that runs Docker will do:

| Option | Type | Notes |
| --- | --- | --- |
| **Liara** — <https://liara.ir> | Iranian PaaS | Accepts Iranian cards, Docker deploys, Iranian support. Good for the web app; check that your plan allows a *persistent* worker. |
| **ArvanCloud** — <https://arvancloud.ir> | Iranian cloud | IaaS/PaaS; can run both containers. |
| **Parspack / Iranserver / MihanWebHost** | Iranian VPS | Paid (rial), not free, but cheap and reliably reachable from Iran. Good home for the worker. |
| **Koyeb** — <https://koyeb.com> | Global PaaS (FR) | Free instance, no credit card. Fine for the web app; usually too small for Firefox. |
| **Render** — <https://render.com> | Global PaaS (US) | Free web service, no card. Web app only (free tier sleeps, no background workers). |
| **Hugging Face Spaces** | Free Docker, 16 GB RAM | Can host the *worker* (Docker Space), but free Spaces sleep when idle. |

**Recommended split (what this guide uses):** the **web app on Render** (free,
no card, no domain needed) and the **worker on a VPS** — a European VPS reaches
Instagram directly; an Iranian one needs `WORKER_DEFAULT_PROXY`.

Either way you need the free **Supabase** project from section 2 below.

---

## 2. Supabase

1. Create a project at <https://supabase.com> (free plan).
2. **Settings → Database** → copy the connection string. Use the
   **connection pooler** (`...pooler.supabase.com:6543`) for the app, and the
   direct connection (`:5432`) for `drizzle-kit` if the pooler rejects DDL.
3. **Settings → API** → copy the project URL, the `anon` key, and the
   `service_role` key.
4. Apply the schema from your machine:

   ```bash
   cp .env.example .env          # fill in DATABASE_URL + the SUPABASE_* keys
   npm install
   npm run db:push               # or: npm run db:generate && npm run db:migrate
   ```

5. Run `supabase/policies.sql` in the Supabase **SQL Editor**. It links
   `public.profiles` to `auth.users`, installs the signup trigger, enables RLS,
   and seeds the settings row. Safe to re-run.

---

## 3. Deploy the web app on Render (no domain needed)

Render gives you a free `https://<name>.onrender.com` URL, so you can start
without owning a domain. The repo includes a `render.yaml` Blueprint.

1. Push the repo to GitHub.
2. Render dashboard → **New → Blueprint** → connect the repo. Render reads
   `render.yaml` and creates the `growly` web service.
3. Render prompts for every value marked `sync: false`. Paste the Supabase keys,
   `CREDENTIALS_ENCRYPTION_KEY`, `WORKER_API_TOKEN`, and `ADMIN_EMAILS`. You can
   leave `APP_ORIGIN` blank for this first deploy.
4. Deploy. When it finishes, copy the service URL from the top of the page,
   e.g. `https://growly.onrender.com`.
5. **Environment** tab → set `APP_ORIGIN` to that URL → save (it redeploys).
   This enables the CSRF origin check.

Notes:

- The blueprint sets `NITRO_PRESET=render-com` and `HOST=0.0.0.0`, and pins Node
  to 22 via `.node-version`.
- `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` must exist **at build time** —
  Render passes env vars to the build, so just set them and redeploy after any
  change (they are baked into the browser bundle).
- The **worker does not run on Render** (the free tier has no background
  workers and no Firefox). Host it on a VPS and point its `WORKER_API_URL` at
  this URL — see the next section.
- A free web service sleeps after ~15 min idle. The worker's ~20 s polling keeps
  it warm (good for responsiveness), but keep an eye on your free
  instance-hours.
- Choose a Render region near your Supabase region (the blueprint uses
  `frankfurt`) so DB round-trips stay short.

## 4. Deploy the worker (and optionally the web app) on a VPS

The worker needs Firefox and a long-running process, so it lives on a VPS. If
the web app is on Render, you only need the **worker** container here;
otherwise the compose file runs both.

### Prepare the box

On a small (2 GB) VPS, run the bootstrap script — it installs Docker + Compose,
adds 2 GB of swap (Firefox is memory-hungry), and locks the firewall down:

```bash
git clone <your-repo> growth && cd growth
sudo bash deploy/bootstrap-vps.sh
```

### Configure

```bash
cp .env.example .env
```

Edit `.env` and set at least:

```dotenv
DATABASE_URL="postgresql://...pooler.supabase.com:6543/postgres"
VITE_SUPABASE_URL="https://<ref>.supabase.co"
VITE_SUPABASE_ANON_KEY="<anon-key>"
SUPABASE_URL="https://<ref>.supabase.co"
SUPABASE_ANON_KEY="<anon-key>"
SUPABASE_SERVICE_ROLE_KEY="<service-role-key>"
CREDENTIALS_ENCRYPTION_KEY="<openssl rand -base64 32>"
WORKER_API_TOKEN="<openssl rand -hex 32>"
APP_ORIGIN="https://your-domain"
ADMIN_EMAILS="you@example.com"
# Required in Iran so the worker can reach Instagram:
WORKER_DEFAULT_PROXY="http://user:pass@proxy-host:8080"
```

Then:

```bash
docker compose up -d --build
docker compose logs -f          # watch web + worker
```

The web app listens on `:3000`. The worker reaches it at `http://web:3000`
internally (already set in `docker-compose.yml`). Refresh the app after editing
`VITE_*` values, since they are baked in at build time:

```bash
docker compose build web && docker compose up -d web
```

### Web app on Render? Run the worker only

If the web app lives on Render, point the worker at it and start just that
container:

```bash
# In .env:
#   WORKER_API_URL="https://growly.onrender.com"
#   WORKER_API_TOKEN="<same value as Render>"
#   CREDENTIALS_ENCRYPTION_KEY="<same value as Render>"

docker compose up -d worker
docker compose logs -f worker
```

Only `WORKER_API_TOKEN` and `CREDENTIALS_ENCRYPTION_KEY` must match the web app;
the worker doesn't need the Supabase keys or `DATABASE_URL`.

### Concurrency / resources

The worker runs one headless Firefox per job. Keep one worker container
(`WORKER_CONCURRENCY=1`). Give it at least **1 GB RAM** (2 GB is comfortable);
if the host is tight, add swap.

On a **2 GB box** (common on free tiers) web + worker together is tight but
workable with swap: Node uses ~150 MB, Firefox + InstaPy can spike to ~1 GB.
If jobs get OOM-killed, either raise swap to 2 GB (the bootstrap script does
this) or run **only the worker** on the small host and host the web app
elsewhere — the worker reaches the app over `WORKER_API_URL`, so they don't
have to share a machine.

### If GitHub is blocked at build time

`Dockerfile.worker` downloads geckodriver from GitHub releases. Point the build
at a mirror:

```bash
docker build -f Dockerfile.worker \
  --build-arg GECKODRIVER_URL=https://your-mirror.example.com/geckodriver \
  -t growly-worker .
```

---

## 5. Deploy without Docker (systemd on a VPS)

If you have a plain Iranian VPS (Parspack, Iranserver, …), use the systemd
units instead of Docker.

### Web app

```bash
sudo apt-get update
sudo apt-get install -y git curl build-essential
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
sudo useradd --create-home --shell /bin/bash growly

sudo -iu growly
git clone <your-repo> /opt/growly && cd /opt/growly
cp .env.example .env        # fill it in, then: chmod 600 .env
npm ci && npm run build

sudo cp deploy/growly-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now growly-web
curl -fsS http://127.0.0.1:3000/ >/dev/null && echo "web up"
```

### Worker

```bash
sudo apt-get install -y python3-venv firefox-esr xvfb unzip
sudo ln -sf /usr/bin/firefox-esr /usr/local/bin/firefox

# geckodriver (skip if your distro ships one, e.g. Ubuntu's firefox-geckodriver)
curl -fsSL https://github.com/mozilla/geckodriver/releases/download/v0.35.0/geckodriver-v0.35.0-linux64.tar.gz \
  | sudo tar -xz -C /usr/local/bin

sudo -iu growly
cd /opt/growly
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r instapy-00/requirements.txt -r worker/requirements.txt
python -m worker            # smoke test; Ctrl-C to stop

sudo cp deploy/growly-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now growly-worker
journalctl -u growly-worker -f
```

---

## 6. TLS

A domain terminates TLS in front of `:3000`.

- **Iranian PaaS / VPS**: Liara, ArvanCloud, and most VPS panels give you a free
  managed certificate — just point the domain at the app/port.
- **Your own box**: use the provided Caddy config:

  ```bash
  sudo apt-get install -y caddy
  sudo cp deploy/Caddyfile /etc/caddy/Caddyfile   # replace example.com
  sudo systemctl reload caddy
  ```

  Caddy also can restrict `/api/worker/*` to localhost so the worker API is
  never exposed publicly.

---

## 7. First run

1. Visit `https://your-domain/signup` and create an account. Emails in
   `ADMIN_EMAILS` become admin on first login.
2. **Accounts → Add account**: Instagram username/password, plus a proxy if this
   account needs one. Credentials are encrypted with
   `CREDENTIALS_ENCRYPTION_KEY` before they touch the database.
3. **Growth settings**: enable activities, daily caps, comments, delays,
   working hours/timezone.
4. **Targets**: hashtags / usernames / locations.
5. The worker picks the job up on its next poll and reports to
   **Dashboard → Activity logs** and **Analytics**.

---

## 8. Updating

```bash
cd growth && git pull
docker compose up -d --build
```

Without Docker: `npm ci && npm run build`, reinstall worker deps if
`requirements` changed, then `sudo systemctl restart growly-web growly-worker`.

---

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Worker logs `401` | `WORKER_API_TOKEN` differs between web and worker (same `.env`). |
| Worker logs `Missing required environment variable` | `.env` not found / not passed to the container (`env_file: .env`). |
| `InstaPy could not be imported` | Install `instapy-00/requirements.txt` in the worker environment. |
| Login fails / timeouts to Instagram | Add a proxy (`WORKER_DEFAULT_PROXY` or per account). Instagram blocks Iranian IPs. |
| `InstaPy only supports HTTP(S) proxies` | Convert SOCKS to HTTP with `gost`/`3proxy`, or use an HTTP proxy. |
| Firefox won't start in the container | Ensure `WORKER_HEADLESS=true`; if not, Xvfb must be running on `DISPLAY`. |
| `CREDENTIALS_ENCRYPTION_KEY must be 32 bytes` | Use base64 of 32 random bytes (`openssl rand -base64 32`). |
| No jobs run | Only during the account's working hours/day, when `enabled` is on and a target exists. |

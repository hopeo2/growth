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
| **Netlify** — <https://netlify.com> | Global PaaS (US) | Free plan, no card. Runs the web app as serverless functions + CDN. Worker can't run here. |
| **Altare** — <https://altare.gg> | Global PaaS | Free sandboxes (root SSH, Debian/Ubuntu, EU regions). **No Docker and no systemd**, so the worker is installed natively — see §4b. |
| **Render** — <https://render.com> | Global PaaS (US) | New accounts now require a card. Web app only (free tier sleeps, no background workers). |
| **Hugging Face Spaces** | Free Docker, 16 GB RAM | Can host the *worker* (Docker Space), but free Spaces sleep when idle. |

**Recommended split (what this guide uses):** the **web app on Netlify** (free,
no card, no domain needed) and the **worker on a VPS** — a European VPS reaches
Instagram directly; an Iranian one needs `WORKER_DEFAULT_PROXY`.

Either way you need the free **Supabase** project from section 2 below.

---

## 2. Supabase

1. Create a project at <https://supabase.com> (free plan).
2. **Connect → Direct** (or **Settings → Database**) → copy the connection
   string. Use the **transaction pooler** (`...pooler.supabase.com:6543`) for
   the app at runtime, and the **session pooler** (`:5432`) for `drizzle-kit`.
   New projects expose the "Direct" connection over IPv6 only, so the session
   pooler (IPv4) is the safe choice for migrations.
3. **Connect → Framework → React/Vite** → copy the project URL and the
   **publishable** key (this replaced the old `anon` key). The **secret** key
   (old `service_role`) is under **Settings → API Keys**.
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

## 3. Deploy the web app on Netlify (no card, no domain needed)

Netlify's free plan gives you `https://<site>.netlify.app` with HTTPS and does
not require a credit card. The repo includes `netlify.toml`; Nitro writes the
server function to `.netlify/v1/functions` and static assets to `dist`.

1. Push the repo to GitHub.
2. Netlify → **Add new site → Import an existing project** → GitHub → pick the
   repo. Netlify reads `netlify.toml` (`npm run build`, publish `dist`, Node 22,
   `NITRO_PRESET=netlify`).
3. **Site configuration → Environment variables** → add:

   | Variable | Value |
   | --- | --- |
   | `DATABASE_URL` | Supabase **transaction pooler** (port `6543`) |
   | `VITE_SUPABASE_URL` | `https://<ref>.supabase.co` |
   | `VITE_SUPABASE_ANON_KEY` | publishable / anon key |
   | `SUPABASE_URL` | same as `VITE_SUPABASE_URL` |
   | `SUPABASE_ANON_KEY` | same as `VITE_SUPABASE_ANON_KEY` |
   | `SUPABASE_SERVICE_ROLE_KEY` | secret / service_role key |
   | `CREDENTIALS_ENCRYPTION_KEY` | shared with the worker |
   | `WORKER_API_TOKEN` | shared with the worker |
   | `ADMIN_EMAILS` | your signup email |
   | `DATABASE_POOL_MAX` | `1` (serverless: one connection per invocation) |
   | `APP_ORIGIN` | leave blank for the first deploy |

4. Deploy. When it finishes, copy the site URL.
5. **Environment variables** → set `APP_ORIGIN` to that URL → **Deploys → Trigger
   deploy** (env changes need a redeploy).

Notes:

- `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` are baked into the browser
  bundle **at build time**; changing them requires a redeploy.
- The free plan has a monthly credit allowance and a ~10 s function timeout.
  This app only does quick DB reads/writes per request — the long InstaPy work
  happens on the worker — so it fits.
- The **worker does not run on Netlify**. Host it on a VPS (next section).

### Render (alternative, now requires a card)

The repo also includes `render.yaml`. Render → **New → Blueprint** → pick the
repo → fill the `sync: false` values → set `APP_ORIGIN` after the first deploy.
Render's free web service sleeps after ~15 min idle.

## 4. Deploy the worker (and optionally the web app) on a VPS

The worker needs Firefox and a long-running process, so it lives on a VPS. If
the web app is on Netlify, you only need the **worker** container here;
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

### Web app on Netlify? Run the worker only (recommended)

The worker only makes **outbound** calls, so this box needs no open ports beyond
SSH. On a fresh Ubuntu 24.04 VPS:

```bash
# 1. Code + Docker + swap + firewall
git clone https://github.com/hopeo2/growth.git growth
cd growth
sudo bash deploy/bootstrap-vps.sh

# 2. Worker config — no Supabase keys, no DATABASE_URL needed here
cp deploy/worker.env.example .env
nano .env
```

The `.env` needs three values from the web app's host (Netlify → **Site
configuration → Environment variables**):

```dotenv
WORKER_API_URL="https://growth00.netlify.app"   # your web app URL
WORKER_API_TOKEN="<same 64-hex value as the web app>"
CREDENTIALS_ENCRYPTION_KEY="<same 44-char base64 value as the web app>"
WORKER_POLL_SECONDS="60"                        # keeps Netlify invocations low
```

```bash
# 3. Build and start
docker compose up -d --build worker
docker compose logs -f worker
```

A healthy start logs `Worker 'worker-1' v0.1.0 starting against ...` followed by
heartbeats. Confirm in the web app: **Admin → Workers** lists the worker as
online.

Only `WORKER_API_TOKEN` and `CREDENTIALS_ENCRYPTION_KEY` must match the web app;
the worker never talks to Postgres directly.

> **Reaching Instagram.** A European VPS (this Austria box) usually reaches
> Instagram, but shared datacenter IPs are sometimes rate-limited. If runs fail
> with `checkpoint_required` or a login challenge, set `WORKER_DEFAULT_PROXY` to
> an HTTP(S) proxy — a residential/mobile proxy in the account's country works
> best. InstaPy does **not** support SOCKS proxies.

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

## 4b. Worker on an Altare sandbox (no Docker)

[Altare](https://altare.gg) gives every team an *Always Free* pool of memory,
CPU and disk, plus sandboxes you reach over SSH as root. Its free EU regions
(Frankfurt, Karlskrona/Stockholm, Helsinki, London) can reach Instagram
directly.

Sandboxes have **no Docker and no systemd**: install with `apt`, run processes
under `nohup`/`tmux`, and start them again after a restart.

In the console → **Apps → New app**:

| Field | Value |
| --- | --- |
| Software | **Sandboxes → Debian 12** |
| Region | Frankfurt, Stockholm, Helsinki or London |
| SSH access | a team SSH key, or a password (10+ chars) |
| Name | `growly-worker` |
| Memory / CPU / Disk | 2 GiB / 100% / as offered |

> **Why Debian 12?** It ships Python 3.11 and `firefox-esr` from `apt` — the same
> combination as the tested `Dockerfile.worker` image. Ubuntu 24.04 ships
> Firefox as a snap (which needs systemd), so its install differs; the script
> below handles either, but Debian is smoother.

Then, over SSH (or the browser shell in the console):

```bash
apt-get update && apt-get install -y git
git clone https://github.com/hopeo2/growth.git /root/growth
cd /root/growth
bash deploy/altare-sandbox.sh   # Firefox ESR, geckodriver, venv, Python deps
cp deploy/worker.env.example .env
nano .env                       # WORKER_API_URL + the two shared secrets
bash deploy/altare-start-worker.sh
tail -f /root/logs/worker.log
```

Set in `.env`:

```dotenv
WORKER_API_URL="https://growth00.netlify.app"
WORKER_API_TOKEN="<same as the web app>"
CREDENTIALS_ENCRYPTION_KEY="<same as the web app>"
WORKER_POLL_SECONDS="60"
```

Keep **Pause when idle** off (Settings → General), or Altare stops the sandbox
after a quiet spell. There is no auto-start, so after any restart run
`bash deploy/altare-start-worker.sh` again.

`deploy/altare-sandbox.sh` installs `firefox-esr` (or Mozilla's `.deb` on
Ubuntu), geckodriver 0.35, a `.venv` with both requirements files, and writes
`deploy/altare-start-worker.sh`.

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

# Growly automation worker

Python worker that polls the web app for queued jobs, runs
[InstaPy](https://github.com/InstaPy/InstaPy) against the requested Instagram
account, and streams activity back to the app.

```
web app (TanStack Start)  ──/api/worker/*──►  worker (this package)
        ▲                                          │
        └──────────── jobs / activity_logs ────────┘
                    (Postgres via Supabase)
```

The worker never talks to Postgres directly: everything goes through the
token-authenticated HTTP API at `/api/worker/{heartbeat,schedule,claim,progress,
events,complete,fail}`. Instagram credentials are decrypted locally with the
shared `CREDENTIALS_ENCRYPTION_KEY`.

## Layout

| File | Purpose |
| --- | --- |
| `__main__.py` | Poll loop: heartbeat → claim → run → complete/fail. |
| `config.py` | Reads environment (+ repo-root `.env`). |
| `crypto.py` | AES-256-GCM decryption, byte-compatible with the web app. |
| `api.py` | HTTP client for `/api/worker/*`. |
| `events.py` | `logging.Handler` that turns InstaPy logs into activity events. |
| `runner.py` | Builds an `InstaPy` instance from the job payload and runs it. |

## Setup

1. **System packages** (Firefox/geckodriver are installed by InstaPy's
   `instapy-dependencies-setup` scripts; on a headless VM you also want a
   virtual display):

   ```bash
   sudo apt-get update
   sudo apt-get install -y python3-venv firefox-geckodriver xvfb
   ```

2. **Virtualenv + dependencies:**

   ```bash
   cd /opt/growly            # wherever the repo lives
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r instapy-00/requirements.txt
   pip install -r worker/requirements.txt
   ```

3. **Configure** — the worker reads the same `.env` as the web app, plus a few
   `WORKER_*` keys. At minimum:

   ```dotenv
   APP_ORIGIN="http://127.0.0.1:3000"   # or the public URL
   WORKER_API_TOKEN="<same value as the web app>"
   CREDENTIALS_ENCRYPTION_KEY="<same value as the web app>"
   INSTAPY_PATH="./instapy-00"
   WORKER_NAME="worker-1"
   WORKER_POLL_SECONDS="20"
   WORKER_HEADLESS="true"
   # Fallback proxy for accounts without their own (see "Proxies" below):
   # WORKER_DEFAULT_PROXY="http://user:pass@proxy-host:8080"
   ```

   `WORKER_API_URL` overrides `APP_ORIGIN` if the API is reachable at a
   different address.

## Proxies (required in some countries)

Instagram is blocked in some countries (Iran among them) and blocks many
datacenter IPs, so the worker usually needs an **HTTP(S) proxy**:

- per account: fill in the `proxyUrl` field when adding the account;
- globally: set `WORKER_DEFAULT_PROXY`, used for any account without its own.

InstaPy only supports **HTTP(S)** proxies. If you only have a SOCKS proxy, run
`gost`/`3proxy` locally to expose it as HTTP and point the worker at that.

## Run

```bash
source .venv/bin/activate
python -m worker
```

Start one process per `WORKER_NAME`. Multiple workers are safe: claim uses
`SELECT … FOR UPDATE SKIP LOCKED`, so no two workers get the same job.

### Keeping it running

Run it under `tmux`, `screen`, `nohup`, or your own process manager:

```bash
nohup python -m worker > worker.log 2>&1 &
```

## How a run works

1. `claim` returns a `job` (`id`, `type`, `payload`) and the account
   (`username`, `proxyUrl`, encrypted `credentials`).
2. The worker decrypts the password and constructs `InstaPy(...)` with
   `log_handler=InstaPyLogHandler(...)`.
3. `login()` runs; on failure the job is reported as failed.
4. For `growth_run`, phases run in order — `like_by_tags`, `follow_by_tags`,
   `interact_by_users`, `like_by_locations`, `story_by_tags`, `unfollow_users` —
   each guarded so one failure doesn't abort the rest.
5. Progress is reported along the way; events are batched and flushed.
6. `complete` sends counters read from the InstaPy instance
   (`liked_img`, `followed`, `unfollowed`, `commented`, `stories_watched`,
   `followed_by`, `following_num`). The app folds these into daily stats.

`login_check` and `account_sync` jobs just verify the session and refresh
follower/following counts.

## Notes & limits

- InstaPy caches its logger per username. The worker clears
  `Settings.loggers[username]` before and after each run so the event handler is
  attached fresh and never leaks between accounts.
- Only HTTP(S) proxies are supported by InstaPy; other schemes are logged and
  ignored.
- Daily caps (`likesPerDay`, …) are divided by the number of runs per day to get
  a per-run budget. InstaPy's own quota supervisor is the backstop.
- Keep `WORKER_CONCURRENCY=1`: a single Firefox session per job avoids
  resource contention and account-safety issues.

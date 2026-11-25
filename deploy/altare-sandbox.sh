#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Growly worker on an Altare sandbox — native install (no Docker, no systemd).
#
# Altare sandboxes have no Docker and no systemd, so we install Firefox ESR,
# geckodriver and the Python dependencies directly and run the worker under
# nohup. Files, packages and settings survive sandbox restarts, but running
# processes do not — re-run deploy/altare-start-worker.sh after a restart.
#
# Recommended sandbox: Debian 12 (Python 3.11 + `firefox-esr` from apt), which
# matches the Dockerfile.worker image that is known to work.
#
#   sudo bash deploy/altare-sandbox.sh
#
# Then edit the config and start it:
#
#   nano .env                         # WORKER_API_URL + the two shared secrets
#   bash deploy/altare-start-worker.sh
#   tail -f /root/logs/worker.log
# ---------------------------------------------------------------------------
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GECKODRIVER_VERSION="${GECKODRIVER_VERSION:-0.35.0}"
GECKODRIVER_URL="${GECKODRIVER_URL:-https://github.com/mozilla/geckodriver/releases/download}"
LOG_DIR=/root/logs

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash deploy/altare-sandbox.sh" >&2
  exit 1
fi

log "Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates curl git bzip2 xvfb fonts-liberation tmux procps \
  python3 python3-venv python3-pip

# Firefox: Debian ships `firefox-esr`; Ubuntu 24.04 ships Firefox as a snap,
# which needs systemd, so on Ubuntu we use Mozilla's official .deb repository.
if apt-get install -y --no-install-recommends firefox-esr; then
  log "Installed firefox-esr from apt"
else
  log "firefox-esr not available — adding Mozilla's APT repository"
  install -d -m 0755 /etc/apt/keyrings
  curl -fsSL https://packages.mozilla.org/apt/repo-signing-key.gpg \
    -o /etc/apt/keyrings/packages.mozilla.org.asc
  echo "deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] https://packages.mozilla.org/apt mozilla main" \
    > /etc/apt/sources.list.d/mozilla.list
  apt-get update -y
  apt-get install -y --no-install-recommends firefox
fi

# InstaPy discovers Firefox with shutil.which("firefox").
if [[ ! -e /usr/local/bin/firefox ]]; then
  ln -sf "$(command -v firefox-esr || command -v firefox)" /usr/local/bin/firefox
fi

log "Installing geckodriver ${GECKODRIVER_VERSION}"
curl -fsSL "${GECKODRIVER_URL}/v${GECKODRIVER_VERSION}/geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz" \
  | tar -xz -C /usr/local/bin
chmod +x /usr/local/bin/geckodriver
geckodriver --version | head -1
firefox --version

log "Creating the Python virtualenv"
cd "${REPO_DIR}"
python3 -m venv .venv
./.venv/bin/pip install --no-cache-dir --upgrade pip
./.venv/bin/pip install --no-cache-dir \
  -r instapy-00/requirements.txt \
  -r worker/requirements.txt

mkdir -p "${LOG_DIR}"

log "Writing the start script"
cat > "${REPO_DIR}/deploy/altare-start-worker.sh" <<EOF
#!/usr/bin/env bash
# Start the Growly worker under nohup. Re-run this after a sandbox restart.
set -euo pipefail
REPO_DIR="${REPO_DIR}"
LOG_DIR="${LOG_DIR}"
cd "\${REPO_DIR}"

# Xvfb keeps InstaPy happy on the odd non-headless code path; harmless always.
pgrep -x Xvfb >/dev/null 2>&1 || Xvfb :99 -screen 0 1280x1024x24 >"\${LOG_DIR}/xvfb.log" 2>&1 &
export DISPLAY=:99

pkill -f "\.venv/bin/python -m worker" 2>/dev/null || true
sleep 1
nohup "\${REPO_DIR}/.venv/bin/python" -m worker >>"\${LOG_DIR}/worker.log" 2>&1 &
echo "worker started (pid \$!) — logs: \${LOG_DIR}/worker.log"
EOF
chmod +x "${REPO_DIR}/deploy/altare-start-worker.sh"

cat <<'EOF'

Done. Next:

  1. Fill in the config (it must live at the repo root, next to worker/):

       cd /root/growth
       cp deploy/worker.env.example .env
       nano .env

     Set WORKER_API_URL, WORKER_API_TOKEN and CREDENTIALS_ENCRYPTION_KEY.

  2. Start it and watch:

       bash deploy/altare-start-worker.sh
       tail -f /root/logs/worker.log

  Reminder: sandboxes have no systemd. After a sandbox restart, run
  `bash deploy/altare-start-worker.sh` again. Keep "Pause when idle" off.
EOF

#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Prepare a small (2 GB) Ubuntu/Debian VPS to run Growly.
#
# Installs Docker + Compose, adds swap (important on 2 GB), and locks down the
# firewall. Safe to re-run.
#
#   sudo bash deploy/bootstrap-vps.sh
#
# After this: clone the repo, fill in .env, then `docker compose up -d --build`.
# ---------------------------------------------------------------------------
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash deploy/bootstrap-vps.sh" >&2
  exit 1
fi

SWAPFILE=/swapfile
SWAP_GB="${SWAP_GB:-2}"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

log "Updating packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl gnupg git ufw

log "Installing Docker (official convenience script)"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
else
  echo "Docker already installed"
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose plugin missing — installing docker-compose-plugin" >&2
  apt-get install -y docker-compose-plugin || true
fi

log "Enabling Docker"
systemctl enable --now docker

log "Creating ${SWAP_GB}G swap at ${SWAPFILE} (skipped if present)"
if ! swapon --show | grep -q "${SWAPFILE}"; then
  if [[ ! -f "${SWAPFILE}" ]]; then
    fallocate -l "${SWAP_GB}G" "${SWAPFILE}" || \
      dd if=/dev/zero of="${SWAPFILE}" bs=1M count=$((SWAP_GB * 1024))
    chmod 600 "${SWAPFILE}"
    mkswap "${SWAPFILE}"
  fi
  swapon "${SWAPFILE}"
  grep -q "^${SWAPFILE} " /etc/fstab || echo "${SWAPFILE} none swap sw 0 0" >> /etc/fstab
else
  echo "Swap already active"
fi

log "Configuring firewall (SSH, HTTP, HTTPS)"
ufw allow OpenSSH || ufw allow 22/tcp || true
ufw allow 80/tcp  || true
ufw allow 443/tcp || true
ufw --force enable || true

log "Disabling memory overcommit for stability (optional)"
sysctl -w vm.overcommit_memory=1 | tee /etc/sysctl.d/90-growly.conf >/dev/null

cat <<'EOF'

Done. Next steps:

  1. git clone <your-repo> /opt/growly && cd /opt/growly
  2. cp .env.example .env    # fill in Supabase keys + secrets
  3. docker compose up -d --build
  4. docker compose logs -f

On a 2 GB box, if Firefox gets OOM-killed during a run, lower the worker's
memory use or move the web app to a different host (see DEPLOYMENT.md).
EOF

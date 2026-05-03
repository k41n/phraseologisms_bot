#!/usr/bin/env bash
# Deploy the phraseo bot to butler-api.k41n.com.
#
# Idempotent: creates the system user, venv, env file and systemd unit on
# the first run; subsequent runs only sync source and bounce the service.
#
# Local prerequisite: bot/.env exists with BOT_TOKEN=...
# Run as:  ./deploy.sh

set -euo pipefail

SSH_HOST="${SSH_HOST:-root@butler-api.k41n.com}"
APP_DIR="/opt/phraseo-bot"
DATA_DIR="/var/lib/phraseo-bot"
ENV_FILE_REMOTE="/etc/phraseo-bot.env"
SERVICE_NAME="phraseo-bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
APP_USER="phraseo"

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ENV="${PROJECT_ROOT}/bot/.env"

green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*" >&2; }

if [[ ! -f "${LOCAL_ENV}" ]]; then
  red "Missing ${LOCAL_ENV}. Create it from bot/.env.example before deploying."
  exit 1
fi
if [[ ! -f "${PROJECT_ROOT}/out/phraseo.json" ]]; then
  red "Missing out/phraseo.json. Run 'python3 collect.py' first."
  exit 1
fi

green "→ Sanity-checking SSH connection to ${SSH_HOST}"
ssh -o BatchMode=yes -o ConnectTimeout=10 "${SSH_HOST}" 'true'

green "→ Ensuring system user, dirs and packages exist"
ssh "${SSH_HOST}" "APP_USER='${APP_USER}' APP_DIR='${APP_DIR}' DATA_DIR='${DATA_DIR}' bash -s" <<'REMOTE_BOOTSTRAP'
set -euo pipefail
id "${APP_USER}" >/dev/null 2>&1 || useradd --system --home "${APP_DIR}" --shell /usr/sbin/nologin "${APP_USER}"
mkdir -p "${APP_DIR}" "${DATA_DIR}"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}" "${DATA_DIR}"
# python3-venv may or may not be preinstalled; install only if missing
if ! python3 -c "import ensurepip" 2>/dev/null; then
  apt-get update -qq
  apt-get install -y -qq python3-venv
fi
REMOTE_BOOTSTRAP

green "→ Syncing project source"
rsync -az --delete \
  --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
  --exclude='.pytest_cache' --exclude='cache/' \
  --exclude='bot/.env' --exclude='bot/progress.sqlite3' \
  --exclude='bot/tests' \
  --include='out/phraseo.json' \
  -e ssh \
  "${PROJECT_ROOT}/bot" \
  "${PROJECT_ROOT}/out" \
  "${PROJECT_ROOT}/collect.py" \
  "${SSH_HOST}:${APP_DIR}/"

green "→ Installing/refreshing Python venv"
ssh "${SSH_HOST}" "APP_USER='${APP_USER}' APP_DIR='${APP_DIR}' bash -s" <<'REMOTE_VENV'
set -euo pipefail
if [[ ! -d "${APP_DIR}/.venv" ]]; then
  sudo -u "${APP_USER}" python3 -m venv "${APP_DIR}/.venv"
fi
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install --quiet --upgrade pip
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install --quiet -r "${APP_DIR}/bot/requirements.txt"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"
REMOTE_VENV

green "→ Installing env file"
# Replace PHRASEO_DATA / PROGRESS_DB to absolute paths on the server.
TMP_ENV=$(mktemp)
trap 'rm -f "${TMP_ENV}"' EXIT
{
  grep -E '^BOT_TOKEN=' "${LOCAL_ENV}"
  echo "PHRASEO_DATA=${APP_DIR}/out/phraseo.json"
  echo "PROGRESS_DB=${DATA_DIR}/progress.sqlite3"
} > "${TMP_ENV}"
scp -q "${TMP_ENV}" "${SSH_HOST}:${ENV_FILE_REMOTE}"
ssh "${SSH_HOST}" "chown root:${APP_USER} ${ENV_FILE_REMOTE} && chmod 640 ${ENV_FILE_REMOTE}"

green "→ Installing systemd unit"
scp -q "${PROJECT_ROOT}/bot/phraseo-bot.service" "${SSH_HOST}:${SERVICE_FILE}"
ssh "${SSH_HOST}" "chmod 644 ${SERVICE_FILE} && systemctl daemon-reload && systemctl enable --quiet ${SERVICE_NAME} && systemctl restart ${SERVICE_NAME}"

green "→ Verifying"
sleep 2
ssh "${SSH_HOST}" "systemctl status --no-pager --lines=15 ${SERVICE_NAME}" || {
  red "Service did not come up cleanly. Recent journal:"
  ssh "${SSH_HOST}" "journalctl -u ${SERVICE_NAME} --no-pager -n 30"
  exit 1
}

green "✓ Deploy complete — bot @phraseologisms_bot is running on ${SSH_HOST}"

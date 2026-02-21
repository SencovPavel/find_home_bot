#!/usr/bin/env bash
set -euo pipefail

: "${APP_DIR:?APP_DIR is required}"
: "${SYSTEMD_SERVICE:?SYSTEMD_SERVICE is required}"

if [[ ! -d "$APP_DIR" ]]; then
  echo "Directory does not exist: $APP_DIR" >&2
  exit 1
fi

cd "$APP_DIR"

git fetch --all --prune
git reset --hard origin/main

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Python virtual environment not found in $APP_DIR/.venv" >&2
  exit 1
fi

.venv/bin/pip install --upgrade pip
.venv/bin/pip install .

sudo systemctl restart "$SYSTEMD_SERVICE"
sudo systemctl is-active --quiet "$SYSTEMD_SERVICE"
sudo systemctl status "$SYSTEMD_SERVICE" --no-pager --lines=20

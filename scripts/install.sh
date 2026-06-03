#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/ralleh/ralleh-voice}"
ENV_FILE="${ENV_FILE:-/etc/ralleh-voice/ralleh-voice.env}"
SERVICE_FILE="/etc/systemd/system/ralleh-voice.service"

if [[ $EUID -ne 0 ]]; then
  echo "Run as root (or via sudo)."
  exit 1
fi

mkdir -p "$APP_ROOT" /etc/ralleh-voice /var/log/ralleh-voice

if [[ ! -f "$ENV_FILE" ]]; then
  install -m 600 .env.example "$ENV_FILE"
  echo "Created $ENV_FILE from .env.example (review before start)."
fi

python3 -m venv "$APP_ROOT/.venv"
"$APP_ROOT/.venv/bin/pip" install --upgrade pip
"$APP_ROOT/.venv/bin/pip" install .

install -m 644 deploy/systemd/ralleh-voice.service "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable ralleh-voice.service

echo "Installed. Start with: systemctl start ralleh-voice"

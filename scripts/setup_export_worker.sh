#!/usr/bin/env bash
set -euo pipefail

WORKDIR="${1:-/opt/hmm-connect}"
PYTHON_BIN="${2:-python3}"
SERVICE_USER="${SUDO_USER:-$(id -un)}"
SERVICE_NAME="hmm-connect-export-worker"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

cd "${WORKDIR}"

if [ ! -d .venv ]; then
  "${PYTHON_BIN}" -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-worker.txt

mkdir -p /tmp/hmm-connect-exports

.venv/bin/python - <<'PY'
import boto3
import openpyxl
from app.core.config import settings
from app.core.database import SessionLocal

assert settings.EXPORT_S3_BUCKET or settings.S3_BUCKET, "EXPORT_S3_BUCKET or S3_BUCKET is required"

with SessionLocal() as db:
    db.execute(__import__('sqlalchemy').text('SELECT 1'))

print('openpyxl:', openpyxl.__version__)
print('aws region:', settings.AWS_REGION or boto3.session.Session().region_name)
print('export bucket:', settings.EXPORT_S3_BUCKET or settings.S3_BUCKET)
import app.scripts.journal_import_worker
print('journal import worker import: OK')
print('EC2 export/import worker prerequisites OK')
PY

sudo tee "${SERVICE_FILE}" >/dev/null <<EOF
[Unit]
Description=HMM Connect asynchronous XLS export worker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${WORKDIR}
ExecStart=${WORKDIR}/.venv/bin/python -m app.scripts.export_worker --poll --interval 2
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

printf '\nWorker service installed.\n'
sudo systemctl --no-pager --full status "${SERVICE_NAME}" | head -n 20

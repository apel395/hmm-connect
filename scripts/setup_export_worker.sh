#!/usr/bin/env bash
set -euo pipefail

WORKDIR="${1:-/opt/hmm-connect}"
PYTHON_BIN="${2:-python3}"

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
print('EC2 export worker prerequisites OK')
PY

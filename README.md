# HMM Connect Backend

FastAPI backend for HMM Connect purchasing, inventory, approvals, audit
traceability, payables/receivables, and accounting.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Existing installations should run `alembic upgrade head`. Because migrations
older than `20260720_approval_workflows` were absent from the recovered Git
branch, a brand-new empty database can be initialized with:

```bash
python scripts/bootstrap_database.py
```

Docker users can run `docker compose up --build`. The API health check is
available at `GET /health`, and OpenAPI documentation is at `/docs`.

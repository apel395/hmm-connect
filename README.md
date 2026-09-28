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

## September 2026 finance contracts

The frontend lives on `main`; this branch supplies the FastAPI routes under
`/api/v1`. After upgrading the database, finance users can query:

- `GET /ap-movement`: posted invoice, payment and adjustment movements with
  opening, running and closing balances.
- `GET /journal-entries`: `supplier_id` filter and full filtered debit/credit
  summary.
- `GET /general-ledger` and `/general-ledger/print`: `search_type`,
  `account_from_id`, `account_to_id` and full filtered totals.
- `GET /payments`: full filtered payment total. AP users see only payments
  they created, including on payment detail and action routes.
- `GET /stock-reconciliation`: compares the recorded movement ledger at
  the fiscal-year boundary with current inventory and later movements.
  `POST /stock-reconciliation/requests` records a pending, audited variance
  request; it does not change stock. Finance management permission is required.

Receiving before 2026-01-01 is rejected on creation, editing and posting.
Previously posted historical records remain for audit and reconciliation.
Opening balances can be recorded only once for a fiscal year; recorded
amounts cannot be voided through the routine endpoint. Corrections require
a separate controlled adjustment journal.


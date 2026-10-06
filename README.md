# HMM Connect Backend

FastAPI backend for HMM Connect purchasing, inventory, approvals, audit
traceability, payables/receivables, and accounting.

## Local setup

Login allows one active session per user. If a connection drops after login,
the login page offers **Sign in and end previous session**. The API accepts
`replace_session=true` on `/api/v1/auth/login` only after verifying the password
and active account, then replaces the session under a user row lock. Previous
tokens cannot access the app or log out the replacement session. Normal login
still reports a conflict for an active session; idle sessions expire after 30
minutes. Recovery does not require an administrator or a database reset.

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
Opening balances are manually entered annual starting values, separate from
transaction journals. They are never automatically balanced with an equity
contra. Corrections use the audited opening-balance revision while an accounting
period in the year is open. Trial Balance keeps that opening separate from all
activity in the selected fiscal year.

## October 2026 reporting and closing

Run `.venv/bin/alembic upgrade head` on EC2 after pulling `backend`. The API runs
on AWS Lambda and deployment is triggered by a push/merge to `backend`; EC2 runs
the database and heavy processing. The UI is deployed from `main`.

- `/financial-reports/setup`: account visibility checklist, KAP header-only
  display and the current-year earnings posting account. Display selection
  changes detail only; report totals retain the complete scoped ledger.
- `/financial-reports/comparison`: monthly (MTD) and annual (YTD) actual,
  approved budget, previous month and same period of the previous year.
  Comparisons use the same elapsed cutoff day, clipped for shorter months.
  `/financial-reports/comparison/export` exports the same scope to Excel.
- Profit & Loss uses only activity in the requested period and excludes
  `PERIOD_CLOSE`/`YEAR_END` journals. Balance Sheet uses manual annual opening
  values plus posted year activity, with credit-balance contra assets deducted.
- P&L supports unit/location/department. Balance Sheet defaults to consolidated.
  Assigned-location users are restricted on report reads and exports.
- `/budgets`: monthly account budgets by business unit/location/department,
  draft editing, submit/approve/reject/lock/cancel. Approved/locked budgets feed
  comparisons. Missing budgets show unavailable; overlapping plans require an
  explicit budget selection. P&L budgets are full-month plans. Balance Sheet
  budgets are month-end balance targets, never the sum of monthly balances.
- New revenue postings and budgets use account `400`. Migration activates that
  account and maps POS revenue to it. Historical child-account postings are
  preserved and grouped under `400` in the comparison report.
- Closing `/fiscal-periods/{id}/close` automatically generates balanced journals
  per unit/location/department, dated at the period end, transferring its result
  to `CURRENT_YEAR_EARNINGS_ACCOUNT`. It then locks the period. Empty periods
  create no zero journal; repeated closes return existing evidence.
- Reopening voids those generated closing journals and removes their GL rows,
  retaining audit evidence. Close/reopen share the posting period row lock.
  Closing journals cannot be manually unposted. Year closing closes all twelve
  months and records December 31 of the selected year, not the execution date.
  Company period/year management requires unscoped location access.
- Supplier invoice entry can already load received quantity, price, PPN and
  dimensions directly from an eligible receiving document.

If report setup has not been migrated, actual statements remain readable with
the full default account layout; absent budget tables show unavailable budget
values, never an invented zero. Setup reads/writes require the migration and
return a database-update message until it completes. To inspect the production
schema, serialize both reports, and verify the closing earnings account without
writing data, run:

```bash
.venv/bin/python scripts/check_financial_reports.py --date 2026-10-06
.venv/bin/python scripts/check_financial_reports.py --date 2026-10-06 --location-id 1
```

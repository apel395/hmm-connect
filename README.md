# MMH Connect Backend

FastAPI backend for MMH Connect purchasing, inventory, approvals, audit
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
- Location/unit/department report activity uses explicit line dimensions, then
  the journal header when a line has no override. Unit-filtered opening balances
  use only locations explicitly assigned to that unit; unassigned openings are
  not allocated to a unit or department. No opening record is changed.
- Prior-year comparisons without accounting evidence in that year and scope
  return unavailable values (screen dash, blank Excel cells), not a claimed
  zero. Current-period zero activity remains zero. Report headings and exports
  identify unit/location/department names.
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


## Finance delivery — 2026-10-07

- Visible branding is MMH. The financial dashboard uses posted monthly/YTD activity, department performance, margins, rankings and actual financial position. The HTML reference supplies presentation only; its embedded numbers are never imported.
- Financial report presentation uses account names. IDs/codes remain internal mappings. Account drilldown uses exact account IDs and preserves date/location/unit scope. P&L includes configured departments, even with zero activity, in screen/print/Excel. Balance Sheet offers separate KAP summary and detailed print layouts.
- Manual journals may contain a single debit or credit line and may be posted with a difference. No contra is inserted. The difference remains in GL and Trial Balance. Source-document journals must still balance, posting still requires an open accounting period, and opening balances remain separate manually entered starting values.
- SELL items support a service-charge percentage. POS snapshots charge rates and amounts on each sale line and includes the charge in the sale total and revenue account 400. Existing tax calculations are unchanged; service charge is not silently treated as tax.
- Payments keep invoice allocation, bank fee and signed short/over separate. Cash funding = invoice settlement + bank fee + short/over. A positive short/over increases cash paid; a negative amount decreases it. Fees require explicit expense accounts, and a difference reason is required for fees/short-over or partial settlement. Editing funding never rewrites invoice allocations or taxes.
- Budget Input uses the existing monthly/location/department budget module. General Cashier and Petty Cash Usage create auditable draft journals with supporting references, location and department; posting creates GL once. Supplier/customer invoice settlements stay in their respective payment modules. Draft cashier entries can be voided and entered again. Cashier print loads all filtered pages.
- AR invoice printing supports per-client title, billing details, description, payment instructions, footer and optional settlement display. Legacy AR has no location dimension, so these invoice reads/settings require consolidated finance access. Exact client stationery requires the client's approved sample; the app does not invent invoice line items or tax.
- The workspace Back control closes the current tab and returns to the last active tab. Unsaved journal/payment/invoice/cashier inputs remain recoverable in the user's browser.

Backend is deployed to Lambda by pushing/merging `backend`. EC2 handles PostgreSQL migrations and heavy export workers, not the API server. Required migration: `20261007_finance_delivery` (additive columns and AR print settings; no balance changes).

```bash
cd /opt/hmm-connect
git pull --ff-only origin backend
.venv/bin/alembic upgrade head
.venv/bin/alembic current
.venv/bin/python scripts/check_finance_1007.py --year 2026 --month 10
```

Restart the existing EC2 export worker after pulling so Excel GL drilldown uses the same exact account and search filters. Keep existing imports/private-backups and environment configuration.


## Item creation — 2026-10-08

New items show an automatic code after selecting their group/subgroup (BUY) or sales classification (SELL). `/products/next-code` is a read-only preview; saving uses `auto_code=true` and recomputes the next available code under a PostgreSQL transaction lock. The existing numeric pattern is retained, e.g. FOOD / MEAT `1-1` gives `1-100001`. Existing/inactive codes are not reused, BUY/SELL catalogs are validated separately, and existing item codes remain unchanged during editing. Explicit codes remain supported for existing API/import clients.

Purchase and Usage UOM are text inputs with optional common-unit suggestions. Custom units such as Tray, Portion, Bucket or Serving are accepted within the existing 20-character field size. This change requires no database migration and does not alter stock, journals or existing classifications.


### BUY Item Master and Fixed Assets — 2026-10-08
Asset intake creates or reuses a classified BUY/FIXED_ASSET item and persists its ID on the fixed asset. Invoice registration also links the manual invoice line to that item, using a reference-only update so posted source tax and amounts remain unchanged. Existing codes and accounting are not regenerated. The ASSET catalog is reused; computer equipment under 100-600-104 uses the existing KOMPUTER subgroup. Ambiguous matches require explicit selection rather than silently reclassifying items.

Run `alembic upgrade head` to add the nullable fixed asset item link. For the historical computer, run `python scripts/link_fixed_asset_items.py --asset-id 2 --invoice-id 611 --user-id 45 --subgroup 4-4` for a dry run, then repeat with `--apply`. The script locks and checks the expected source, records an audit, and leaves invoice amounts, tax, journals and inventory unchanged. Fixed Asset details show the linked BUY item code and name.

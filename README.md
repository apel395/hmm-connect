# MMH Connect ERP

MMH Connect is the operational ERP for Hotel Mutiara Merdeka and Project Catering. The system covers purchasing, receiving, inventory, POS, finance, fiscal reporting, administration, approvals, and audit traceability.

This README is the **current module snapshot**. Keep it updated when a module, workflow, permission, or accounting rule changes so the next maintenance/fix session starts from the same picture.

## Repository / deployment

The login page offers **Sign in and end previous session** when an active
session blocks login after a disconnect. This checks the password again and
replaces the previous session; only one session remains active. Network errors
during session initialization retain the saved token for a retry, and responses
from an old session cannot erase a newer login.

- Frontend source and Vercel deployment branch: `main`
- Backend / Lambda source branch: `backend`
- Production frontend: `https://connect.mutiaramerdekahotel.com`
- Backend: FastAPI + SQLAlchemy + PostgreSQL
- Frontend: React + Vite + React Router + TanStack Query

Frontend:

```bash
npm install
npm run lint
npm run build
```

Backend migrations:

```bash
alembic upgrade head
```

## Access model

Access is permission-based with role fallbacks for legacy mappings.

Core roles currently include:

- `SYSTEM_ADMINISTRATOR`
- `GENERAL_MANAGER`
- `GENERAL MANAGER`
- `PURCHASING`
- `HO PURCHASING`
- `WAREHOUSE`
- `STORE`
- `CHEF`
- `PM/CAMP BOSS`
- `FINANCE`
- `AP`
- `DEPARTMENT`
- `AUDITOR`
- `VIEWER`

The `AP` role is intentionally restricted to the Accounts Payable workspace and AP-related permissions.

There are **no documented default/trial users or passwords** in this repository. User accounts are managed from Administration > Users.

## Workspace layout

Desktop navigation starts as a narrow icon rail. Hovering or keyboard focus shows the module name immediately in a floating label outside the scrolling rail; clicking an icon opens its permitted submenu. Escape dismisses the label and submenu. The rail or header toggle expands the full sidebar, and the browser remembers the preference. Mobile uses the header menu drawer. Selecting a module, clicking outside, or pressing Escape closes the drawer or submenu. Lists use compact single-line rows and reduced spacing between table sections. Stock Movement displays IN or OUT in the Event column, with source links in the Source document column.

## Module snapshot

### Dashboard

Route: `/dashboard`

Purpose:

- operational overview
- role/permission-aware entry point
- summary metrics from purchasing, inventory, and finance

Permission: `dashboard.view`

### Approval Center

Route: `/approval-center`

Purpose:

- centralized approval queue
- PR / Market List / PO / Receiving and other configured approval workflows
- ordered workflow steps with role, department, and location scope
- approval history remains attached to the document

Permission: `approval.view`

Approval configuration is data-driven rather than hardcoded into each module.

### Master Data

#### Items

Route: `/products`

Purpose:

- product/item master
- classification and accounting defaults used by purchasing, receiving, inventory, and finance
- active/inactive lifecycle

Permission: `products.view`

#### Suppliers

Route: `/suppliers`

Purpose:

- supplier master
- supplier banking and payable information
- used by PO, supplier invoice, AP, payment voucher, and payment flows

Permission: `suppliers.view`

#### Warehouses

Route: `/warehouses`

Purpose:

- warehouse master
- warehouse-to-location mapping
- stock ownership / storage context

Permission: `warehouse.view`

#### Business Units / Departments / Locations

Routes:

- `/organization-dimensions?section=business-units`
- `/organization-dimensions?section=departments`
- `/organization-dimensions?section=locations`

Purpose:

- organizational dimensions used by workflow, inventory, journals, reports, and audit context
- location is the main operational scope dimension

Administration permission: `admin.settings.manage`

### Purchasing

#### Purchase Requisition

Route: `/purchase-requisitions`

Core flow:

```text
DRAFT
  ↓
PENDING_APPROVAL
  ↓
APPROVED
  ↓
Convert to PO
```

Purpose:

- request product/service demand
- estimated price only; final purchasing cost belongs to the PO
- configurable approval workflow

Permission family: `pr.*`

#### Market List

Route: `/market-lists`

Purpose:

- operational purchasing requests
- approval flow separate from PR where required

Permission family: `market_list.*`

#### Purchase Order

Route: `/purchase-orders`

Purpose:

- supplier commitment
- may combine approved requisitions
- final unit price
- expected / expiry dates
- receipt tolerance
- approval workflow

Permission family: `po.*`

#### Receiving

Route: `/receiving`

Core accounting flow for warehouse receiving:

```text
Goods Receipt
Dr Inventory / Expense
Cr AP Suspense
```

Purpose:

- PO-based and supported direct receiving
- warehouse or direct-use destination
- quantity and cost evidence
- creates stock movement
- creates accounting journal for posted receipt

Permission family: `receiving.*`

### Inventory

#### Stock

Route: `/inventory`

Purpose:

- on-hand quantity by product / warehouse
- average cost state

Permission: `inventory.view`

#### Stock Movement

Route: `/inventory/movements`

Purpose:

- movement history
- links to receipts and operational documents
- quantity / unit cost evidence

Permission: `inventory.view`

#### Store Request

Route: `/store-requests`

Purpose:

- internal stock request / issue workflow

Permission: `store_request.view`

#### Stock Opname

Route: `/stock-opnames`

Purpose:

- physical stock count
- variance handling and audit trail

Permission: `stock_opname.view`

#### Stock Adjustment

Route: `/stock-adjustments`

Purpose:

- controlled stock correction
- adjustment history

Permission: `inventory.view`

### Point of Sales

#### Register

Route: `/pos`

Purpose:

- point-of-sale transaction entry

Permission: `pos.view`

#### Sales

Route: `/pos/sales`

Purpose:

- sales transaction history / review

Permission: `pos.view`

### Finance

#### Finance Dashboard

Route: `/finance-dashboard`

Purpose:

- finance operational summary

Permission: `finance.view`

#### Accounts Payable workspace

Route: `/accounts-payable`

The AP workspace contains the payable flow in this order:

```text
Supplier Invoice
      ↓
Payment Voucher   (preferred, not mandatory)
      ↓
Payment
      ↓
Journal
      ↓
Bank / GL
```

Direct payment without a Payment Voucher remains supported.

Permission: `ap.view`

##### Supplier Invoice

Main behavior:

- supplier invoice can be sourced from one or multiple Goods Receipts
- supplier filter supports supplier name search
- posting clears AP Suspense / GRNI and creates AP liability
- VAT / tax lines are supported
- invoice balances drive payment eligibility

Accounting:

```text
Dr AP Suspense / GRNI
Dr Input VAT / variance when applicable
Cr Accounts Payable
```

Permission family: `supplier_invoice.*`

##### Payment Voucher

Purpose:

- internal AP payment approval / preparation document
- preferred workflow before payment
- does **not** itself create GL entries
- payment may still be created directly without a voucher

Permission family: `payment.*`

##### Payment

Purpose:

- allocate payment to posted supplier invoices
- funding source must be a valid active payment-enabled bank/cash account
- approval creates/prepares the payment journal
- final accounting comes from the posted journal

Accounting:

```text
Dr Accounts Payable
Cr Bank / Cash
```

Print document label is **Payment**, not Payment Request.

Permission family: `payment.*`

#### Accounts Receivable

Route: `/accounts-receivable`

Purpose:

- receivable monitoring and finance operations

Permission: `finance.view`

#### Cash & Bank

Route: `/cash-bank`

Purpose:

- cash / bank operational view
- funding account integration

Bank Accounts are configured in Finance Setup and linked to posting COAs with subtype:

- `BANK`
- `CASH`
- `PETTY_CASH`

A funding account must be active and `is_payment_account = true`.

#### Journal

Route: `/journal`

Sub-workspaces include:

- Journal
- General Ledger
- Trial Balance

General Ledger account filter is searchable by account code or account name and loads all active accounts.

Trial Balance calculation:

```text
Opening Balance = manually recorded fiscal-year opening balances
Period Movement = posted activity in the selected 2026 period
Closing Balance = Opening + cumulative activity through date_to
```

Only posted journals affect financial statements and ledger reports.

AP Suspense is expected to clear when the receipt and supplier-invoice sides are complete:

```text
Receipt:
Dr Inventory / Expense
Cr AP Suspense

Supplier Invoice:
Dr AP Suspense
Cr Accounts Payable
```

Permission: `journal.view`

#### Accounting Periods

Route: `/finance-setup/accounting-periods`

Purpose:

- fiscal/accounting posting controls
- initialize fiscal year
- close / reopen periods
- Finance posting-date validation

Posting follows the period containing the selected document date. Each period has an Allow backdated entries setting, enabled by default. A past date is allowed only when that period is open and backdating is enabled. Closed and missing periods reject posting. The frontend calendar and backend posting-status use the same policy; Finance can manage it from Accounting Periods or the System Settings link. Business today is calculated in Asia/Jakarta. The 2026 receiving cutoff remains in force.

Migration required on EC2: `.venv/bin/alembic upgrade head` (revision `20261004_period_backdates`) before deploying the backend that reads the new period policy.

Permission: `finance.manage`

#### Reconciliation

Route: `/financial-reconciliation`

Purpose:

- read-only overview of AP, AR, AP Suspense, and Inventory source balances against posted GL
- as-of summary of source and posted GL closing balances, differences, and status; period analysis belongs in each module
- linked COAs open the filtered General Ledger; module links open AP, Receiving, AR, or Inventory for document-level review
- source documents, journal evidence, and corrections belong in their owning modules; this overview creates no journal

Permission: `finance.view`

#### Fixed Assets

Route: `/fixed-assets`

Purpose:

- fixed-asset accounting workflow

Permission: `finance.view`

### Fiscal

#### Fiscal COA

Route: `/finance/fiscal/coa`

Purpose:

- fiscal account mapping

#### Fiscal Reconciliation

Route: `/finance/fiscal/reconciliation`

Purpose:

- fiscal reconciliation workflow

#### Lampiran 1D

Route: `/finance/fiscal/lampiran-1d`

Purpose:

- fiscal reporting output

#### SPT Tahunan 1771

Route: `/finance/fiscal/spt-1771`

Purpose:

- annual corporate tax reporting workflow

Permission family: `fiscal.*`

### Reports

#### Purchasing Reports

Route: `/reports/purchasing`

Permission: `reports.purchasing`

#### Inventory Reports

Route: `/reports/inventory`

Permission: `inventory.view`

#### Cash Flow Statement

Route: `/cash-flow-statement`

Permission: `reports.view`

#### Balance Sheet

Route: `/balance-sheet`

Permission: `reports.view`

#### Profit & Loss

Route: `/profit-loss`

Permission: `reports.view`

Financial reports are based on posted journal activity rather than document status alone.

### Administration

#### Users

Route: `/users`

Purpose:

- create / update users
- role assignment
- organizational assignment

Permission: `admin.users.manage`

#### Roles

Route: `/roles`

Purpose:

- role administration
- permission assignment
- core-role bootstrap

Permission: `admin.roles.manage`

#### Finance Setup

Route: `/finance-setup`

Purpose includes:

- Chart of Accounts
- Bank Accounts
- accounting setup used by Finance

Permission: `finance.manage`

#### System Settings

Route: `/settings`

Permission: `admin.settings.manage`

## September 2026 finance UI work

The frontend branch adds AP Movement, payment list totals, Journal supplier filtering, General Ledger search and account range controls, Trial Balance links to account ledgers, and a Stock Consolidation workspace under Financial Reconciliation. Opening Balance input is locked in the UI after an entry is recorded, and the recorded figures remain visible. The Recreate GL control was removed from Journal Detail.

Payment creation allows earlier dates; Finance posting still follows backend accounting period validation. Receiving creation and editing reject dates before 2026-01-01 in the UI. Historical 2025 receiving records are not deleted by this frontend change.

The AP Movement and Stock Consolidation screens call `/ap-movement` and `/stock-reconciliation`; stock adjustment requests call `/stock-reconciliation/requests`. Supplier filtering and complete filtered totals in Journal/GL also need backend support. The API must enforce AP user visibility, the stock cutoff, the one-time opening balance rule, and the accounting period controls. Until those contracts are implemented, the UI cannot complete those workflows or guarantee access restrictions.

## Accounting / document flow

The main purchasing-to-payment accounting chain is:

```text
Purchase Requisition
        ↓
Purchase Order
        ↓
Goods Receipt
        ↓
Inventory / Expense
        ↓
AP Suspense
        ↓
Supplier Invoice
        ↓
Accounts Payable
        ↓
Payment Voucher (preferred / optional)
        ↓
Payment
        ↓
Bank / Cash
```

Payment Voucher is an internal AP approval document and does not post GL by itself.

## Approval engine

The approval engine uses four concepts:

```text
Approval Workflow
        ↓
Workflow Steps
        ↓
Approval Request
        ↓
Approval Request Steps
```

Workflow steps can be scoped by:

- role
- department
- location

The workflow configuration is copied into each approval request so historical approvals preserve the rules that applied when the document was submitted.

## Audit principle

Audit is a core ERP feature.

Important actions preserve actor and document context such as:

```text
User
Actor name
Department
Location
Roles
Action
Document
Workflow
Timestamp
Before / After details
Source / import batch
```

Snapshot fields are intentional: changing a user's current department, location, or roles must not rewrite historical audit context.

## Historical-data / reconciliation notes

Historical finance reconstruction may be driven from bank evidence, invoice evidence, and receiving evidence, but each accounting event keeps its actual business date.

Rules:

- Bank statement is authoritative for cash movement.
- Receiving / physical evidence is authoritative for stock quantity and cost.
- Bank movement alone must not invent missing receiving quantities.
- Historical corrections must preserve explicit source references.
- Missing operational documents should be represented as controlled historical reconstruction, not fabricated live workflow documents.

Current known historical work has included:

- January 2026 purchasing / receiving / supplier invoice reconstruction
- AP Suspense reconciliation
- supplier invoice tax reconstruction where source evidence exists
- cash / bank registration from active COA
- payment and GL reconciliation

## Seeding supplier invoices from PO workbooks

Monthly PO workbooks can be loaded end-to-end with:

```text
Workbook
  ↓
Goods Receipt
  ↓
Supplier Invoice
  ↓
Journal
```

Example:

```bash
python3 scripts/seed_po_minas_receiving_invoice.py \
  --workbook "PO MINAS Januari 2026.xlsx" \
  --department-code WAREHOUSE \
  --create-missing-products \
  --create-missing-suppliers \
  --apply
```

Omit `--apply` or use the script's dry-run mode when available to preview before writing.

Historical import scripts should be treated as controlled migration/reconciliation tools, not routine live-entry APIs.

## Maintenance rule

When fixing or extending MMH Connect:

1. Use the current backend behavior / API contract as the source of truth for frontend changes.
2. Preserve organization scope: Business Unit, Department, Location.
3. Preserve auditability and source references.
4. Never silently bypass closed-document or posted-journal controls.
5. Prefer batching frontend fixes on a working branch and merging once to `main` to reduce unnecessary Vercel deployments.
6. Update this README when a module, role, accounting rule, or workflow changes.


## Financial report printing and input recovery (2026-10-06)

- Profit & Loss and Balance Sheet use dedicated `/profit-loss/print` and `/balance-sheet/print` previews, with applied date, budget, organization scope, zero-value and KAP settings sent to the same reporting API. The application shell and interactive controls are excluded.
- P&L printing groups MTD and YTD comparisons. Balance Sheet printing begins with a T-format closing position, followed by separate MTD/YTD comparison pages. Tables repeat column headings and retain complete account names, signed amounts and unavailable comparison dashes. KAP uses the API's header-only rows.
- Journal creation/editing, supplier payment creation/editing and supplier invoice creation/editing recover unsaved browser input by authenticated user and document ID. Closing, navigation or refresh preserves it; successful saves and explicit Discard input clear it. Restored input still uses normal API validation and never submits, approves or posts automatically.
- Recovery uses versioned browser local storage, so it is specific to that browser/device and excludes credentials/files. Session expiry clears session credentials without erasing input recovery. When storage is unavailable, the form shows an alert instead of promising recovery.


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

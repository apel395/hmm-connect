# HMM Connect ERP

HMM Connect is an ERP prototype focused on controlled purchasing, document traceability, inventory, finance, and auditability.

This project is currently in **trial / pre-production mode**. The source-of-truth workflow is temporarily distributed as a project snapshot while the company evaluates the system.

## Business flow

```text
User
  ↓
Purchase Requisition (PR)
  ↓
Configurable approval layers
  ↓
Approved PR
  ↓
Purchase Order (PO)
  ↓
Configurable approval layers
  ↓
Approved PO
  ↓
Goods Receipt
  ├── Inventory
  └── Direct Consumption
```

## Procurement flow

### 1. Purchase Requisition (PR)

A requester creates a PR with:

- Product
- Quantity
- Estimated price
- Notes

The estimated price is an **estimate only**. It is not the final purchasing cost.

PR lifecycle:

```text
DRAFT
  ↓
PENDING_APPROVAL
  ↓
APPROVED
```

A PR can also be rejected.

### 2. Layered PR approval

Approval is **not hardcoded as `Section → Manager` in application code**.

The workflow is configurable:

```text
PR_APPROVAL
  1. Section Approval
  2. Manager Approval
```

Each approval step can be configured by:

- Role
- Department (optional)
- Location (optional)

Example:

```text
Step 1
Role: SECTION_APPROVER
Department: Operations

Step 2
Role: MANAGER
```

A workflow can be changed without changing the PR business logic.

### 3. Purchase Order (PO)

A PO can combine **multiple approved PRs**.

```text
PR-000001 ─┐
            ├── PO-000001
PR-000002 ─┘
```

PO stores:

- Supplier
- PO items
- Final unit price
- Expected date
- Expiry date
- Receipt tolerance

The PO price is separate from the PR estimated price.

### 4. Layered PO approval

Default trial workflow:

```text
PO_APPROVAL
  1. Section Approval
  2. Manager Approval
  3. Finance Approval
```

The same configurable approval engine is used for PR and PO.

### 5. Goods Receipt

A PO is received only after approval.

```text
Approved PO
  ↓
Goods Receipt
```

The receiving user chooses the destination:

```text
Inventory
```

or

```text
Direct Consumption
```

Receipt cost is derived from the PO and is not manually changed during receiving.

The PO receipt tolerance controls how much quantity variance is allowed.

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

### Workflow definition

Defines the business flow:

```text
PR_APPROVAL
PO_APPROVAL
```

### Workflow steps

Defines the ordered approval layers.

### Approval request

Created when a document is submitted.

The request stores the workflow used by the document.

### Approval request steps

The workflow configuration is copied into the document approval instance.

This is intentional.

If the company changes the workflow next month, an old PR must still show the approval chain that was required when it was submitted.

## Audit principle

Audit is a core ERP feature.

Every important action records:

```text
User
Department
Location
Roles
Action
Document
Timestamp
Details
```

Example:

```text
Advan
Purchasing
Jakarta Office
PURCHASING

SUBMITTED PR-000001
```

The user identity context is snapshotted in the audit log. If the user later changes department, location, or role, historical audit records remain correct.

## User / role / department / location

```text
User
  ↓
Roles
  ↓
Department
  ↓
Location
```

Location is part of the operational identity context used by audit and approval rules.

## Trial users

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | ADMIN |
| `requester` | `requester123` | REQUESTER |
| `purchasing` | `purchasing123` | PURCHASING |
| `warehouse` | `warehouse123` | WAREHOUSE |
| `finance` | `finance123` | FINANCE |
| `manager` | `manager123` | MANAGER |
| `section` | `section123` | SECTION_APPROVER |

The default approval workflow also includes `SECTION_APPROVER` as a configurable role. The `section` trial user is included so the layered PR and PO approval flow can be tested immediately.

## Database migration

From the backend directory:

```bash
alembic upgrade head
```

The layered approval migration is:

```text
20260720_approval_workflows
```

## Seeding supplier invoices from PO workbooks

Monthly PO workbooks (e.g. `PO MINAS Januari 2026.xlsx`, `PO PEDADA Januari 2026.xlsx`) can be loaded end-to-end with:

```text
WB: workbook → Goods Receipt → Supplier Invoice → Posted Journal
```

Run from the backend directory:

```bash
python3 scripts/seed_po_minas_receiving_invoice.py \
  --workbook "PO MINAS Januari 2026.xlsx" \
  --department-code WAREHOUSE \
  --create-missing-products \
  --create-missing-suppliers \
  --apply
```

Omit `--apply` (or pass `--dry-run`) to preview without writing. One summary GR/invoice/PO is created per detail sheet; receipts are direct (no PO link) and destination is `WAREHOUSE` by default (`--destination-type DIRECT_USE` for direct consumption). Invoice due date defaults to PO date + 30 days (`--invoice-terms-days`).

Idempotency: sheets whose `external_reference` already has a GR are skipped by default (`--skip-existing`), so re-running after a partial commit only fills the missing documents. `--verbose` prints per-sheet detail.

Workbook repair: if any sheet cell holds the Excel epoch (`1900-01-24`), repair the workbook first (load with `openpyxl.load_workbook(..., data_only=True)` so cached formula results are preserved, save to a new file) and run the seed against the repaired copy. Repairing without `data_only=True` wipes cached values (qty/amount become `None`).

## Frontend

```bash
npm install
npm run lint
npm run build
```

## Current architecture direction

The project is intentionally moving toward:

```text
HMM Connect
    ↓
GitHub
    ↓
develop branch
    ↓
Terraform
    ↓
Cloud deployment
```

The current focus is making the ERP comfortable and correct for the company trial before production infrastructure is finalized.

ERP PROJECT RECOVERY

Recovered from the latest known project state.

Backend:
- Supplier master replaced with the 14 suppliers from the supplier PDF.
- Classification/subgroup fixes included.
- Product/classification alignment included.

Frontend:
- Login bypassed temporarily.
- Item Master and frontend fixes included.

Backend start:
  cd backend
  alembic upgrade head
  uvicorn app.main:app --reload

Frontend start:
  cd frontend
  npm install
  npm run dev

## 2026-07-18 Audit Logging

Added the audit log foundation and UI.

- Added `audit_logs` table and Alembic migration `20260718_audit_logs`.
- Added audit records for supplier, product, item classification, PR, PO, goods receipt, role, and user-role actions.
- Added `GET /api/v1/audit-logs`.
- Added the Audit Log page and navigation item.
- Added action and entity filters plus expandable audit details.

## 2026-07-18 Purchase Requisition and Supplier Audit

- PR item responses now include product code, name, and UOM directly from the backend.
- Added PR detail endpoint usage and a PR detail modal in the frontend.
- Supplier editing added with replacement of Excel-style PIC / Unit / Item rows.
- Added supplier update audit records.
- Supplier edit modal preserves the Excel supplier master structure.

## Procurement / accounting controls update (2026-07-20)

The project now includes:

- Many-to-many Purchase Requisition ↔ Purchase Order linkage via `purchase_order_requisitions`.
- PR estimated price is preserved separately from PO unit price.
- Purchase Order expiry dates and receipt tolerance percentages.
- Goods Receipt destination controls: `INVENTORY` or `DIRECT_CONSUMPTION`.
- Receipt cost is always derived from PO unit price and is not client-editable.
- Department master data and user department assignment.
- Warehouse-aware inventory and stock movements.
- Chart of Accounts seed data.
- Account Payable and Account Receipt records.
- Warehouse management page.
- PO create modal and multi-PR selection.
- PR and PO print actions.
- Finance page for COA, AP and account receipts.

Run:

```bash
alembic upgrade head
```

The latest migration is `20260720_procurement_accounting`.


## Trial authentication

The trial user accounts are seeded by `20260720_trial_users`. See `TRIAL_USERS.md`.

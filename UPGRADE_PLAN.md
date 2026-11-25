# Upgrade plan and TODOs

Status: active. Last verified: 2026-11-25.

## Demo/live relationship

The demo app follows the live app at the **application and schema level**:

- One public frontend URL and one deployed API serve both live and demo sessions.
- Login routing is server-side: the exact allowlisted user receives a signed JWT claim `db=demo`; every request session uses that claim.
- `erp_demo` is isolated from `erp_db`. It is **not** a copy of live data.
- `erp_demo` is currently aligned with the live Alembic head (`20261105_pos_guests`) and should stay aligned on every schema release.
- Demo-specific behavior is limited and explicit: isolated data, blocked primary-only bulk journal import, and single-login receiving approval for the demo scope.
- Frontend changes go to `main` and deploy through Vercel. Backend changes go to `backend` and deploy through the existing GitHub Actions Lambda workflow.

## Invariants

1. Keep the same public URL. Do not add a separate demo origin or frontend database selector.
2. Keep the login contract unchanged. No client-supplied `database` field.
3. Keep exact allowlist routing through `DEMO_USERNAMES`; missing or invalid demo config must fail closed.
4. Do not merge `backend` into `main`.
5. Do not touch the dirty backend recovery checkout.
6. Keep demo data changes in `erp_demo`; do not seed demo users into `erp_db`.

## Current baseline

Already verified and deployed:

- Frontend `main`: GL, Journal, Purchasing, Petty Cash, AR/AP workspaces, typed finance contracts, shared list hooks, and export/print scope clarity.
- Backend `backend`: demo DB routing, export job scope, demo fail-closed rules, and demo receiving single-login approval.
- Demo purchasing chain: PO → Goods Receipt → Supplier Invoice → posted Journal.
- `erp_demo`: 109 tables at Alembic head, owned by `demo_app`, with products normalized and master-data reads working.

## Upgrade waves

### Wave 0 — Parity guardrails

- [ ] U-00 Keep a short release note with frontend commit, backend commit, Alembic head, workflow run IDs, and public smoke results.
- [ ] U-01 Before any UI release, confirm the demo token still resolves to `db=demo` and that `/health`, `/auth/me`, products, suppliers, COA, COA tree, warehouses, POs, GRNs, and supplier invoices return 200.
- [ ] U-02 Before any backend schema release, apply migrations to both `erp_db` and `erp_demo`, then re-check the Alembic head in both databases.
- [ ] U-03 Keep bulk journal import fail-closed for demo unless the worker is made database-aware first.

### Wave 1 — Shared UI system completion

- [x] U-10 Convert remaining ad-hoc POS screens (`PosOperationsPage`, `PosSalesPage`, `PosSettingsPage`) to the shared `DataWorkspace`, `PageHeader`, `WorkspaceFilters`, form shell, and `SearchableSelect` patterns.
- [x] U-11 Add typed API contracts and list/detail hooks for POS operations so those screens stop relying on untyped `any` responses.
- [ ] U-12 Standardize empty, loading, and error states in Admin pages: Users, Roles, Active Sessions, Approval Configuration, Audit Log, and Traceability.
- [ ] U-13 Standardize Bank Reconciliation list/detail and Finance setup pages (Report Setup, Statistics, Posting Rules) with explicit filter context and action states.

### Wave 2 — Operational input flows

- [x] U-20 Smoke test and polish Stock Opname create/detail, Inventory Returns, Store Request, and Put Away using the demo token. Put Away has no deployed backend endpoint, so its route now fails closed with an explicit message instead of calling a missing API.
- [x] U-21 Verify every upgraded form has usable demo option data: business units, locations, departments, warehouses, products, suppliers, COA, tax, UOM, and categories. Tax and UOM come from source product/receipt rows rather than standalone option endpoints.
- [x] U-22 Add regression scripts to `scripts/` for each newly standardized workflow, then include them in the relevant `package.json` test script (`scripts/test-operational-flows.cjs` is registered under `test:store-request`, which is part of `npm test` and Frontend CI).
- [ ] U-23 Confirm print/export buttons state their source, scope, and whether they print live filtered data or an authenticated report artifact.

### Wave 3 — Demo data readiness

- [ ] U-30 Seed only minimal demo records needed for POS, inventory, and finance setup checks; keep them clearly separated from production data.
- [ ] U-31 Re-run full demo purchasing E2E after any backend deploy: PO → GRN approvals → GRN posting → supplier invoice → journal posting.
- [ ] U-32 Document any feature intentionally unavailable to demo, with the exact user-facing message.
- [ ] U-33 Verify no upgraded screen exposes primary-only data or actions to the demo session.

### Wave 4 — Release

- [ ] U-40 Frontend checks: `npm run lint`, `npm run build`, `npm run test:finance`, `npm run test:workspace`, `npm run test:inventory-print`, `npm run test:store-request`, `npm run test:pos-operations`.
- [ ] U-41 Backend checks: full `pytest`, `compileall`, `git diff --check`, and migration-chain validation.
- [ ] U-42 Push frontend to `origin/main` only; push backend to `origin/backend` only when backend code changed.
- [ ] U-43 Watch the GitHub Actions deploy to completion, including `Verify deployed function` and `Smoke test health endpoint`.
- [ ] U-44 Run public URL smoke checks after deploy and record results in the release note.

## Recommended next task

Start with **U-12/U-13: Admin and Finance setup screens**, because the remaining ad-hoc list/detail screens still lack shared filter context and explicit loading/empty/error states. POS operations, sales and settings use the shared workspace shell, typed contracts, hooks and `scripts/test-pos-contracts.cjs`; the four operational flows now use the same shell with `scripts/test-operational-flows.cjs`.

## Definition of done for a wave

A wave is done only when:

1. Code is committed to the correct production branch.
2. Required migrations are applied to both databases before dependent code is used.
3. Automated checks pass.
4. The demo token can open and complete the affected workflow with demo data.
5. The public URL smoke checks still pass.
6. Documentation is updated for changed workflow, permission, accounting rule, report, or deployment behavior.

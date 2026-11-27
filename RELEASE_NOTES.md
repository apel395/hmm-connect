# Release notes

Last verified: 2026-11-27.

## Deployed revisions

- Frontend `main`: `f80d11ae` (fiscal report workspaces and typed contracts), preceded by `af69ec7f` (AR/AP reporting and AP aging print states), `02f3a040` (release note), `8ab16eb6` (Trial Balance, General Ledger and report print states), `f099bddd` (Bank Reconciliation, Balance Sheet/P&L shared workspace, release note), `a8e342d5` (Admin/Finance setup), `96927b64` (Inventory/Stock Movement Summary), `a00a0466` (operational flows), `5f3fd247` (POS operations), `5050e4f1` (print/export scope clarity).
- Backend `backend`: `7ea57c1f` (demo single-login receiving approval), preceded by `b27e65f3` (allowlisted demo DB routing). No backend change in the latest frontend waves.
- Alembic head in both `erp_db` and `erp_demo`: `20261105_pos_guests`.
- GitHub Actions Lambda deployments: runs `45542976476`, `45548502019`. Lambda `hmm-connect-api` Active/Successful; Function URL unchanged.
- EC2 export worker restarted with `DEMO_DATABASE_URL` and `DEMO_USERNAMES=demo`.

## Demo/live behavior

- One public URL serves both live and demo sessions. Demo login `demo / 12345` mints a JWT with `db=demo`; no client-supplied `database` field.
- `erp_demo` is isolated from `erp_db` (109 tables, owned by `demo_app`, 1,529 products at last check).
- Bulk journal import remains blocked for demo with the exact message: `503 Bulk journal import is not available in the demo database`.
- The demo-only receiving exception permits one login to complete both approval steps; production keeps the two-person rule.
- Put Away has no deployed backend endpoint; the route shows an explicit unavailable message instead of calling a missing API.

## Verification performed

- Backend: full `pytest` (`1058 passed, 21 skipped`), `compileall`, `git diff --check`, migration-chain validation.
- Frontend: `npm run lint`, `npm run typecheck`, `npm run build`, `npm test` (`test:finance`, `test:workspace`, `test:pos-operations`, `test:inventory-print`, `test:inventory-module`, `test:admin-setup`, `test:report-workspace`, `test:store-request`) — all passing. `test:report-workspace` now covers fiscal COA mapping, reconciliation, Lampiran 1D and SPT 1771, including runtime fiscal API contract checks.
- Demo purchasing E2E: PO → GRN approvals → GRN posting → supplier invoice → posted journal.
- Public URL smoke: `/health` 200, demo login 200 with `db=demo`, `/api/v1/auth/me` 200. Operational-flow smoke: stock opnames, inventory returns, return sources, store requests and period report all 200; `/put-away` 404 as documented.

## Demo workflow records

Seeded through the public API with the demo token, all in `erp_demo` and all still in `DRAFT`:

- `SO-202611-0001` (Stock Opname, id 1, 3 snapshotted inventory lines)
- `SR-202611-0001` (Store Request, id 1)
- `RTN-202611-0001` (Inventory Return, id 1, sourced from existing GRN `GR-20261125-00002`)

Read-back with the demo token returns 200 and `total_items=1` for all three lists. The demo token receives `503 Bulk journal import is not available in the demo database` for `/api/v1/journal-imports/template`, confirming the primary-only guard.

## Local-only test constraints

- `test-data-workspaces.mjs` is not part of `npm test` or Frontend CI. Scoped Trial Balance and General Ledger views pass locally with synthetic fixtures and preinstalled browser/runtime libraries; the full script still stops at the pre-existing journal-view fixture issue.
- `test-report-statistics.mjs` passed locally using preinstalled browser/runtime libraries; it is not part of `npm test` or Frontend CI.

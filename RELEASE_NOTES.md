# Release notes

Last verified: 2026-11-27.

## Deployed revisions

- Frontend `main`: `26d99552` (docs: closed-loop demo finance data), preceded by `f80d11ae` (fiscal report workspaces and typed contracts), `af69ec7f` (AR/AP reporting and AP aging print states), `02f3a040` (release note), `8ab16eb6` (Trial Balance, General Ledger and report print states), `f099bddd` (Bank Reconciliation, Balance Sheet/P&L shared workspace, release note), `a8e342d5` (Admin/Finance setup), `96927b64` (Inventory/Stock Movement Summary), `a00a0466` (operational flows), `5f3fd247` (POS operations), `5050e4f1` (print/export scope clarity).
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
- The Budget vs Actual page calls `/reports/budget-vs-actual`, which the deployed backend does not expose (404). Budget figures are verified through `/budgets` and the `/dashboard/finance` budget panel until that endpoint is available.

## Verification performed

- Backend: full `pytest` (`1058 passed, 21 skipped`), `compileall`, `git diff --check`, migration-chain validation.
- Frontend: `npm run lint`, `npm run typecheck`, `npm run build`, `npm test` (`test:finance`, `test:workspace`, `test:pos-operations`, `test:inventory-print`, `test:inventory-module`, `test:admin-setup`, `test:report-workspace`, `test:store-request`) — all passing. `test:report-workspace` now covers fiscal COA mapping, reconciliation, Lampiran 1D and SPT 1771, including runtime fiscal API contract checks.
- Demo purchasing E2E: PO → GRN approvals → GRN posting → supplier invoice → posted journal.
- Public URL smoke: `/health` 200, demo login 200 with `db=demo`, `/api/v1/auth/me` 200. Operational-flow smoke: stock opnames, inventory returns, return sources, store requests and period report all 200; `/put-away` 404 as documented. Finance-flow smoke: AR summary/detail/aging, AP summary, fiscal reconciliation/balance sheet, SPT report/profile/credits, budgets, statistics, bank reconciliations and trial balance all 200.

## Demo workflow records

Seeded through the public API with the demo token, all in `erp_demo`. Operational drafts remain available for completion:

- `SO-202611-0001` (Stock Opname, id 1, 3 snapshotted inventory lines)
- `SR-202611-0001` (Store Request, id 1)
- `RTN-202611-0001` (Inventory Return, id 1, sourced from existing GRN `GR-20261125-00002`)

Closed-loop finance data added in the latest demo pass:

- AP: approved payment voucher `PV-20261127-00001`, partial payment `PAY-202611-0001`, and posted journal `PAY-202611-0005`; AP summary now shows 1 paid, 1 partially paid, and `175,000` outstanding.
- AR: two posted POS invoices for `Demo AR Customer` (`INV-20261127-00001` 150,000 and `INV-20261127-00002` 300,000), plus posted customer receipt `CP-202611-0001` (100,000); AR summary now shows 450,000 gross, 100,000 received, 350,000 outstanding, and 50,000 overdue.
- Fiscal: 2026 profile `PT HMM Connect Demo`, two tax credits (60,000 PPh 25 and 30,000 PPh 23), two posted P&L journals, and fiscal remapping for FINAL interest income and NON_DEDUCTIBLE entertainment; reconciliation shows 2,000,000 commercial profit, 250,000 correction, 2,250,000 fiscal taxable income, 247,500 PPh payable, and no unmapped commercial accounts.
- New COA `400-110-100` (Catering Service Revenue) enables POS/AR seeding for the Project Catering business unit and is mapped to fiscal account `4021`.
- Budgets/statistics: COA `900` hierarchy with six leaf metrics and 18 monthly actual/budget rows for Sep–Nov 2026; locked budget `BUD-202611-0001` (4,250,000) for comparison and draft `BUD-202611-0002` (1,050,000) left for the submit/approve workflow. The finance dashboard now compares 2,450,000 November budget against 2,550,000 posted actual expense.
- Bank reconciliation: `BR-202611-0001` for Bank Mandiri `100-110-102` (Nov 2026) is `COMPLETED` with four CSV statement lines auto-matched to posted journal lines and zero difference.

Read-back with the demo token returns 200 for the operational lists and all AR/AP/fiscal/budget/statistics/bank-reconciliation reporting endpoints. Trial balance remains balanced at 9,650,000 debit and credit across 15 accounts with no abnormal balances. The demo token receives `503 Bulk journal import is not available in the demo database` for `/api/v1/journal-imports/template`, confirming the primary-only guard.

The SPT report keeps company identity in its top-level `profile` object and the UI reads identity from `/spt-1771/profile`; `section_i_a` intentionally contains only financial figures.

## Local-only test constraints

- `test-data-workspaces.mjs` is not part of `npm test` or Frontend CI. Scoped Trial Balance and General Ledger views pass locally with synthetic fixtures and preinstalled browser/runtime libraries; the full script still stops at the pre-existing journal-view fixture issue.
- `test-report-statistics.mjs` passed locally using preinstalled browser/runtime libraries; it is not part of `npm test` or Frontend CI.

# Hotel POS operations — Phase 2

## Review and release

Stacked on Phase 1 PR #474 (`feature/hotel-pos-outlets-1024-backend`). The UI is stacked on #475. Neither phase is released by this branch. Merge/deployment requires owner approval. The API is Lambda (`backend`); the UI is Vercel (`main`). PostgreSQL schema changes run on EC2 **before** releasing code that reads the new columns. No production data was queried or changed while developing this feature.

Migration `20261024_pos_operations`, after `20261022_pos_ar_invoices`, adds outlet policies, tables, cashier shifts, nullable order links, request keys and partial unique indexes. It does not backfill or rewrite historical sales, journals, AR, inventory or openings.

After release approval, apply in an isolated checkout containing the approved code and `.env` link:

```bash
/opt/hmm-connect/.venv/bin/alembic upgrade 20261024_pos_operations
/opt/hmm-connect/.venv/bin/python scripts/check_pos_operations_1024.py
```

The checker is read-only. Do not run a schema downgrade after live orders reference these tables.

## Configuration and cashier workflow

Reuse Hotel Location → parent Department → child Outlet. Each policy and table belongs to an exact location/outlet pair. `finance.manage` configures order mode and tables; `pos.sell` opens orders and shifts; `pos.view` reads permitted outlet operations and reports. Server organization access applies to every endpoint. There is no new warehouse, inventory consumption, recipe or BOM path.

1. In **Point of Sales → Outlet Operations → Setup**, choose the Hotel location and child outlet. Choose TABLE (Restaurant: table mandatory), COUNTER (Café: table optional) or EVENT (Banquet: event name required, no table). Names do not decide behavior. A manager cannot change mode while shifts or POS drafts are open.
2. Create tables in **Tables**. Names are unique within the outlet. Edit/deactivate/reactivate are supported; occupied tables cannot change. Tables cannot be moved between outlets after creation.
3. In **Shifts**, the cashier opens their own shift and enters opening float. This is cash counted for operations, not an opening-balance record or a financial journal. One open shift per cashier/outlet/location is enforced by the database.
4. **Open order** opens the existing Register. Select the table/event and menu, then Save Draft to reserve the table. Unsaved browser input does not reserve a table. Another saved DRAFT cannot use that table. Counter/event orders do not reserve a table. Prices/quantities/customer features reuse the existing POS flow.
5. Continue an order from **Orders** or Sales → Continue / settle. Register loads the saved order and updates its ID; it can add items or change quantities. Location, outlet, shift and table remain pinned. Unsaved inputs are recovered per order and per signed-in user. Clearing/leaving local input does not void a saved order; void the draft explicitly from Sales when appropriate.
6. Settle using cash/card/bank. Existing POS tax/service-charge/GL logic posts the source once; source row locks reject second posting. Cash tender must cover the complete total. AR customer invoices remain unpaid bills and do not count as cashier receipts; their existing separate receipt/allocation behavior is unchanged.
7. Complete or explicitly void every open order before closing the shift. Count cash and enter a reason for any difference. Expected cash = opening float + full CASH sale totals (net of change). Card/bank sales are separate. A difference remains visible and never generates an automatic balancing journal. Closed shifts cannot be reopened or receive new sales in this phase.
8. Print the individual shift report with cashier name, timestamps, payment totals, PBJT, service charge, expected/counted cash, difference/reason and source transaction list. Outlet reports support date range, cashier, method breakdown and daily summaries. Only POSTED POS documents with posted journals feed financial sales totals; customer invoices are not presented as collected money.

## Existing data and exclusions

Existing posted records remain unmodified. Newly created Hotel outlet POS orders require configured mode and an open cashier shift; legacy unsessioned Hotel drafts cannot settle into a shift silently. Void and re-enter those **unposted** orders through the controlled Register. Catering and AR invoice workflows remain independent. A table is released when its saved order is posted or voided.

Phase 2 does not implement split tender, tips, cash paid-outs, refunds, shift handover/reopening, kitchen tickets, inventory/BOM consumption or automatic daily GL closing. Such operations must not be simulated with changed shift totals. Reports show the real evidence available.

## Concurrency and validation

- Order create locks the cashier shift before replay checking and table reservation. Stable request key retries return the existing order; changed details are refused.
- Partial unique indexes prevent duplicate active table orders and duplicate open cashier shifts, even if an API caller bypasses UI checks.
- Editing/metadata/settlement lock the source order, then the shift. Closing locks the shift and refuses any remaining draft. An order cannot change type/table via the metadata endpoint.
- Table/policy management locks the outlet Department with PostgreSQL NO KEY UPDATE semantics to serialize master edits without blocking foreign-key key-share locks.
- Existing transactional document numbering and GL posting remain in use. There are no balance repairs or journal rewrites.

Regression coverage includes tables/modes, active order uniqueness, retry identity, editing, void, settlement once, exact cash, shift close/variance, access, daily/cashier/method/PBJT/service totals and AR/inventory invariants. Local business-flow tests use SQLite and enforce partial indexes; production row-lock behavior is PostgreSQL-specific and is not claimed as a live-production concurrency test.

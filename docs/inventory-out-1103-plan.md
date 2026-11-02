# Inventory patch preparation — 3 November 2026

Status: preparation only; no inventory behavior, database schema or production data changed.
Backend base: 49e0e75fa9abc28626fb723368e4fa6f6780b7b8.
Frontend base: 26dae84879d26adeb8fe66399ddd7ff3bbdc18d2.
User confirmed linen cleanup completed; no repeat linen data conversion is planned.

## Scope and delivery order

1. INV-01 / INV-02 (#493, #494): distinguish operational stock consumption from supplier returns. Reuse Store Request / Store Issue for operational use; do not build another parallel consumption journal.
2. INV-03 (#495): supplier return linked to original receiving lines, with AP treatment separated from receipt correction. Do not infer supplier credit or reduce AP merely because goods leave the warehouse.
3. INV-04 (#496): display unit reference cost and extended estimated value in Store Request create/detail/print. Proposed source: current warehouse average cost, read-only reference. Actual posted issue cost remains the locked warehouse cost at posting.
4. INV-05 (#497): improve report traceability for receiving, operational issues, returns and adjustments, then reconcile opening + incoming - outgoing = closing quantity/value for the same scope/date basis.

## Findings in existing code

- app/services/store_request_service.py already creates partial issues, locks the issue/request/inventory, checks available quantities and positive average cost, and posts debit to Item Master cogs_account_id and credit to inventory_account_id. DirectCoaService validates the debit account as an active posting EXPENSE. Preserve this valid behavior; food/beverage costs must not be indiscriminately moved to an overhead account.
- Operational movement references STORE_REQUEST and carries journal_entry_id plus inventory/offset account IDs.
- app/services/inventory_posting.py validates positive balanced journals and rejects an existing GL source reference.
- app/api/v1/store_requests.py detail currently supplies quantities and available_stock, but no reference price/value.
- GoodsReceiptService.return_receipt returns the whole posted receipt, requires its posted journal to be unposted first, and rejects confirmed or modified supplier invoices. Untouched automatic draft invoices can be voided with the return. This is not an invoiced partial supplier-credit workflow.
- app/api/v1/inventory.py _stock_source classifies Store Request as USAGE, but GOODS_RECEIPT_RETURN currently falls through to OTHER. Return reporting must classify existing source references explicitly.
- No separate supplier return / supplier credit-note model was found in the inspected inventory/AP paths. Do not add an AP debit through the existing full-receipt return by bypassing its protections.

## Proposed transaction behavior

### Operational
Approved Store Request -> issue draft -> post.
Journal: debit mapped expense/COGS; credit inventory.
Scope: authorized warehouse, location, business unit and consuming department.
Reuse existing stock and journal transaction. Repeated posting must create no second movement or journal.

### Supplier return
Select original supplier/receiving, eligible warehouse receipt lines and returned quantities. Require a reason and source traceability.
A return of goods and a supplier financial credit are distinct events:
- Unconfirmed receiving correction/replacement: reuse audited source correction/return flow where eligible, retaining existing dependencies.
- Confirmed invoice: require an explicit supplier-credit/AP adjustment design before implementing financial settlement. Paid invoices may result in supplier credit rather than arbitrary negative AP or deletion of payment allocations.
- Partial returns, credit amount/tax, outstanding versus paid invoices, and replacement receipts need explicit handling. No free-form account choice should silently decide the accounting route.
The warehouse carrying value and supplier credit value may differ; never erase such differences with an automatic balancing entry. Confirm the policy before writing this journal.

## Implementation map

Backend:
- store_requests API serializers: reference price/value, preserving existing response fields.
- store_request_service / inventory_posting: reuse operational posting; add regression coverage if source classification is added.
- inventory API stock-source classifier: explicit RETURN classification; preserve IN/OUT signs.
- dedicated supplier-return schema/model/service only if approved invoice-credit design requires it; keep it separate from stock adjustments and stock opname.
- additive migration only for genuinely new persistent return/credit records or posting snapshots. Do not migrate/relabel historical journals or rewrite source quantities.

Frontend:
- Store Request create/detail/print/types: compact reference-price/value columns.
- Movement/report pages: operational/return labels and compatible filters.
- Supplier return form: original document selection and remaining returnable quantities, with clear pending credit/correction route. No invented automatic AP settlement.

## Baseline verification

Local backend baseline: 16 passed, 5 existing warnings:
- tests/test_store_request_flow.py
- tests/test_inventory_delivery_1015.py
- tests/test_inventory_empty_stock.py
- tests/test_inventory_date_account_totals.py

Before release test:
- Partial/full operational issues and exactly-once journal/movement.
- Concurrent/repeated posting and rollback after a later-line error.
- Out-of-scope warehouse, insufficient stock, inactive/wrong-type account.
- Closed-period rejection and unchanged opening balances.
- Current reference price changes do not rewrite posted issue cost or historical GL.
- Partial/repeated supplier returns bounded by eligible source quantities and current stock.
- Confirmed/paid supplier invoices preserve payments and allocation history.
- No duplicate AP reduction; tax/credit amounts and inventory valuation reconcile explicitly.
- Stock source filters, running balance and full export totals agree across pagination.
- Frontend production build and relevant inventory/Store Request tests.

## Release boundary

Feature branches only. Preparation does not authorize a merge, deployment, data cleanup or posting a test transaction in production.

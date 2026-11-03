# Partial supplier returns and period stock report

## Release and migration

Backend and frontend are reviewed on separate feature branches. Do not merge/deploy until approved.
Run `alembic upgrade 20261103_inventory_returns` from the reviewed backend checkout on EC2 before releasing the new API.
This creates return headers/lines/replacement links and adds optional event-value snapshots. Receiving and stock-movement unit costs support four decimal places for warehouse carrying values. Existing event values remain unchanged; the optional snapshot stays null on legacy records. No opening balances, stock quantities, posted journals, tax records or payments are seeded or rewritten.
Downgrade refuses to discard return history or truncate four-decimal costs.

## Accounts and permissions

Finance must choose existing active posting accounts. The app never invents COA mappings.

| Purpose | Required account |
| --- | --- |
| Goods sent back awaiting replacement/credit | Non-cash debit-balance asset clearing account, distinct from source inventory |
| Supplier credit exceeding invoice outstanding | Separate non-cash debit-balance supplier-credit asset account |
| Difference between supplier credit base and returned carrying cost | Explicit Finance-selected debit-balance expense/COGS account |
| Supplier credit PPN reversal | Existing `INPUT_VAT_ACCOUNT` setting; amount entered from supplier document |

`receiving.return` creates, posts or voids draft returns. `receiving.post` registers replacement goods. `finance.manage` settles the supplier credit. Warehouse/location access is checked on the original Receiving and warehouse, independently of frontend controls. The original source needs valid supplier, unit, department and location.

## Operational stock out

Continue using approved Store Request -> Store Issue. Its existing expense/COGS debit and inventory credit remain unchanged. No second consumption journal is created. Stock Movement labels this source as Operational / Usage.

## Partial supplier return

1. Open Inventory -> Supplier Returns -> Create Return.
2. Search/select the original posted purchasing Receiving. Select distinct warehouse lines and quantities.
3. Choose Replacement or Reduce payable / supplier credit, date, reason and the return-clearing account.
4. Save Draft. Review and Post Return. Void an incorrect draft and recreate it before posting.

Create retries reuse a unique request key; changed payloads cannot reuse that key. Replacement deliveries cannot reuse a delivery-note reference on the same return.

Posting checks original received quantities less prior posted returns, current warehouse stock, positive carrying cost and open accounting period. All lines are validated before stock changes. Receipt, return and sorted inventory locks serialize posting; repeated posting is rejected. Quantity and costs are stored with document/journal/movement links.

Journal: debit return-clearing asset; credit the original inventory account at current warehouse carrying cost. Supplier AP is not reduced merely because goods leave the warehouse. Original Receiving/invoice quantities and original journals are preserved.

## Replacement goods

Open the posted replacement-purpose return. Enter actual Receiving date, delivery note and replacement quantities. Partial deliveries are allowed up to the remaining returned quantity.

The app creates a posted linked Receiving with source `SUPPLIER_REPLACEMENT`, stock IN and a balanced inventory/clearing journal. It creates no additional supplier invoice or PPN charge. Replacement receipts are excluded from new invoice source selection, purchasing purchase values and last/average purchase-reference prices.

Each replacement allocates the immutable return-line currency value proportionally. The final delivery takes the remaining cents. Unit carrying-cost precision remains four decimals; event currency values are snapshotted separately so split deliveries do not introduce gain/loss balancing entries. Weighted warehouse cost follows the physical quantities and carrying costs.

## Supplier credit

Finance selects the accounted invoice linked to the source Receiving, credit date/reference, credit base and documented PPN. Original invoice-line links must be unique. Credit base and tax are bounded by returned source invoice lines and previous credits. The current implementation supports IDR.

The invoice is locked while credit is settled. Complete/void pending approved payments or draft supplier adjustments first. A concurrently locked invoice returns a retryable conflict rather than waiting in an opposite-order accounting lock.

- Apply credit to remaining invoice outstanding. Create a posted linked Supplier Credit Note for that AP-applied amount.
- Preserve all payment amounts and allocations.
- If the credit exceeds outstanding, record the excess as a separate supplier-credit asset. It is displayed on the return; applying/refunding that balance in a subsequent transaction is a separate Finance workflow.
- Reverse input VAT only for the explicit supplier-document amount.
- If supplier credit base differs from stock carrying cost, require an explicit variance account. The app does not invent an automatic balancing adjustment.

Credit settlement is once per return. Settled credit/source invoice and source Receiving are protected against reopening, cost changes or unposting that would detach this accounting. Posted returns/replacements/credit journals have no generic unpost handler; preserve history and request a reviewed source reversal rather than editing a posted event.

## Period report, print and Excel

Inventory -> Stock Movement Summary provides From/To, unit, accessible warehouse and item filters. Switch Quantity / Value. It distinguishes purchasing Receiving, operational use, supplier returns, replacement goods, adjustments and other movements.

The report rolls the current stock snapshot back using later recorded movements. Opening + incoming - outgoing = closing on this snapshot/movement basis. It does not change or substitute the manually entered accounting opening balance and does not assert that stock and GL are reconciled merely because this arithmetic matches. Missing inventory snapshots are marked for review. Quantity totals are separated by UOM.

Click an item code to drill into its warehouse stock movements. Returns link to the return document and original Receiving; replacements link to their Receiving. Print and Excel collect all filtered pages and reject incomplete/changing pagination. Excel includes a Summary sheet and quantity/value details.

## Validation

Regression coverage includes draft versus posted changes, duplicate/over-return prevention, later-line failure, four-decimal costs, partial replacements with remaining-cent allocation, unpaid/part-paid/paid invoice credits, preserved paid amounts, explicit variance, PPN bounds, closed periods, permissions, original invoice/source guards, source filters and period totals across pagination. PostgreSQL tests exercise concurrent source returns and migration against a populated isolated schema, never production.

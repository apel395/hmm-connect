# Historical Project Catering 2026 — AR Invoice Excel import

## Source and decision

Input: `REKAP INVOICE PENDAPATAN PROJECT CTRG 2026.xlsx`, 1 worksheet,
12 monthly DPP/PB-1/TOTAL triplets and right-side A/R, receipt and aging
columns. The source has 229 invoice rows for Rumin (119), Duri (70),
Lipet (37) and DOBS (3). It is an **invoice/receipt reconciliation
register**, not a full sales service-line export.

Source sums (before source-specific rounding):
- A/R: Rp131,392,801,291.28
- Cash receipt column: Rp49,741,675,823.20
- Source aging: Rp81,651,125,468.08

The 62 rows with a receipt have remark-based withholding; **the remaining
aging column includes potential tax withholding**, so it must not be blindly
treated as collectible cash debt.

## Operational organization dimensions

- Business Unit: Project Catering, `002`.
- Department: Operasional, `01`.
- Locations: Rumin `005`, Duri `006`, Lipet `010`, DOBS `014`.
- Verify each LocationDepartment association and location access against
  live masters. Hotel is a different BU `001` and uses Hotel location
  `009`; never infer hotel location from the city's Pekanbaru label.

## Source exceptions (Excel row numbers)

| Rows | Problem | Gate |
| --- | --- | --- |
| 105–106 | Repeated invoice `MMH-RBI/173/V/2026` | Resolve invoice identity before registration |
| 209 | Missing invoice date | Source document required |
| 68, 76 | DPP + PB-1 differs from stated total | Verify signed invoice and adjustments |
| 14, 181 | Revenue month differs from invoice issue date | Preserve both; reconcile accounting period |
| 205, 250 | More than two monetary decimal places | Confirm per-invoice rounding |
| 174, 179 | Receipt balance differs from PPh23/PB1 estimate | Bank, tax and source receipt evidence |

67 external invoice identifiers end in `2025` although their issue dates
are 2026. Flag these for source review rather than silently rewriting or
rejecting the legal identifier.

## Safe implementation sequence

1. Upload original XLSX using `POST /api/v1/ar-imports/stage`; this
   stores only ImportBatch and ImportRow. A repeated same-file upload by
   the same user returns the existing staged batch. There is **no**
   `/commit`/posting action in this first phase.
2. Preview totals, normalized month, original number, source row,
   duplicates, active master mappings, issues and reconciliations using
   `GET /ar-imports/{id}/summary` and `/rows`.
3. **Confirmed by the business owner on 20 Nov 2026:** all 229 Project Catering
   invoice rows belong to the active customer **PHR**. Preparation looks up the
   unique active PHR master (not by assumed numerical customer ID), and stores
   the mapping only in the normalized staging rows. No other Catering import
   inherits this mapping by default. Finance still supplies approved contractual
   payment terms and AR/revenue/PB-1 liability account IDs.
4. Reconcile each source invoice with existing AR, sales transaction,
   journal and GL evidence. Existing monthly/bulk journals may contain
   booked revenue or AR balances without carrying an external invoice
   number. Finance must reconcile the period/amount/location, not merely
   check absence of matching string.
5. Register approved historical invoices through a separately reviewed
   `AccountReceivable` subledger catch-up flow after confirming **which
   GL already exists**. `source_sale_id` is nullable, so there is no
   need to invent POS line items. Preserve external invoice number
   (max 50 chars) and link ImportRow.entity_id to the new AR id.
   Do **not** post a second revenue journal if original GL is present.
6. Historical **cash** receipt must be matched to bank statement and
   existing payments/journals before registering CustomerPayment. The
   received cash column is *net* bank receipt, not automatically full
   settlement. Evidence-supported PPh23, PB-1 withholding and residual
   credit should be classified by accounting policy using the correct
   posting accounts; never create cash for non-cash deductions.
7. Require approval by Finance before any status becomes active in AR
   aging; reject duplicates atomically and log audit evidence. The
   import must support partial success with actionable corrections.

## Why not rebuild every POS invoice?

The XLSX lacks service line descriptions, quantities, contractual due
dates, legal customer identifiers, and approved tax configuration. The
current sales transaction posting computes tax and revenue/COGS based on
actual product lines. Inventing one synthetic POS product or fixed rates
would risk different invoices, double revenue/GL and erroneous tax.
Source AR invoice printing for migrated subledger rows may need an
approved separate invoice-document snapshot (the print service supports
a legacy AR row with `source_sale_id=None`, but print readiness remains
false until the document breakdown is supplied).

## Permanent accounting safeguards

- Use Decimal throughout; do not round source totals silently.
- No historical payments should be reposted from the source cash column
  without bank account, payment date, reference and GL reconciliation.
- No inline automatic auto-post or auto-customer creation from location.
- No bypass of closed fiscal-period checks and journal governance.
- Idempotency by source file hash, external invoice identity and
  AccountReceivable unique invoice number; never overwrite existing AR.
- No new VM, SSM trigger, queue broker, or EC2 worker is needed for
  this small XLSX; staging is done in the existing API. Do not treat
  staging as completion of historic AR activation.

## Pending business data

Required to proceed with approved AR activation:
- **Customer mapped:** all 229 rows to PHR per business-owner confirmation.
- Documented due date or signed payment terms per customer/invoice.
- Revenue/AR/PB-1/withholding accounts and evidence of prior journal
  posting or opening-balance recognition.
- Bank statement and PPh23 withholding certificate/reference for the
  62 receipts, including exceptions in rows 174 and 179.

The work is intentionally not blocked at the XLSX upload stage when
these external documents are missing; only accounting activation is held.


## Finance preparation (phase 2, no accounting writes)

The Accounts Receivable > **Stage AR Excel** dialog has a **PHR Invoice
Preparation** form. Use \`GET /api/v1/ar-imports/options\` to fetch the uniquely
matched active PHR customer and eligible chart-of-account choices. Use
\`POST /api/v1/ar-imports/{batch_id}/prepare\` with:

- \`customer_id\` matching the unique active PHR record
- \`payment_terms_days\` (0–365), **verified against the source contract**
- \`ar_account_id\` (active 100-200 asset/debit posting COA)
- \`revenue_account_id\` (active Project Catering operating revenue COA)
- \`pb1_liability_account_id\` (active liability/credit posting COA, must
  specifically be confirmed as PB-1 by Finance)
- \`terms_confirmed: true\` and \`accounts_confirmed: true\`

The API recomputes the due date from the invoice date without changing the
source invoice date; it never chooses payment terms silently. It re-checks
customer uniqueness, Catering BU/dept/location, account classes, exact monetary
balance, source duplicate numbers, and existing AR/Sales/Journal references.
Rows with source exceptions stay \`ERROR\` rather than being auto-corrected.
Other rows become \`READY\` **in staging only**. See
\`GET /api/v1/ar-imports/{batch_id}/journal-preview\` for the balanced
**proposed** debit AR, credit Project Catering revenue, credit PB-1 liability
entries. Staging rows retain original source values in \`raw_data_json\`
and mapped review values in \`normalized_data_json\`. Re-running preparation
only updates the staging mappings and audit records; it never registers a
real AccountReceivable, creates a CustomerPayment, or posts Journal/GL.

This phase deliberately **does not implement /commit or accounting activation**.
When implementing accounting activation, a separate approved design must
avoid inadvertent live AR aging overstatement before reconciling the 62
historical customer receipts and PPh23/PB-1 withholdings.

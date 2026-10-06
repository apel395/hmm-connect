# RESIPING receiving and supplier invoice preparation

Run this after item classification. This script never creates, edits or posts
any master/document/stock/journal/opening record. It has no `--apply` option.

It reads the INVOICES and ITEM_ENTRY sheets, including the added Discount and
Tax columns. Template IDs/date continuation are interpreted explicitly; macros,
general formulas and cached formula totals are never executed or trusted.
Amounts are recomputed with Decimal. Blank tax is unknown; it is not Non PPN.
An explicit zero invoice-header Tax confirms zero tax on that invoice's rows;
a positive invoice-header tax is not silently distributed to lines.

Pre-2026 receiving is excluded before validation. A mixed-year invoice requires
an explicit split; the invoice amount is never automatically reduced by excluded
history. Per the historical-import rule, ranges and lists use the latest date
(e.g. `2-14 JAN 26` → `2026-01-14`, `14FEB&1MARET 26` → `2026-03-01`).
The original date text remains in the report. An explicit year is still required;
missing years and invalid dates remain unresolved. This applies to invoice and
receiving dates only in this import preparation script.
Actual Excel date values remain exactly as stored, even if their display may
have resulted from day/month input confusion. Dates after the invoice date are
flagged. Sequential template invoice numbers need real-document confirmation.

```bash
cd /opt/hmm-connect
git pull --ff-only origin backend
.venv/bin/python scripts/prepare_resiping_transactions.py \
  --file /tmp/resiping-seed-20261006.xlsm \
  --db-check \
  --output /tmp/resiping-transaction-check.json \
  --xlsx /tmp/resiping-transaction-check.xlsx
```

For a freshly edited public workbook replace `--file ...` with
`--drive-id 1gmy6cY8Vccuj78Rj5tNv2EuNtwdCqzqy`. The report includes its SHA256.
A fresh file must be rechecked; earlier totals/classifications do not prove the
new workbook is ready.

The DB check uses a read-only transaction. It matches active BUY names exactly,
never silently substitutes SELL records or aliases, checks purchase units,
classification/COA/tax-review flags and accounting period/backdate settings.
It lists supplier and location IDs, department/warehouse candidates, and possible
existing invoices/receipts. Candidates are evidence for review, not proof that
all documents on a supplier/date are duplicates. Organization and destination
choices must be confirmed before a transaction import is built.

Outputs:

- JSON: full source rows, exact exclusions, arithmetic and database findings.
- XLSX: Invoices, Receiving, Excluded 2025 and Unlinked sheets. Source text is
  written as text, so Excel does not execute formula-like names/numbers.
- Terminal: counts only; no hundreds of item rows to copy.

`seed_ready` remains false: this is preparation, and no apply/post path exists.
Resolve source date/number/tax findings and mapping choices before document
seeding. This report deliberately does not create balancing/rounding entries.

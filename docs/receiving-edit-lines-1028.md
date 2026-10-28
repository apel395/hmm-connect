# Receiving edit lines — 2026-10-28

- Authorized users retain an **Edit Receiving** action after posting or invoice creation. The action opens the draft form only when the server permits editing; otherwise it explains the posting/approval restriction, links to the invoice when available, and offers the existing Correct Cost action when authorized.
- The restriction follows the receiving POSTED status, not simply invoice existence. This release does not introduce full editing of posted receipts. Price-only corrections use Correct Cost. Replacing/removing posted items requires resolving downstream invoices, unposting the source journal when posted, returning the receipt and creating a corrected report using existing workflows. Confirmed invoice, stock and accounting dependencies remain enforced by those actions.
- Unposted Direct Receiving supports removing saved lines and reselecting items. Reselection removes the old unreferenced draft line and creates a new identity; untouched lines retain their IDs. New routing, UOM, price reference and tax defaults come from the chosen Item Master.
- PO/ML draft lines can be removed, but products still follow the original PO/ML; arbitrary replacement/additions remain restricted to Direct Receiving. At least one line is required.
- Active invoice dependencies block source draft editing. Any invoice-history reference (including VOID/REJECTED) prevents removal of its receipt line. Stock-history or posted-journal evidence also blocks draft editing. Removal/addition is included in the existing receiving audit; approved draft edits restart approval as before.
- No migration, production data cleanup, automatic unposting, invoice voiding or posted-data rewrite is performed.

Validation includes backend removal, reselection, foreign-line, invoice-history and posted-receipt regressions plus React form interactions. Test database is SQLite; PostgreSQL locks are not exercised by local tests.


## Controlled depost for higher users

`POST /goods-receipts/{id}/unpost` requires Receiving Manage/Edit/Post and Journal Manage,
a nonempty reason, an open accounting period and access to the receipt location. The UI
shows **Depost for Edit** only when the server grants it. It keeps the receipt ID/number.

The transaction locks the receipt, its affected products/inventory, source journal, invoices
and PO. Only an untouched automatic invoice draft can be withdrawn; confirmed, edited,
paid or duplicated invoices block depost. A later stock movement blocks rollback. Invalid
valuation/source evidence blocks rather than applying a balancing adjustment.

Original stock IN records remain in history. Explicit GOODS_RECEIPT_UNPOST OUT reversals
remove their quantity/value. Reposting creates a new active IN cycle; prior reversed cycles
are excluded from duplicate-posting checks and cost-correction selection. Inventory rounding
remainders at zero quantity are recorded in the audit, with a precision tolerance check.

A posted journal is unposted through the existing accounting service. Its DRAFT lines are
cleared (and audited) so the unposted receipt is not recognized by the new DRAFT accounting
rules. Reposting fills that same journal ID/number. No opening balance is changed.

The unconfirmed automatic invoice is VOID with audit evidence; its obsolete receipt-line
links are detached so corrected draft lines can be removed. Other invoice history stays
protected. Reposting prepares a fresh automatic invoice draft. Approval is restarted and
higher receiving managers can edit the returned draft at its pending stage.

All changes commit together or roll back together. No migration is required. Tests cover
stock/direct-use cycles, journal/GL identity, double-depost, permissions, closed periods,
confirmed invoices, later movements and failure rollback. Local tests use SQLite; database
row-lock concurrency requires a PostgreSQL environment for verification.

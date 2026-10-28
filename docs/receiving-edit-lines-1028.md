# Receiving edit lines — 2026-10-28

- Authorized users retain an **Edit Receiving** action after posting or invoice creation. The action opens the draft form only when the server permits editing; otherwise it explains the posting/approval restriction, links to the invoice when available, and offers the existing Correct Cost action when authorized.
- The restriction follows the receiving POSTED status, not simply invoice existence. This release does not introduce full editing of posted receipts. Price-only corrections use Correct Cost. Replacing/removing posted items requires resolving downstream invoices, unposting the source journal when posted, returning the receipt and creating a corrected report using existing workflows. Confirmed invoice, stock and accounting dependencies remain enforced by those actions.
- Unposted Direct Receiving supports removing saved lines and reselecting items. Reselection removes the old unreferenced draft line and creates a new identity; untouched lines retain their IDs. New routing, UOM, price reference and tax defaults come from the chosen Item Master.
- PO/ML draft lines can be removed, but products still follow the original PO/ML; arbitrary replacement/additions remain restricted to Direct Receiving. At least one line is required.
- Active invoice dependencies block source draft editing. Any invoice-history reference (including VOID/REJECTED) prevents removal of its receipt line. Stock-history or posted-journal evidence also blocks draft editing. Removal/addition is included in the existing receiving audit; approved draft edits restart approval as before.
- No migration, production data cleanup, automatic unposting, invoice voiding or posted-data rewrite is performed.

Validation includes backend removal, reselection, foreign-line, invoice-history and posted-receipt regressions plus React form interactions. Test database is SQLite; PostgreSQL locks are not exercised by local tests.

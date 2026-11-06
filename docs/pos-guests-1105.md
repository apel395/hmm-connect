# Hotel POS: table, guests, menu

Restaurant TABLE orders use the existing outlet/table and shift controls. Select a table, enter a positive whole number of guests, then add food/drinks. No guest count is invented from table capacity. COUNTER and EVENT guest counts remain optional; Catering invoices are unchanged.

Guest count is saved in the draft, included in the order retry identity, restored on Continue and browser recovery, and retained on settlement. Draft edits include before/after counts in the audit trail. Counts do not change pricing, PBJT, service charge, payment allocation, GL, inventory, or opening balances. Posted sales remain immutable. Table uniqueness and cashier-shift locks remain in the existing services.

The outlet open-order list and sale detail show the saved count. Existing historical counts remain unknown (NULL); no backfill or transaction values are rewritten. A legacy TABLE draft must have its guest count entered through Continue before it can next be saved/settled.

## EC2 migration before API release

Apply `20261105_pos_guests` after `20261104_pos_checkout` in an isolated backend worktree with the existing virtualenv/environment. Then run `PYTHONPATH=. /opt/hmm-connect/.venv/bin/python scripts/check_pos_guests_1105.py`.

The migration adds only nullable `sales_transactions.guest_count` and a positive-count check. Downgrade refuses to discard recorded counts. No default data or financial entries are created. Backend and frontend PRs must be approved before merge/deployment.

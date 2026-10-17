# Item Master treatment and false-stock correction

Fresh Vegetables, Fruit, Herb, Fish, Poultry, Meat and Snack default to Direct
Use in new Buy forms. Frozen/Beku, Tenderloin, Sirloin and explicitly named
imported items retain a Stock default. These are editable defaults, not inferred
historical warehouse events. Existing masters are not changed during deployment.

Changing a stocked item to Direct Use offers **Save & correct stock**, displays
current stock value and records a reason. The API requires finance management
permission and explicit correction intent. It locks the product and affected
rows. A metadata edit cannot silently abandon a warehouse balance.

Automatic correction is limited to fully matched, posted 2026 receiving-only IN
history, with no subsequent issues/transfers/adjustments, no explicit warehouse
exceptions, matching quantities/costs and journal/GL amounts. Original accounting
periods must be open and permit the selected historical dates. Hotel receiving
must identify its consuming department. Ambiguous or unsafe cases fail as one
transaction; the master and financial records stay unchanged.

The operation moves only that item's original receiving inventory debit to its
selected expense account, retaining the source journal number and dimensions.
The original credit, document prices/taxes, invoice/AP and manual opening values
are untouched. It removes proven false IN movements and matching inventory rows,
sets those receipt lines to Direct Use, preserves other lines in mixed receipts,
and records before snapshots. No synthetic OUT or extra journal is generated.
Repeating an already completed master correction produces no duplicate posting.

Receiving posting reloads and locks current master settings. A warehouse draft
that predates a Direct Use change needs its line reviewed or a documented
warehouse exception before posting.

## Existing food master batch

`scripts/correct_food_item_treatments_1017.py` defaults to a dry run, simulates
eligible corrections and rolls back. `--apply` commits eligible items; blocked
items are isolated using savepoints and listed with reasons. The full JSON report
includes every item, preserved warehouse default and selected expense account.
It uses each item's valid purchase/COGS mapping first, otherwise the registered
active debit food-cost posting account `500-100-100`. No new COA is created.

The operator is recorded as an EC2 classification script, without impersonating
a human user. Re-running is idempotent. Run against the backend worktree with the
existing `.env` and `.venv`; no database migration is required.

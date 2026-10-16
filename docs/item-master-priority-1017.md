# Item Master and purchasing priorities — 17 October 2026

Hotel/Catering each have separate Buy and Sell menus. Existing `/products` and
`/hotel-items` links now open Buy items; `/sell-items` and `/hotel-sell-items`
open Sell items. New forms inherit the menu's item type. List/export filters
preserve both catalog and type. The export worker must be updated on EC2.

Optional department ownership is stored in `item_departments`, one assignment
per item. Existing items stay shared until explicitly assigned. Select only an
active department in the catalog's unit and user's assigned location. This is
master metadata: it never allocates or edits historical stock/journals. Before
migration, item reads and existing writes remain available, but assigning a
new department returns a clear migration-required error. The UI disables that
selector until the table exists.

Market List supports Vegetables, Fruit, Herb, Fish, Poultry and Snack. Meat is
explicitly enabled in Item Master; existing meat stays on normal purchasing
unless marked. This does not infer eligibility from words like fresh/frozen or
change treatment based on family. Receiving follows the item's configured
Stock/Direct Use treatment. A warehouse/direct-use exception requires a line
reason and valid posting accounts. No existing document is reinterpreted.

Store Request creation/date changes and warehouse issue draft creation validate
the selected accounting period. Closed periods reject the date; past dates in
open periods require `allow_backdated_entries`. Issue posting rechecks the
period, and the issue cannot precede its request.

Item detail popups have tracked print previews beside purchase-order and
receiving references, using the source's existing print route and permissions.
The help icon on page headers opens a searchable task guide. It is guidance,
not an automatic posting or financial correction tool.

## EC2 update

Use a detached worktree from the real `origin/backend` branch, link the existing
`.env`, run migration and checks with `/opt/hmm-connect/.venv/bin/python`.
`check_item_master_1017.py` reports migration status and assignment count.
`audit_item_duplicates_1017.py --output /tmp/item-duplicate-review.json` is
read-only. It groups case/space variations within the same catalog and BUY/SELL
identity and lists units, treatment and foreign-key reference counts. Different
units or treatments require review. No automatic delete, merge or history edit
is performed. Review the production report before choosing survivor IDs.

Restart the existing export worker against updated backend code for BUY/SELL
exports. No opening balances, accounting values or tax flags are changed.

# Hotel POS outlets — cashier operations

This feature is stacked on Phase 1 PR #475. It is not released until approved, the backend migration is applied on EC2, and both approved branches are merged through the normal production process. API: Lambda/backend; UI: Vercel/main; database: PostgreSQL/EC2.

## Menu and use

**Point of Sales → Outlet Operations** reuses the current Hotel Location and child Outlet master. Select the Hotel and outlet; access follows your login organization.

- **Setup** (finance manager): TABLE for restaurants, COUNTER for cafés (optional table), EVENT for banquets. Outlet names do not configure behavior automatically. Finish open orders and shifts before changing mode.
- **Tables** (finance manager): create a name and seats; edit/deactivate/reactivate. Occupied tables cannot be changed. Tables never move between outlets.
- **Shifts** (cashier): enter counted opening float and open your shift. This float does not change the annual opening balance or create a journal.
- **Orders**: Open order goes to the existing Register. Choose a table/event, add menu items and Save Draft. Only saving reserves a table. Continue / settle loads the same order ID, lets you add items or change quantities, and keeps its original outlet/table/shift. Unsaved input is recovered per order and user. Clearing local input leaves a saved draft open; use Sales → Void to cancel an unposted order explicitly.
- **Settlement**: existing cash/card/bank, PBJT, service charge and GL posting apply. Cash tender must cover the total; change is excluded from cash retained. Invoice · AR remains an unpaid customer bill and is not counted as collected cashier money.
- **Close shift**: settle/void all drafts, count the drawer, and explain any difference. Expected cash = opening float + cash sales. The difference is recorded as evidence without a balancing journal. Use **Print shift report** for the individual shift, its cashier/times, totals and transactions.
- **Reports**: choose dates and optionally a cashier. Shows sales/payment method, service charge, PBJT and daily outlet closing totals, excluding AR bills and documents without posted journals.

Tables show AVAILABLE/OCCUPIED from saved open orders. Multiple cashiers may have separate sessions in an outlet, but no cashier can open a second active session there. Another cashier cannot edit or settle your active order. A manager may close a shift only when it has no remaining open orders.

## Compatibility and scope

Backend migration: `20261024_pos_operations`. New Hotel outlet POS orders require configured mode and an open shift. Existing posted sales, journals, tax, AR and stock are untouched. Unsessioned historical Hotel drafts must be explicitly voided/re-entered before settlement; the system does not silently attach them to a shift.

No recipe/BOM consumption, inventory posting, split tender, paid-outs/refunds, kitchen tickets or shift reopening is introduced. Source transaction and server authorization remain authoritative. Network retries preserve saved order identity; posted orders cannot be resumed for editing.

Validation includes React component interactions for required shift/table/event, outlet pinning, refresh/retry, continued-order editing and single source identity; backend regression checks cover accounting, access and operational integrity.

## Opening the correct Hotel context

Outlet Operations resolves link parameters against the signed-in user's accessible Hotel locations and child outlets before requesting operational data. Catering links and unrelated departments are not valid Hotel contexts. The Register only offers its scoped Outlet Operations link after a valid Hotel child outlet is selected. A direct `/pos/operations` visit lets the user choose a Hotel and outlet; a Hotel with no configured child outlets remains selectable and explains the required master setup. Failed requests show the actual available API error and do not assert that the database migration is missing.

# Central POS settings and access review

## Configuration

Open **Settings → POS Settings** (`/settings/pos`). Choose a sales location:

- Hotel: configure existing F&B outlets (three-letter code), select an outlet,
  change order mode, and create/edit/activate/deactivate tables. Occupied-table
  and active-order protections stay enforced by the existing backend services.
- Catering: maintain the existing per-location customer/billing/contract defaults,
  accounts, terms and explicitly shared service list.

Configuration forms are removed from the Register and Outlet Operations pages;
those pages link to the selected location/outlet in Settings. Runtime orders,
shift opening/closing, table occupancy and reports stay in Outlet Operations.
Reapplying saved defaults to a new invoice remains available in the Register.

Permissions are unchanged: `pos.view` plus `admin.settings.manage` for outlet
master changes; `pos.view` plus `finance.manage` for mode/table and Catering
billing changes. The settings route and navigation expose only the applicable
controls. No database migration, automatic account mapping or role elevation.
Existing payment-method mappings and discount calculation are not changed by
this settings relocation. Payment setup and controlled discount policy remain
separate backlog tasks (#507, #506).

## Missing Catering menus for an Admin (#509)

An account's display name/username does not grant administrative privileges.
`SYSTEM_ADMINISTRATOR` is the existing unrestricted role. Custom Admin roles
require persisted POS permissions and retain their assigned organization scope.
No patch should turn a similarly named role into an unrestricted administrator.

The companion backend read-only command compares selected account IDs:

```bash
PYTHONPATH=. .venv/bin/python scripts/check_pos_access_1104.py --user-id ID1 --user-id ID2
```

It reports canonical-admin status, effective POS permissions, organization
assignments, accessible sales locations, menu counts and unavailability reasons.
On PostgreSQL the transaction is explicitly READ ONLY. It never changes users,
role mappings, Item Master or transactions. Tests prove that two canonical Admin
profiles see the same Catering menu even with different location assignments;
custom roles remain scoped and require explicit permission.

The specific production accounts have not been inspected. Do not mark #509
resolved until their IDs/output identify whether the cause is permission,
organization scope, inactive location, item availability or a reproducible bug.
The Register now distinguishes an options request failure from no accessible
sales locations, rather than appearing as an unexplained empty menu.

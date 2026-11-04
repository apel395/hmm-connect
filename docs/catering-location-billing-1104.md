# Catering service invoices across locations

Backend `backend` / frontend `main`; deploy only after approval. Apply additive
migration `20261104_catering_billing` on EC2 before releasing these branches.
It follows `20261104_catering_prices` and does not update historical invoices,
customers, Item Master, journals, inventory, opening balances or AR allocations.
Check with `PYTHONPATH=. .venv/bin/python scripts/check_catering_billing_1104.py`.
Rollback refuses to discard saved settings or invoice details.

## Setup and operation

In POS, select **Invoice · AR**, then a Catering sales location. Authorized
Finance users can open **Location billing settings**. Optional defaults include
customer, department, payment term days, revenue/receivable accounts, contract,
billing address, payment instructions and print layout. Nothing is mandatory
merely to save location defaults. Customer identity remains independent of location;
no PHR customer/code/name is required to use the Catering invoice layout.

A service assigned to no sales location remains available across compatible
locations under the existing Item Master rule. To reuse an already location-owned
service, explicitly select it under **Additional services available at this
location**. Only active NON_STOCK Catering SELL services in the same business unit
can be shared. This does not change their original Item Master, Hotel menus or
normal paid POS availability. Generic shared services must still satisfy their
Item Master department and business unit restrictions.

Location defaults fill a new invoice. **Use location defaults** explicitly reapplies
them. Each invoice can adjust billing identity/address, contract, period/reference,
service description, quantity, unit, price and invoice date. Tax and service-charge
calculation follows the existing saved transaction rules; no new rate override is
introduced. Financial account choices still use existing active posting-account
validation.

Draft Catering invoices can change to another authorized Catering location. The
app checks every service at the target before accepting the change. Prices,
quantities and entered details are retained; unavailable services leave the old
selection unchanged. Saved drafts retain their invoice ID/number and can be
continued from POS Sales. Existing Hotel/outlet/table orders retain their locks.
Posted invoices remain immutable under this patch.

Billing details and service descriptions/periods are saved on the invoice. Later
customer, location-setting or product-name edits do not rewrite those snapshots.
POS and AR use the same Catering print representation. Existing manually saved AR
print-document overrides continue to apply. Legacy invoices without snapshots
retain their prior client-print settings behavior.

## Accounting and permissions

Settings require `finance.manage` plus `pos.view` and location/unit/department
access. Creation/draft changes require existing `pos.sell`; existing scope rules
apply to both old and target locations. Posting revalidates menu availability,
revenue account, customer, AR account and the open accounting period through the
existing posting service. No warehouse stock consumption is introduced. Duplicate
posting remains rejected and AR is created only once by the existing workflow.

Regression coverage: context validation without writes, permitted sharing,
unavailable/cross-scope rejection, draft identity, price/tax totals, saved billing
snapshots, non-PHR print layout, line descriptions/periods, posted guards, no stock
or opening-balance changes, migration preservation and frontend draft recovery.

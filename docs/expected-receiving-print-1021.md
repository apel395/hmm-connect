# Expected Receiving print

Open Purchasing → Receiving → Expected deliveries. The schedule has a Print
icon for the complete filtered list and each PO has its own Print icon beside
Receive. Both open the existing large print preview with A4 landscape layout.

The preview reloads the authorized receivable PO API with the selected delivery
date range. It groups outstanding items by PO/supplier and shows expected date,
location, department, separate item code/description, ordered quantity, received
quantity, remaining quantity and UOM. Fully received items are omitted. If the
selected PO no longer has outstanding items in the selected dates, it asks the
user to refresh rather than printing stale rows. Unscheduled deliveries appear
when no delivery date range is selected.

Headers repeat across pages, item codes are emphasized, and the report includes
the generating user and Jakarta date/time. Counts summarize POs and outstanding
lines; quantities with different UOMs are not added together. This is a planning
report and does not create receiving, stock or accounting entries or increment
the original PO document's copy count.

Regression checks are included in `npm run test:finance`.

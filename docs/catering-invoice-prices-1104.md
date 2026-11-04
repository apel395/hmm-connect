# Catering invoice prices

For Catering **Invoice / AR**, the SELL Item Master price is the initial reference.
The register shows an editable Unit price beside each selected item. Changing it
updates that line's amount, service charge, tax and invoice total using the
existing calculations. The agreed price belongs to that transaction; editing or
posting never changes the master selling price.

Use the copy icon on an order line to add the same menu with another unit price
(for example, two biweekly service periods). Enter its price, then save the draft
or post the invoice. Each line has an independent UI identity, quantity and price.
Matching-price lines continue to use quantity. The duplicate-line exception is
limited to Catering invoices; normal POS/Hotel behavior remains unchanged.

Refresh recovery and Continue Draft preserve entered prices. Existing Sales draft
editing already supports unit-price editing. Posted invoices remain controlled by
the existing correction workflow. Source tax/service-charge rules and permissions
are unchanged; no new approval or master-data fields are introduced.

Migration `20261104_catering_prices`, after `20261103_return_completion`, removes
the product-per-sale uniqueness constraint so separate-price lines can persist.
Existing line primary keys, data, stock, journals and opening balances are not
changed. Apply before releasing the backend. Downgrade refuses if repeated-product
invoice lines exist, preserving their history.

Regression coverage: distinct-price create/update/post, master reference unchanged,
AR print amounts, draft identity, duplicate posting, invalid prices, separate UI
line values, refresh/retry recovery, existing hotel operations and a populated
PostgreSQL schema migration.

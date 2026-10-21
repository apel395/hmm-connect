# Location-based POS and PHR catering invoices

POS sells active NON_STOCK SELL items from the selected location's HOTEL or CATERING catalog. A menu's explicit sales unit/location and Item Master department/outlet ownership constrain availability. BUY materials are never cashier menu items. A department-owned menu requires selecting that department. Menus with no department ownership remain available at valid locations.

A sale no longer needs warehouse stock. Completing payment posts cash/bank, sales revenue, applicable supported tax and service charge using existing explicit POS account mappings. It does not produce inventory OUT, inventory credits or synthetic HPP. Record ingredient costs through the actual receiving/warehouse issue workflows. Existing posted transactions are preserved. Old BUY drafts must be corrected before posting.

Zero selling prices cannot be checked out. Existing unsupported PBJT/PPN sales-profile / withholding configurations remain blocked explicitly; no tax is inferred or silently omitted. Cashier menu cards with unsupported profiles are disabled. This patch does not implement recipes, ingredient consumption, or seed SELL master data.

Migration: `20261021_pos_sell_catalog` makes sales_transactions.warehouse_id nullable, keeping historical warehouse references. Apply on EC2 with the deployed backend checkout, existing .env and .venv. Downgrade refuses if location-only sales exist, rather than assigning a fabricated warehouse.

AR: customer-specific PHR template remains in AR > invoice > Client invoice layout. Configure billing/address, attention, contract, bank instructions and signatory. Invoice service details hold biweekly registration numbers, descriptions, explicit tax/amounts and words. Amounts must match the recorded AR invoice before printing. The accepted sample is a layout reference; signatures, stamps, PHR acceptance records, contractual numbers and historical amounts are never automatically copied into production. Sample regression: 230,817,730 + 238,436,660 + 46,925,439 = 516,179,829.

Validation: tests/test_pos_sell_catalog_1021.py and tests/test_phr_invoice_print.py. Frontend test:finance includes accepted PHR amounts and escaped data rendering. No production records are seeded or changed by this patch.

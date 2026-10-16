# Receiving destinations per item

New receiving lines default from Item Master: STOCK to Warehouse; DIRECT_USE/NON_STOCK to Direct Use; FIXED_ASSET to its existing non-warehouse asset route. The create form has no document-wide Destination selector.

A line's Special Case icon allows STOCK or DIRECT_USE goods to use the other destination with a recorded reason. Warehouse exceptions still require a valid inventory COA; service/non-stock and fixed asset items cannot be routed into consumable warehouse stock. The exception never changes the Item Master.

One receipt can mix destinations. Its header becomes MIXED; a single warehouse, in the receipt's work location, is required only when a warehouse line exists. Only warehouse lines create stock movements or change average cost. Journal debit accounts, invoice snapshots, cost correction, and returns use each line's saved destination. Approval, taxes, dates, PO/ML limits and finance journal posting stages remain unchanged.

Existing lines stay NULL after migration and inherit their original header; they are never reclassified from today's Item Master. Editing costs/quantities preserves the saved route. Selecting Item Master explicitly resets a line to its current master default. Old API clients using document-wide destination remain supported; the new forms send line-level choices.

## Release

Apply migration 20261016_receiving_lines on EC2 before merging the backend API or releasing the new UI. It adds two nullable columns; it does not rewrite source documents, stock, accounts or balances. Run scripts/check_receiving_destinations_1016.py afterward.

Backend branch deploys Lambda; main deploys the frontend. No API server restart is required on EC2. Keep worker checkout compatible after release.

# MMH asset policy — 20 October 2026

## Useful life and categories
MMH requires at least 48 months for newly configured depreciable fixed assets and newly created amortization records. This is company policy, not a claim that every accounting or tax category has a four-year life. Finance may choose longer lives. Ordinary land remains non-depreciable with no invented life or posting accounts. Existing records and posted schedules are never silently rewritten; reports identify lives below the current minimum. Previously active schedules and amortization preserve their historical amounts and reversal controls.

Tangible assets use depreciation; intangible assets and amortizable costs use amortization. Both post expense and accumulated reduction (or direct prepaid reduction where configured) through existing explicit monthly posting actions. Classifying an item does not duplicate its source acquisition journal. Historical opening balances remain separate.

`setup_asset_categories_1020.py` creates missing MMH categories for existing COA: land, building, mechanical/electrical, vehicle, FF&E and other fixed assets. Each depreciable category starts at 48 months and can be extended. It validates active posting accounts and preserves existing categories, asset snapshots and journals. It does not invent COA or assign categories to existing assets automatically. Missing COA is reported for setup; invalid posting configurations abort. No schema migration is needed.

## Utensil cleanup
Under MMH policy, chinaware, glassware, silverware and utensils belong in MATERIAL Item Master and operational quantity control, not depreciation. New fixed-asset categories cannot use their `100-900-101` to `100-900-103` accounts. Linen is separately classified and is not included.

`cleanup_hotel_utensil_assets.py` expands the earlier 13-item repair to all Hotel BUY FIXED_ASSET items matching utensil classifications or original `UTEN -` / `CHI -` source prefixes. These identify the source catalogue family even if imported as FURNITURE. The entire candidate batch is validated under locks. Any valuation, acquisition date, source document, physical stock, depreciation or accounting evidence blocks the transaction for inspection.

Eligible items move to MATERIAL / UTENSILS, STOCK, inventory `100-300-700` and issue expense `700-500-119`, retaining IDs, prices, tax and master relationships. Only empty ITEM_MASTER PENDING_REGISTRATION rows are removed. No stock, expense, journals, GL or balances are created. Actual later receiving and issue establish quantities and expenses. A second run finds no remaining matching fixed-asset classifications. Preview rolls back changes including classifications and audit; `--apply` commits atomically.

## Reports and export
Fixed Asset Register shows registered records, category, life, cost, accumulated depreciation, book value, status and policy review. Unvalued catalogue registrations are excluded. Totals exclude disposed/written-off/inactive records; detail retains history. Category summary and selected details export in separate Excel sheets.

Depreciation Report separates POSTED amounts from PLANNED/GENERATED forecasts; SKIPPED amounts contribute to neither. Date, unit, location, department, category and status filters are enforced on the server and shared with Excel. The UI defaults to POSTED. These are monthly schedules, not daily prorated expense. Amortization register has authenticated Excel export and legacy policy reviews. All exports use login scope. The asset register shows current state; depreciation is period-filtered. No historical as-of carrying-value reconstruction is implied.

## EC2
Use the persistent checkout, linked production `.env`, and `/opt/hmm-connect/.venv/bin/python`. API code deploys to Lambda through backend; EC2 runs setup and cleanup separately.

```bash
cd /opt/hmm-connect
git fetch origin backend
cd /opt/mmh-notes-1020
git merge --ff-only origin/backend
/opt/hmm-connect/.venv/bin/python scripts/setup_asset_categories_1020.py
/opt/hmm-connect/.venv/bin/python scripts/setup_asset_categories_1020.py --apply
/opt/hmm-connect/.venv/bin/python scripts/cleanup_hotel_utensil_assets.py
/opt/hmm-connect/.venv/bin/python scripts/cleanup_hotel_utensil_assets.py --apply
/opt/hmm-connect/.venv/bin/python scripts/check_1017_master_data.py
```

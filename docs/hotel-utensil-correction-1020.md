# Inspected Hotel utensil correction — 2026-10-20

The production read-only inspection identified exactly 13 Hotel BUY items: product 7391 and products 7399–7410. Each is currently FIXED_ASSET and linked to the specified unvalued ITEM_MASTER registration. No stock balances were reported. There are zero SELL items and no purchasing retention candidates in that inspection; those are not repair targets.

`scripts/reclassify_hotel_utensils_1020.py` validates the exact IDs, names, old codes and old asset links again under locks. It refuses changed, inactive or valued records, any transactional product link, warehouse quantity/value, asset movement, depreciation schedule or direct asset accounting evidence. All 13 are checked before any mutation. The script reuses or creates the uniquely active **MATERIAL / UTENSILS** subgroup, then allocates normal classification-based item codes with the existing item-numbering lock.

The items use **STOCK** for future receiving, inventory COA **100-300-700**, and issue expense COA **700-500-119 Alat & Perlengkapan**. This is a prospective warehouse setup, not evidence that the company already holds these quantities. Receiving can use an explicit Direct Use line override when the supplies are consumed immediately. No stock quantity, receipt, invoice, expense, journal or GL is created by the repair. Prices, tax flags, names, product IDs and other master references remain unchanged. Only the 13 proven empty pending asset registrations are deleted, with complete before/after snapshots in the audit.

Dry run stages everything transactionally and rolls it back. Apply commits the batch atomically. A repeat run validates the completed state and returns `already_applied` without new writes. A changed record aborts the transaction rather than guessing a correction.

```bash
/opt/hmm-connect/.venv/bin/python scripts/reclassify_hotel_utensils_1020.py
/opt/hmm-connect/.venv/bin/python scripts/reclassify_hotel_utensils_1020.py --apply
/opt/hmm-connect/.venv/bin/python scripts/check_1017_master_data.py
```

# Hotel linen cleanup — 2 November 2026

Scope: the 35 Hotel BUY masters with product IDs 7344–7378 and the exact empty asset registrations 3–37, as listed in the EC2 read-only inspection. No other item or asset is targeted.

## Result

- Retain each Product ID, name, UOM, usage UOM, conversion, prices, tax, supplier and department relationships.
- Move classification to MATERIAL / LINEN and STOCK.
- Use inventory COA 100-900-100 (the same account previously used on the empty asset).
- Allocate a classification-based MATERIAL item code; retain the old code in the audit record.
- Remove only the exact PENDING_REGISTRATION / ITEM_MASTER asset whose cost/date remain unknown and which has no valuation, registration, source, fiscal, schedule, movement or accounting evidence.
- Retain existing purchase/issue-expense account IDs; do not invent a new consumption expense mapping.
- Create/reuse one active LINEN subgroup under the purchasing MATERIAL group. Prefer explicit BUY over supported legacy ITEM; never choose a SELL group.

No opening quantities, inventory movements, depreciation, source-document corrections, journals or GL entries are created. Warehouse quantities must come from actual receiving/opening/physical-count documents, not the legacy Item Master price.

## Execution

From a backend checkout containing the script, with the EC2 `.env` available:

```bash
/opt/hmm-connect/.venv/bin/python scripts/cleanup_hotel_linen_assets_1102.py
/opt/hmm-connect/.venv/bin/python scripts/cleanup_hotel_linen_assets_1102.py --apply
/opt/hmm-connect/.venv/bin/python scripts/cleanup_hotel_linen_assets_1102.py
```

The first command is a rolled-back preview. `--apply` commits all 35 changes and audit records in one transaction. Any changed identity, nonempty registration, transactional item use, missing mapping or audit failure stops/rolls back the entire batch. No partial cleanup is committed.

The last command should report `already_applied: 35`, `changed_items: 0`, `removed_empty_assets: 0`. A no-op rerun remains valid after subsequent legitimate receiving/warehouse use, provided the cleaned classification and deleted asset links have not changed. Unexpected later edits are reported; they are not silently repaired again.

Each `LINEN_RECLASSIFIED` audit contains the full original master snapshot, updated snapshot, removed empty asset snapshot and this batch ID: `HOTEL_LINEN_20261102`.

No API, frontend or schema migration is needed. This script is explicitly run on EC2; merging it does not execute the cleanup. Refs issue #503; production completion must be confirmed from the apply/verification output.

# Classify the 6 October BUY master seed

The public RESIPING workbook is the item-name and unit source. Reviewed SHA256:
`1a2055a09ef413e0e958fdc16537a3bae1792af12b786d388eacc304e2edf821`.
Its 2026 rows contain 349 distinct names. The explicit JSON manifest covers all
349 names; the database update selects only the 291 product creation audits
for this hash. Existing matches, aliases, unit-review items and SELL items are
outside that batch. No code prefix is used to infer classification.

STOCK is the default for ingredients, drink ingredients and consumables;
ready-to-eat prepared purchases are DIRECT_USE. A receiving destination can
still reflect immediate use of an otherwise stockable item. Family/subgroup
are independent of item code. Syrups use the dedicated BEVERAGE / SYRUP subgroup; drink powders, coffee
and tea use FOOD / GROCERIES. Prepared snacks use SNACK; complete meals use
GROCERIES. DIRECT_USE remains separate from family/subgroup classification.

| Family | Stock asset | Consumption expense |
| --- | --- | --- |
| FOOD | 100-300-100 | 500-100-100 |
| BEVERAGE | 100-300-500 | 500-100-102 |
| MATERIAL | 100-300-700 | Not assumed |

STOCK sets inventory and the consumption COGS account where mapped.
DIRECT_USE sets the purchase expense account, with inventory/COGS unset.
No contra account, transaction or balancing entry is created. Tax remains
REVIEW_REQUIRED with original flags; this is not a non-taxable determination.
Confirm supplier invoice evidence separately.

```bash
cd /opt/hmm-connect
git pull --ff-only origin backend
.venv/bin/python scripts/classify_resiping_items.py \
  --drive-id 1gmy6cY8Vccuj78Rj5tNv2EuNtwdCqzqy \
  --output /tmp/resiping-classification-dry-run.json
.venv/bin/python scripts/classify_resiping_items.py \
  --drive-id 1gmy6cY8Vccuj78Rj5tNv2EuNtwdCqzqy \
  --output /tmp/resiping-classification-applied.json --apply
```

If Drive has since changed, replace `--drive-id ...` with
`--file /tmp/resiping-seed-20261006.xlsm` to use the exact workbook already seeded.
The script refuses a different hash, unexpected batch count, changed identity,
manual accounting edits, or usage in inventory/receipts/invoices. Those records
need a follow-up review rather than silent historical changes.

Dry-run is read-only. Apply validates every item before writing and commits
atomically. Before/after audits are recorded. The only new subgroup permitted is BEVERAGE / SYRUP. BUYPEND is removed
after all 291 items move. PREPARED FOOD, PREPARED DRINK and any unmerged
BEVERAGE INGREDIENTS proposal are removed; existing items are reassigned
without changing accounting or tax. Future seeds do not create BUYPEND.
Legacy ITEM groups are normalized only if all their products are BUY.
Repeat runs report ALREADY_CLASSIFIED without new audits. Terminal output is a
summary; full details are saved to the JSON report. No migration is required.

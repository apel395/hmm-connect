# RESIPING item-first seed

Use the supplied `RESIPING2026_UNUSED_INVOICE_DROPDOWN_CLASSIC_EXCEL.xlsm`
local copy. Scripts never evaluate macros or general formulas. Template invoice
IDs and blank-date continuation are decoded explicitly. Dates are reset for
each new invoice. The read-only preparation of the supplied workbook found:

- 460 receiving item rows with 2026 date evidence; 260 distinct names.
- 664 pre-2026 rows excluded.
- 51 rows with missing/ambiguous year, missing invoice links or missing units
  held for review.
- 6 distinct items with multiple units requiring conversion review.

Run from `/opt/hmm-connect` with `.venv`. Use `--drive-id` to download the public Excel file directly, or use
`--file scripts/resiping-source.xlsm` for a local copy. Downloads are temporary;
source Drive ID and SHA-256 are recorded. Sign-in/error pages are rejected.

```bash
.venv/bin/python scripts/seed_resiping_items.py --drive-id 1gmy6cY8Vccuj78Rj5tNv2EuNtwdCqzqy --output /tmp/resiping-item-seed-plan.json
```

This default dry run matches existing BUY items by normalized exact name.
Existing SELL names never substitute for BUY records. Similar or slash-alias
names, inactive/ambiguous matches and incompatible units are deferred. No
existing master rows are overwritten.

After reviewing the DB plan, `--apply` creates eligible new BUY items already
classified with the explicit reviewed name/unit manifest. Only FOOD, BEVERAGE,
MATERIAL and ASSET families are allowed. It uses existing subgroups; SYRUP in
BEVERAGE is the only permitted new subgroup. It never creates BUYPEND. Unknown
names remain in the JSON review report and are not inserted until classified.

Treatment and COA are assigned before insertion. Tax remains REVIEW_REQUIRED;
this is not a Non PPN determination. Stock and transactions are not created.
Stable name-based codes and table locks protect repeat execution. Each inserted
product records source hash/rows and optional `--actor-id` in audit.

The workbook report does not authorize any transaction import or any 2025
activity. Dates stored as Excel dates remain exactly as supplied; ambiguous
text/ranges require separate review before document posting.

The older 237-item classification workbook remains the source for correcting
existing reviewed identities through `correct_item_classification.py`;
it is not a replacement for the new RESIPING item extraction.

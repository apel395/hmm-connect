# PPh asset categories

The Categories page now uses the actual PPh groups, instead of one category per asset COA family.

| Group | Default months | Straight line/year | Declining balance/year |
| --- | ---: | ---: | ---: |
| Kelompok 1 | 48 | 25% | 50% |
| Kelompok 2 | 96 | 12.5% | 25% |
| Kelompok 3 | 192 | 6.25% | 12.5% |
| Kelompok 4 | 240 | 5% | 10% |
| Bangunan permanen | 240 | 5% | — |
| Bangunan tidak permanen | 120 | 10% | — |
| Tanah | — | — | — |

Source: PMK 72/2023, Article 2 and its annex, https://pajak.go.id/id/peraturan/penyusutan-harta-berwujud-danatau-amortisasi-harta-tak-berwujud . Classification examples must follow the annex and applicable industry, not just a broad item name. Actual longer permanent-building life is configured in the asset fiscal profile using the existing reference/election fields.

## Category vs posting accounts

PPh group categories have no shared asset account. Asset registration retains its actual 100-600 COA and uses the matching 100-800 accumulated-depreciation account with expense 700-500-133. Groups 1–4 exclude land/building accounts; building groups require 100-600-101; land requires 100-600-100. Linen remains quantity-controlled inventory and is not a fixed asset.

The category supplies useful-life defaults. Existing book calculations remain straight line; the fiscal panel offers straight line / declining balance where permitted. Book life may differ from fiscal life and is still set per asset. Selecting a category does not create a fiscal profile or another GL journal. The category's PPh group is preselected when a user first configures that asset's fiscal profile. Existing fiscal profiles, book schedules, values and opening balances remain unchanged.

## Who created the previous categories?

The `MMH-*` family categories were created by the earlier EC2 setup script. Replacement requires matching audit evidence: the first CREATE/ASSET_CATEGORY_CREATED log must be action ASSET_CATEGORY_CREATED with batch ASSET_POLICY_20261020, and the code must belong to that script's explicit list. A matching name or code alone is insufficient.

Migration `20261102_pph_categories`:

1. Allows per-asset account mappings for PPh group categories.
2. Creates seven audited PPh category rows. An existing unrelated code is retained and a distinct new code is used.
3. Deactivates only proven script-created family categories. Their IDs and all asset references remain for history.
4. Preserves user/unconfirmed categories, including FA-0001 unless its provenance is separately established. The UI labels these as existing book categories and shows creator evidence when available.

No fixed assets are reassigned; no useful life, source accounting, depreciation, journals or balances are backfilled. There is no automatic linen data cleanup in this change.

The migration applies the category setup itself, so there is no second seed step to remember. The older setup_asset_categories_1020.py command now uses the same PPh policy and cannot recreate the old family defaults. It remains a rolled-back preview unless --apply is supplied.

Read-only authorship report (works before/after the migration):

```
python scripts/inspect_asset_category_creators.py
```

Run the new migration from the updated backend worktree **before** deploying the new category UI:

```
alembic upgrade 20261102_pph_categories
python scripts/inspect_asset_category_creators.py
```

The data migration is forward-only: reverting it by deleting categories would destroy classification/audit evidence or leave asset references invalid. Use a reviewed forward correction if required.

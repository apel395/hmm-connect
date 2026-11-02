# MMH fixed assets: book and fiscal policy

The supplied `chart-of-accounts (1).xlsx` defines these account pairs:

| Asset | Accumulated depreciation |
| --- | --- |
| 100-600-100 Tanah | None |
| 100-600-101 Bangunan | 100-800-100 |
| 100-600-102 Mekanikal dan Elektrikal | 100-800-101 |
| 100-600-103 Kendaraan | 100-800-102 |
| 100-600-104 Furniture, Fixture and Equipment | 100-800-103 |
| 100-600-105 Inventaris | 100-800-104 |
| 100-600-999 Asset Tetap Lainnya | 100-800-999 |

Book depreciation expense: **700-500-133**. IDs are looked up by code. Related accumulated accounts are filtered and selected in category setup. Missing accounts are never created by this patch. Existing historical asset balances and categories are not rewritten. MMH excludes operating supplies under 100-900 from new fixed-asset setup.

`100-400-*` is prepayments, not an automatic intangible-asset classification. `700-500-134` is HGB amortization, not a generic software expense. Existing amortization functionality remains unchanged. Generic intangible fiscal schedules are outside this tangible-asset patch.

## Book policy

The existing company minimum of 48 months remains for depreciable book assets. This is a company rule, not a universal tax rule. Categories supply book defaults; changing defaults does not rewrite existing asset schedules. Land is non-depreciable. Disposal gain/loss mappings remain optional and are used by the existing disposal workflow.

## Fiscal policy

Each registered asset can separately store its confirmed fiscal group, cost basis, method, start date and reference. No blanket mapping from a COA or a book category to a fiscal group: e.g. FF&E includes assets belonging to different groups. Finance must classify the actual asset under the PMK annex, including industry-specific rules. Unlisted non-building assets generally use group 3 unless another group is determined under the applicable procedure.

| Fiscal group | Years | Straight line | Declining balance |
| --- | --- | --- | --- |
| 1 | 4 | 25% | 50% |
| 2 | 8 | 12.5% | 25% |
| 3 | 16 | 6.25% | 12.5% |
| 4 | 20 | 5% | 10% |
| Permanent building | 20 | 5% | Not allowed |
| Non-permanent building | 10 | 10% | Not allowed |
| Land | — | None | None |

Permanent buildings can use a longer actual life with a recorded tax reference. The start date represents the fiscal commencement month, normally the expenditure month; completion/use and approved exceptions require the actual applicable date. The system does not decide that date from book capitalization automatically.

Monthly amounts round to cents; the final useful-life month clears the remaining balance. Declining balance uses each calendar year's opening fiscal NBV and prorates the first year. A historical fiscal NBV can be entered at December 31; it does not touch accounting opening balances. Reports before that snapshot are explicitly unavailable. Calendar-year fiscal reporting only; non-calendar tax years, tax improvements/capitalized additions, insurance-deferral approvals and special industry regimes require separate handling and are not inferred here.

Fiscal schedules stop at the effective disposal/write-off month. Reports show the fiscal NBV removed on disposal separately from depreciation; they do not automatically recognize or post a tax disposal loss or insurance income.

## Use

1. Fixed Assets → Categories: select the asset account, review its matched accumulated account and book life, then save.
2. Open a registered asset → Fiscal depreciation → Configure. Select the actual fiscal group and basis. Saving is audited and uses a version check; a stale edit must be reloaded.
3. Fixed Assets → Reports → Fiscal comparison: choose year and authorized unit/location/department/category. Export Excel or print. Assets without confirmed profiles display `NOT_CONFIGURED`; do not read their blank amounts as a completed zero calculation.
4. Book-minus-fiscal compares **posted book depreciation schedules** against calculated fiscal depreciation, for configured profiles only. It is not a tax return or a reconciliation of arbitrary manual GL depreciation entries.

Book depreciation continues through the existing depreciation-run journal service. Fiscal setup and reports create **no journals, GL rows, inventory movements or opening balance changes**.

## Deployment (only after approval)

Backend and frontend PRs must be reviewed together. Apply Alembic revision `20261102_asset_fiscal` using the backend feature worktree and the existing EC2 environment before enabling the fiscal UI. The migration creates only `fixed_asset_fiscal_profiles`; there is no financial-data backfill.

Optional category preparation:

```
python scripts/setup_asset_categories_1020.py
```

This is a rolled-back preview. `--apply` creates missing categories plus audit records only. Existing categories remain unchanged. Legacy `MMH-OTHER` mapped to 100-600-105 is reported for review; its posted mappings are not changed automatically. New explicit categories are `MMH-INVENTARIS` and `MMH-OTHER-999`.

Sources:
- https://jdih.kemenkeu.go.id/dok/pmk-72-tahun-2023
- https://pajak.go.id/id/peraturan/penyusutan-harta-berwujud-danatau-amortisasi-harta-tak-berwujud
- https://stats.pajak.go.id/sites/default/files/Lampiran%20PMK72TAHUN2023.pdf

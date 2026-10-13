# Hotel Item Master preparation

Source: `invlistofgoods.xls`, sheet `InvListofGoods.rpt`, SHA256
`a9d0e58b3fa1bacbe4d5cfcdcb96e1d9cfef003343979b0c71d1fd623f2ed96a`.

The source contains 3,822 rows across 17 legacy categories. The original codes
are not unique identifiers. Preserve source row, sequence, category and legacy
code in the import audit. Generate final MMH product codes with the existing
group/subgroup numbering service after classification.

Keep the source workbook on EC2 as `scripts/invlistofgoods.xls`.
The checker preserves all source item rows, including blank units, repeated
names and negative legacy Expense values. The report columns Purchase and
Expense remain source references. Expense is never used as an opening balance,
stock value or selling price. Purchase is a proposed reference cost only.
Confirm its meaning before application.

Target catalog is HOTEL. Catering matches are reported for information and are
never reused or moved. BUY versus SELL use requires review for portion items.
Only the existing FOOD, BEVERAGE, MATERIAL and ASSET groups are allowed for the
final seed. Source headings do not automatically create master groups or
subgroups. Equipment versus consumable and STOCK versus DIRECT_USE treatment
must follow actual use. Hotel Direct Use expense destinations remain selected
by department and receipt; this source contains no department/COA mapping.

No tax evidence exists in this report. Do not infer VAT, PBJT or exemptions from
item names. This preparation does not create stock, fixed asset records,
receipts, journals, tax or opening balances. No database apply mode exists.

Run from the repository using its .venv and .env:

```bash
.venv/bin/python scripts/prepare_hotel_items.py --check-db --output /tmp/hotel-item-seed-plan.json
```

Install the .xls reader with `.venv/bin/python -m pip install xlrd==2.0.2`.
This command runs
in a PostgreSQL READ ONLY transaction, rolls back and writes a JSON plan and
CSV review on disk. Review source duplicates, missing/invalid units, catalogue
matches, subgroup mappings, treatment and reference cost before constructing
the final seed manifest. Existing items and transaction history are untouched.

The checker includes active BUY/legacy ITEM groups, subgroups and candidate
posting accounts in its printed summary. This is the database evidence needed
for final mappings; it does not create taxonomy or assign expense accounts.
The script adds the repository root to its import path automatically.

`COFFEE` is a mixed legacy prefix (including milk powder, sprinkles and jam),
so it does not by itself move FOOD ingredients into BEVERAGE. Explicit syrup
is proposed under BEVERAGE / SYRUP. GROCERIES also recognizes the existing
legacy spelling GRESORIS without creating another subgroup.

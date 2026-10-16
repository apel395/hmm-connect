# January 2026 Hotel journal preparation

`scripts/prepare_hotel_january_journals.py` is deliberately read-only. It has no
apply mode and creates no journal, GL, opening balance or operational document.

Source: `xjur jan 26.xls`, sheet `gljournalTransactionbyregist.rp`, SHA256
`045a54343005ee0c3cbd130838dd292c594ae434452abbf9b19578f99bc22507`.
A changed source requires a new inspection; the script rejects a changed hash.

## Source rules

- One register is one journal. Never pair adjacent debit/credit rows or group by
  invoice reference. Registers and source row numbers remain in the full plan.
- Read financial amounts from Debit L and Credit M. The D/C label is informational
  because 3,284 labels conflict with the actual amounts.
- The file contains 3,261 registers and 7,844 lines; 27 zero-value lines remain in
  source evidence and are omitted only from future financial posting.
- Detail totals must match the source grand total exactly: debit
  Rp10,065,531,233.74; credit Rp10,065,576,233.74.
- Register 1151053, header row11220 / detail11222, has a Rp45,000 credit excess.
  Do not add a balancing line, alter opening balances, or silently skip it.
- All source posting dates are January2026. A 2025 date in descriptive text is
  not a posting date. The script blocks dates outside January2026.
- 3,004 nonzero lines have no new COA in column F. Missing mapping is not account
  zero and is never carried forward from another line.
- Sequence gaps214–216 are source diagnostics; do not manufacture missing lines.

## EC2 preparation

Use the EC2 worker virtualenv. `xlrd==2.0.2` is an XLS reader needed only here,
not in Lambda API dependencies. Place the original workbook on EC2, e.g.
`/opt/hmm-connect/scripts/xjur jan 26.xls`. The workbook and its customer data
are not committed to git.

```bash
/opt/hmm-connect/.venv/bin/python -m pip install 'xlrd==2.0.2'
/opt/hmm-connect/.venv/bin/python scripts/prepare_hotel_january_journals.py \
  '/opt/hmm-connect/scripts/xjur jan 26.xls' --db-check \
  --output /tmp/hotel-january-journal-plan
```

Outputs: full `.json` plan, `.csv` line review, and a `-mapping-template.json`.
Only the first two are overwritten on rerun; finance's mapping template is kept.
Copy the template, confirm Hotel business unit and location IDs, map the missing
legacy accounts to exact active posting COA codes, and confirm department IDs.
Suggested department names are evidence for review, not automatic assignments.
SWP, LDY, BOD and any unknown prefix require explicit decisions. Do not create
new departments or push everything into Admin and General.

Run again with `--mapping-file /path/to/completed-review.json`. The report uses
`SET TRANSACTION READ ONLY` to check COA, Hotel scope, linked departments,
January open/backdate settings and existing register references (including
draft/void records). Existing January journals are included for duplication review.
An external reference `HOTEL-JAN2026-REG-<register>` identifies each future journal
independently of file name/hash; later seed code must recheck this transactionally.

`READY_FOR_SEED_REVIEW` means that register passed the implemented preparation
checks. Overall `seed_ready` remains false: this is not a seed executor. Review
legacy imports with nonstandard references before authorizing any later seed.
Do not clear existing journals automatically. Any future importer must preserve
whole registers across batches and use the existing posting service, periods,
roles, audit and duplicate controls. The current bulk importer accepts at most
500 documents / 5,000 lines per batch.

This is a journal-only migration: it will not create AP/AR subledgers, stock
movements, payments, fixed assets or opening balances. Reconcile existing source
documents before later posting to avoid duplicating their GL effects.

## Prepared mapping review (16 October 2026)

Use `--mapping-file scripts/hotel_january_2026_mapping.json` to prepare against
the current database. This is a proposal for preparation, not authorization to
post journals. Existing source column-F mappings are kept, except legacy AP
201101: its target 200-100-100 does not exist; actual active posting AP is
200-100-1 (also used for legacy generic trade AP 201).

The manifest fills 77 of 110 previously unmapped legacy accounts by account
purpose. Hotel unit1/location8, named department prefixes (including LDY/Laundry),
and explicit Rooms/F&B/Banquet/Laundry legacy families use IDs from the uploaded
DB snapshot. New target accounts and departments are still validated on every
live preflight. No new COA/department is created.

Against that snapshot: 2,449 registers pass the implemented preparation checks;
812 require review. There are 783 nonzero lines without a final account mapping
(33 legacy accounts), 95 registers requiring department confirmation, 9
reference overlaps and the original one Rp45,000 imbalance. Categories overlap.
Counts are snapshot evidence; fresh EC2 output is authoritative.

Existing Hotel imports may use JOURNAL_IMPORT external references instead of
legacy register numbers. The preflight therefore also flags normalized document
reference matches within the same Hotel scope, including matches with different
January dates. These are possible overlaps, not proof of duplicates; compare
line detail before seeding. Never delete an existing document automatically.

Do not force director owner expenses into Prive, card/QRIS receivables into bank
cash, OTA advance receivables into guest deposits, or tax payables into expenses.
SWP and BOD department assignments remain unresolved; do not create substitute
departments or put them in Admin and General automatically.

### Remaining account decisions

| Legacy | Source account | Decision needed |
| --- | --- | --- |
| 591050 | BOD - Officer Check/ Complimentary BOD | Director complimentary meals: confirm staff meal versus directors expense and department. |
| 591007 | BOD - Owner Expenses | Mixed owner/business/project descriptions: confirm expense versus drawings; do not force all to Prive. |
| 201409 | A/P - Refund | Refund payable: confirm guest deposit/refund control account. |
| 103086 | A/R - BNI Debit Card | Card receivable: confirm clearing versus trade receivable policy; not bank cash. |
| 103091 | A/R - Mandiri Visa Card | Card receivable: confirm clearing versus trade receivable policy; not bank cash. |
| 103092 | A/R - Mandiri QRIS | QRIS receivable: confirm settlement clearing versus trade receivable policy; not bank cash. |
| 103089 | A/R - Mandiri Debit card | Card receivable: confirm clearing versus trade receivable policy; not bank cash. |
| 103087 | A/R - BNI Credit Card Master | Card receivable: confirm clearing versus trade receivable policy; not bank cash. |
| 103090 | A/R - Mandiri Master Card | Card receivable: confirm clearing versus trade receivable policy; not bank cash. |
| 103085 | A/R - Advance Deposit | A/R advance deposit includes OTA prebuy settlements: confirm receivable versus customer deposit; do not change to a liability by name alone. |
| 536005 | SWP - Swimming Pool Chemical | Pool chemical: choose cleaning supplies versus water treatment/pool maintenance. |
| 548006 | PMC - Maintenance Plumbing/ Heating | Plumbing/heating maintenance: choose building maintenance versus operating equipment repairs. |
| 305002 | Banquet Meeting Room | Meeting room rental: confirm F&B banquet revenue versus other Hotel revenue. |
| 401602 | COGS laundry Guest | Laundry COGS: choose direct versus other COGS; preserve COGS classification. |
| 201499 | A/P - Others | Other payables: confirm trade payable versus other liability. |
| 544006 | A&G - Data Processing | Data processing includes web/email and internet: confirm communication versus IT expense; may need line-specific mapping. |
| 514007 | HK - Decoration & Garden | Decoration and garden combine supplies and landscaping: confirm account or split by line. |
| 544021 | A&G - Miscellaneous Expenses | Miscellaneous administration: confirm Hotel operating versus administration expense. |
| 201408 | A/P - Short / Over | Source short/over is a payable: confirm settlement liability versus genuine expense before reclassifying. |
| 532023 | FBP - Food Test | Food testing: confirm direct food cost versus entertainment/promotional expense. |
| 522023 | FBS - Food Testing | Food testing: confirm direct food cost versus entertainment/promotional expense. |
| 512037 | FO - Fruit Basket, Welcome Drink, Birthday Cake | Fruit basket/welcome drink/birthday cake: confirm guest supplies versus complimentary food cost. |
| 201411 | A/P - Loan/Pinjaman | Loan payable includes director borrowing and employee repayments: requires counterparty/line review. |
| 548009 | PMC - Maintenance Painting/ Decorating | Painting/decorating maintenance: confirm building repairs versus decorating supplies. |
| 544012 | A&G - Cash Overages & Shortages | Cash over/short: confirm operational cash difference account and department. |
| 544017 | A&G - Licenses | Licences: confirm permit/admin expense versus legal/audit fee. |
| 106099 | Other Assets | Other assets has a banquet issue: confirm fixed asset versus operating equipment account. |
| 514051 | HK - Miscelleneous Charge | Miscellaneous HK charge is a gardener trolley repair: confirm equipment repair versus other expense. |
| 512007 | FO - Decoration | FO decoration: confirm supplies versus maintenance expense. |
| 516002 | LDY - Laundry Supplies | Laundry supplies: confirm cleaning materials versus operating supplies. |
| 548048 | PMC - ABT (AIR BAWAH TANAH) | Underground-water tax: confirm expense target; water expense and tax payable exist but no explicit tax expense account. |
| 202014 | A/P TAX - Pajak Reklame | Advertising tax payable: no explicit matching posting liability exists; do not map it to expense/prepayment. |
| 542011 | S&M - Sales Commission & Incentive | Sales commission/incentive: confirm sales expense versus travel agents commission/payroll. |

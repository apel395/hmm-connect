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

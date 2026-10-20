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

## Authorized seed and report validation (16 October)

The user authorized seeding and posting all source journals using registered COA,
then correcting through the app unpost/edit workflow. The seed script is
`scripts/seed_hotel_january_journals.py`. It defaults to dry run; `--apply --post`
creates and posts manual journals through `post_locked_journal`.

- One source register becomes one manual journal, with a stable external reference
  HOTEL-JAN2026-REG-<register>. Original dates, Debit L/Credit M, descriptions,
  source register/row evidence and existing column-F mappings remain traceable.
- The source credit excess Rp45,000 is intentionally posted as a one-sided manual
  journal. No contra, opening balance adjustment or balancing line is generated.
- DANA PROYEK source rows24372/24375/24376/24377/26448 now use registered
  Biaya Operasional Direksi750-100-104 following the user revision on 2026-10-20.
  This supersedes the provisional Piutang Direksi100-210-102 mapping. Source
  debit/credit directions and bank counterparts remain unchanged. The guarded
  `scripts/remap_hotel_january_dana_proyek.py` corrects existing posted journals
  atomically. Other BOD payroll rows retain their payroll account mapping.
- SWP and BOD resolve by exact active department names Swimming Pool / Board of
  Directur within Hotel, then validate their work-location links. Display codes
  010/011 are never assumed to be database IDs. No department or account is added.
- All remaining mappings use existing registered accounts. Broad registered
  accounts are used when no exact legacy category exists. Earlier review notes
  remain in the mapping JSON for finance; no additional account decision blocks
  seeding solely because a broader registered mapping needs later review.
- Possible reference overlaps with previous imports are skipped for comparison,
  not cloned or deleted. On the supplied snapshot there are9 such registers;
  expect3252 new journals including the one-sided source register, if the live
  departments and period remain valid and no new overlapping entries were added.
- Corrected app journals are never overwritten or automatically reposted on
  rerun. Existing stable identities require matching source-hash batch provenance.
- Source SHA is pinned. Current COA, scope, department links and period are checked
  again inside the transaction. PostgreSQL table locks serialize journal changes
  while duplicate evidence is checked and the atomic import/post runs. Failure
  rolls back all new journals, GL, source audit rows and batch changes.
- Actor is an active SYSTEM_ADMINISTRATOR. Pass --user-id, or the script selects
  the sole active administrator; with multiple administrators it prompts on a
  terminal for the audit actor ID. This is attribution, not a new approval.
- ImportBatch, ImportRow and activity snapshots retain source identity, raw
  amounts, original COA, mapped line values and import/posting actor. Zero-value
  rows remain in source audit evidence without creating zero-value journal lines.
- Journal/GL import does not manufacture AP/AR documents, stock movements, fixed
  assets, payments or opening balances. Those subledger reconciliation differences
  remain visible; source totals are not evidence those subledgers were migrated.

Run from an EC2 worktree linked to /opt/hmm-connect/.env:

```bash
/opt/hmm-connect/.venv/bin/python scripts/seed_hotel_january_journals.py \
  /opt/hmm-connect/scripts/xjurjan26.xls --apply --post
```

The JSON result defaults to /tmp/hotel-january-seed-result.json and records exact
created IDs, already-present entries, skipped references, totals and source
differences. `committed: true` plus the COMMITTED console message confirms the
DB commit. Application unpost is supported while its accounting period is open.


## Apply the revised Dana Proyek mapping

The user revised the provisional receivable mapping on 2026-10-20. Existing
posted journals 4417 (register 1153653) and 4660 (register 1153977) are corrected
with `scripts/remap_hotel_january_dana_proyek.py`. The default simulates and
rolls back; `--apply` commits both journals in one transaction. The command
requires exact original source identities/amounts, current journal-to-GL
agreement and the original Hotel scope. It unposts/reposts through the app
functions, so closed periods remain locked. Raw source data is unchanged;
normalized account mappings retain `original_account_id` and a revision marker,
with before/after audit evidence. Repeating a completed correction verifies
existing postings without recreating their GL.

The change increases NOP by Rp21,159,848, from the verified Rp69,292,329.66 to
Rp90,452,177.66 if other January activity is unchanged. The original report's
Rp89,089,502.88 still differs by Rp1,362,674.78 because it subtracts Jasa Giro
Rp681,337.39 instead of adding the recorded income. Changing an account mapping
without reversing amounts/bank directions cannot reproduce that subtraction.
The command does not change the seven bank-interest receipts or their signs.

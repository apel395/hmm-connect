# Item classification preparation — 2026-10-06

Authoritative input: local `scripts/item-classification-review-237.xlsx`, SHA-256
`7adc409f1e9873f3758d4db4d5d22e8b047773f5d2e5d87132705d9c0ceeacc0`.

`item_classification_rules_20261006.json` covers all 237 exact item identities.
The correction script uses this manifest by default. The previous 20261005
manifest remains available via `--rules-file`.

- 96 rules contain vetted STOCK or DIRECT_USE account mappings, including the
  previous 93 rules, two syrup products, and whole mature coconut.
- 141 rules retain their family/default and normalize the legacy groceries label
  where applicable. These rules preserve current treatment, all account IDs,
  tax, and market-item flags.
- 31 usage questions remain explicit. Receipt 661's Direct Use destination
  does not globally change its six remaining products' stocking defaults.
- BLENDER requires a capitalization policy and exact asset/expense mapping;
  its classification is rejected for review.

Source and manifest validation without DB access:

```bash
.venv/bin/python scripts/correct_item_classification.py --check-source-only
```

Read-only current-DB plan:

```bash
.venv/bin/python scripts/correct_item_classification.py --output /tmp/item-classification-20261006-plan.json
```

The dry run checks current identities, BUY/SELL separation, active catalogs,
posting accounts and historical stock/receiving. Missing subgroups are planned
and created only on explicit apply. Stock/treatment/account changes with posted
history remain deferred for a coordinated historical correction. It creates
no warehouse OUTs, journals, GL, taxes or opening balances.

Review the full plan before applying eligible changes with `--apply`. Applying
updates existing products with audit records and preserves product IDs/codes.
The report's `seed_ready` remains false while usage/policy or posted-history
reviews remain; partial eligible corrections are identified separately.
An output file records the proposed/results plan, not proof of transaction
commit: the terminal COMMITTED message is the transaction outcome.

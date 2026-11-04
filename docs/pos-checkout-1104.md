# Hotel F&B checkout presets and payment accounts

Requires additive migration `20261104_pos_checkout` after
`20261104_catering_billing`. It adds nullable checkout JSON to outlet policies
and sales; no existing configuration, transaction, journal, valuation or opening
balance is rewritten. The read-only check is
`PYTHONPATH=. python scripts/check_pos_checkout_1104.py`. Downgrade refuses to
remove saved policy or sale evidence.

## Settings and cashier flow

In **Settings → POS Settings**, choose Hotel location and F&B outlet. Finance
with existing `finance.manage` and `pos.view` can configure:

- Cash, Card and Bank Transfer: enable/disable each and explicitly choose its
  active debit-balance posting asset (cash/bank/clearing) account.
- Named discount presets: percentage or fixed IDR, amount/value and active flag.
  No example percentage, amount or account is automatically created or chosen.

Before an outlet policy is saved, existing global POS payment-account mappings
are displayed and used without modification. Saving creates an outlet-specific
policy. No global accounting setting or other outlet policy is overwritten.
All payment methods may be disabled intentionally; drafts can still be saved,
but no paid sale can settle until an enabled method is selected.

For Hotel paid POS, the cashier chooses a preset or **No discount**, rather than
typing a discount amount. Only enabled payment methods are selectable. The server
calculates the preset against the existing subtotal, applies the existing cap at
subtotal and preserves service-charge/PBJT calculation. Amounts use Decimal and
cent rounding. Zero-charge orders remain subject to existing posting rules;
this patch does not add complimentary-sale accounting.

Drafts record the selected preset and its terms; posted sales additionally record
the selected payment account and configuration version. Continuing a draft keeps
its invoice/order identity. Hotel order settlement from the Sales list directs
users to Continue / settle in the Register so choices are reviewed.

Versions prevent stale policy edits and order settlement. When Finance changes
settings, a cashier must refresh/review and save the draft with the current
version before settling a changed preset. A changed, inactive, foreign or forged
preset/payment selection cannot bypass the backend. Later policy changes do not
rewrite posted sale snapshots or journals. The existing sale/shift locks and
single-post guard remain; checkout policy reads lock its row during persistence
and settlement, serializing with Finance updates.

Scope is **Hotel F&B paid POS only**, matching the Restaurant issues #506/#507.
Catering service invoice pricing, discounts, AR creation/allocation and tax logic
are unchanged. No recipe/BOM, inventory consumption, new payment methods,
automatic tax rates, cash-balancing journal or opening adjustments are introduced.

## Validation

Regression coverage includes preset PBJT totals, fixed/percentage rounding,
Cash change/shift reconciliation, explicit Card posting account, rejected raw
amounts and disabled methods, missing/stale versions, changed presets, source
identity, duplicate posting, permission enforcement, invalid/inactive accounts,
unchanged posted snapshots, and stock/opening preservation. PostgreSQL migration
checks preserve existing sales and financial rows and guard destructive rollback.
Frontend tests cover selection instead of manual entry, nonactive method hiding,
forged selection rejection, settings save and existing order/refresh behavior.

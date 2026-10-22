# POS PBJT posting

PBJT-tagged SELL menus use their explicit `pbjt_rate`. Resolve the existing active credit-balance LIABILITY posting account through `POS_PBJT_PAYABLE_ACCOUNT` if mapped; otherwise use `200-400-100` (Hutang PBJT - Hotel dan Resto, Catering) from the supplied COA. `200-400-101` is electricity PBJT and must not receive menu tax. Do not create another account, infer a rate, or fall back to PPN. Missing or invalid mappings disable the affected menu with a reason.

New sales lines snapshot tax type, rate and PBJT account. Posting uses those snapshots, even if the Item Master changes later. PBJT is calculated on the item value after proportional document discount plus the saved service charge, rounded to cents. Existing legacy sales retain their saved tax figures and their original VAT account path. Explicit SELL PPN and PPh 23 profiles remain unavailable pending their own implementation.

For Rp100,000 plus PBJT10%, the immediate-payment POS journal debits the selected cash/bank account Rp110,000, credits revenue Rp100,000, and credits the existing PBJT payable account Rp10,000. Mixed legacy VAT and PBJT are posted separately. No warehouse, inventory, HPP, supplier invoice or opening balance is generated. As of `20261022_pos_ar_invoices`, `INVOICE` posts to customer AR; actual payment is recorded separately. The immediate-payment example above applies to retail `POS`.

Apply `20261022_pos_pbjt` on EC2, then run `scripts/check_pos_pbjt_1022.py`. The checker is read-only. The migration only adds tax snapshot columns; it does not revise historical transactions, balances or tax amounts.

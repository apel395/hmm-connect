# Fixed assets and amortization

## Categories
Use an active posting debit asset account from `100-600-*` or `100-900-*`. Ordinary land uses a Non-depreciable category with no useful life or depreciation posting accounts. Depreciable categories require useful life, an accumulated depreciation credit account and depreciation expense debit account. Policy is explicitly selected; no tax useful life is assumed. Category changes do not rewrite registered asset snapshots. Create a separate category to change asset account or depreciability after use.

## Register
BUY FIXED_ASSET items retain automatic unvalued PENDING_REGISTRATION registration. Completing a registration records actual acquisition cost/date, known quantity and organization. Opening accumulated depreciation can be entered as register history. This does not post or correct opening balances. Unknown quantities remain null. Existing invoice registrations retain their posted cost and now snapshot invoice quantity for new registrations. Receipt cost synchronization remains a separate source integration; this patch does not assume a cost from an Item Master reference price.

Capitalization lets finance select the capitalization and depreciation start dates. Activation without an acquisition journal is the default. Invoice/posted receiving sources and opening accumulated depreciation cannot post acquisition again. Dates must be in an open accounting period. Straight-line schedules start in the selected month if its first day, otherwise the next month; no daily prorating. Final month absorbs rounding to finish at residual value. Existing posted schedules are retained.

## Monthly posting
Create one depreciation run per business unit and work location, calculate, then post. Earlier outstanding months must be posted first. Generated journal/GL preserve department dimensions. Recalculate after source changes. Latest run can be unposted in an open period if no later depreciation, disposal or subsequent transfer prevents it. GL is removed precisely for that journal; journal remains VOID in history. Reposting creates one new active journal.

Amortization uses actual cost, start date and useful life. `100-400-*` prepaid costs can credit the same asset account; other intangible assets use an accumulated credit account. Tangible `100-600-*` and operating equipment `100-900-*` use Fixed Assets. Each Post Next action identifies its expected month counter. Schedule and journal history are available, as is Unpost Last with the same period and GL checks. Final period clears rounding. Old completed records with stranded remainders are reported by the checker, never silently corrected.

## Transfer and disposal
Transfer moves the whole asset register record, including its known quantity. By default gross cost and accumulated depreciation are reclassified from source to target organization. Finance can explicitly choose physical register-only transfer. Disposal/write-off posts removal of cost and accumulated depreciation, proceeds if any, and gain/loss. Posting dates cannot precede acquisition/capitalization or an already posted later depreciation month. Book value becomes zero; historical cost remains visible. Register totals exclude disposed/written-off/inactive records.

## Deployment
Apply `20261014_asset_policy` on EC2 before merging backend and UI feature branches. It adds explicit category depreciability, nullable non-depreciable policy fields, optional asset quantity and movement journal links. It does not reclassify assets, create postings or change balances. Run `scripts/check_fixed_assets_1014.py` for read-only evidence.

# Balance Sheet control

The comparison API returns `balance_control` for Balance Sheet reports:
assets, liabilities plus equity, difference, balance status, as-of date and
`COMPLETE_REPORT` basis. The equation is Assets − Liabilities − Equity.
The control uses the report's authorized organization and date scope, and all
ledger totals, even when display settings hide some rows or use KAP headers.

The page and KAP/detail print show a compact Balanced or Out of balance marker.
Excel includes total liabilities plus equity, status and numeric difference on
the summary and detail sheets. Status text accompanies color for accessibility.
A missing control during staged deployment is not displayed as Balanced.

No balancing journal, opening adjustment or automatic correction is created.
Current-year profit remains part of the existing earnings reconciliation; the
control reads the finished totals and does not add earnings again.
Department sheets reflect their own journal attribution. Opening balances have
no department and remain on the separate opening sheet rather than being
allocated to departments.

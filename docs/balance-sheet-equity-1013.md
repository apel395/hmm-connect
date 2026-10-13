# Balance sheet equity and presentation

Current-year earnings formerly appeared as a synthetic row named "Laba Ditahan
Tahun Berjalan (Current Year Retained Earnings)" alongside the actual equity
COA. The synthetic row had no account ID, so its frontend link opened P&L.

The report now keeps all real equity accounts and their identifiers. Residual
current-year profit/loss is included in the configured
`CURRENT_YEAR_EARNINGS_ACCOUNT` display row, once. Its evidence is provided as
`summary.earnings_reconciliation`: manual opening, posted equity movement,
profit/loss awaiting closing and the displayed balance. This is report
presentation only. No opening, journal, ledger or COA record is changed.

For example, opening equity 500 and unclosed profit 70 display as 570. Closing
posts 70 into equity and clears the residual P&L to zero; the same row still
shows 570. Reopening also preserves that total. If no valid closing account is
configured, residual P&L has the explicit label "Laba/Rugi Tahun Berjalan
(Belum Ditutup)" and does not pretend to be a stored COA account.

Real account and header drilldown opens GL with exact account IDs, date and
organization scope. The Equity detail control exposes the display breakdown.
Report preferences are saved per user and report, including date, period,
scope, budget, KAP, zero inclusion and executive/detail view. Explicit report
links take precedence and clear stale scope fields.

Executive balance sheet rows aggregate complete report values by financial
statement group and reconcile to the section totals. KAP printing uses a
portrait T summary without compulsory MTD/YTD comparison pages; detailed
printing retains comparison pages. Neither layout changes report totals.

Read production evidence from EC2:

```bash
.venv/bin/python scripts/check_balance_sheet_equity_1013.py --as-of 2026-09-30
# Optional organization scope:
.venv/bin/python scripts/check_balance_sheet_equity_1013.py --as-of 2026-09-30 --location 8
```

The check runs in a PostgreSQL READ ONLY transaction and prints the opening
records and posted equity journal lines with actor IDs. No migration is needed.

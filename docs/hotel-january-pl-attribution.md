# Hotel January P&L attribution

Hotel reports use the retained January import evidence to distinguish legacy
meanings that were combined into shared registered COA accounts. Postings and
opening balances are unchanged. Report amounts come from current posted journal
lines, not hardcoded source workbook totals.

| Legacy codes | Report presentation |
| --- | --- |
| 401101 / 401159 / 401301 / 401401 | Food Cost |
| 401102 / 401160 / 401402 | Beverage Cost |
| 401309 / 401602 | Other Cost |
| 512037 / 522023 / 532023 | Department operating expenses |
| 512050 / 514050 / 522050 / 532050 | Department-head Officer Check: operating expenses |
| 542050 / 544050 / 546022 / 548049 | Department-head Officer Check: overhead expenses |
| 591007 / 591050 | BOD deductions, below GOP |
| 602070 | Bank administration, below GOP |
| 301* registered room revenue codes | Room Sales |
| 303001 / 303004 / 304001 / 305001 | Food Revenue |
| 303002 / 304002 | Beverage Revenue |
| 303003 / 304003 / 305002 / 305009 | Miscellaneous Revenue |

Only the approved January source hash and its journal import identity qualify.
The saved batch, active row ordinal, current account, debit, credit and effective
dimensions must match. Different source files, edited lines, drafts and Catering
retain their current accounting classifications. Native BOD expense activity is
also shown below GOP. Overhead payroll and expenses follow actual department
attribution at the consolidated and department levels.

A source account split into several report categories has distinct presentation
keys. Drilldowns use those keys, so a shared COA is not shown twice in a selected
category. Legacy labels/codes are shown with the registered COA. The GL link opens
the full registered account ledger; it does not pretend that a report-only slice
is a separate accounting account. Retained original zeros remain available.

Comparisons use their own date ranges and current posted evidence. Budgets stay
in their registered COA classification; unallocated source-slice budgets remain
blank rather than being distributed. The approved owner-loan receivable mapping
stays outside P&L. Bank interest increases the final result below GOP.

The January P&L source places department-head Officer Check under each
department's other expenses, separately from Employee Meal in payroll. Although
both currently share `600-100-107 Makan Karyawan`, verified Officer Check import
lines are shown as expenses in page categories, drilldowns, department schedules
and Excel totals. Ordinary employee meals stay in payroll. The eight source
codes total Rp1,459,552 (Rp446,021 operating and Rp1,013,531 overhead). Reclassifying
the report slices preserves GOP, NOP and every journal/GL amount.

Run the read-only production check on EC2 with:

```bash
cd /opt/hmm-connect
.venv/bin/python scripts/check_hotel_january_report.py --as-of 2026-01-31 --location-id 8
```

It prints report categories, verified evidence count and the report-to-ledger
net comparison. It does not enforce an old spreadsheet total or write changes.

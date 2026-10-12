# Management report delivery — 10-12

P&L has Hotel, Project Catering and Consolidated scope options. The screen and
print preview show one statement, without departmental tables. Existing assigned
location restrictions apply server-side. Units are identified by their configured
Hotel/Catering names or codes, never fixed database IDs.

Excel starts with Summary (full statement, unit totals, department/location NOP
summary, balance control and split differences). It then has one sheet per Hotel
department or Catering location. Each sheet contains MTD and YTD comparisons.
Inactive departments with historical activity remain included. Unassigned
organizational amounts remain in the overall statement and are exposed as split
control differences; they are never redistributed.

Presentation: Revenue, HPP, operating payroll, operating expenses, GOI,
overhead payroll, overhead expenses, GOP/GOL, under expenses, unclassified
expenses, NOP. GOI subtracts HPP and operating costs. GOP additionally subtracts
overhead costs. NOP additionally subtracts below-GOP and unclassified costs.
These subtotals are presentation only; no posting or balancing entries are made.

Report Setup permits explicit expense-account category mappings, stored in the
existing accounting_settings table as PL_CATEGORY:<account id>. Existing COA
COST_OF_REVENUE and OPERATING_EXPENSE groups remain defaults; OTHER_EXPENSE
is presented below GOP. Unmapped expenses stay visibly unclassified. Display
checkboxes hide details only and never reduce complete-ledger totals.

Balance control compares assets against liabilities plus equity for the selected
unit/location, including manual opening balances and current earnings. It is
separate from profit and is not a manufactured balancing line.

No migration. Backend push deploys Lambda; main push deploys Vercel. EC2:

```bash
cd /opt/hmm-connect
git pull --ff-only origin backend
.venv/bin/python scripts/check_report_delivery_1012.py --as-of 2026-10-31
```

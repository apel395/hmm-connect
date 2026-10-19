# P&L mapping and Excel layout

The report uses the registered COA and the supplied Template PL REV structure.
Hotel is split by department. Catering uses PC LIPET for every location.
Summary is the first sheet, followed by the scoped detail sheets.

| Registered family | Default P&L presentation |
| --- | --- |
| 400-100-* | Hotel operating revenue |
| 400-110-* | Catering operating revenue |
| 500-100-* | Cost of revenue |
| 600-100-* | Payroll, including BPJS, casual workers and payroll tax |
| 700-500-* | Operating expenses or overhead in an overhead department |
| 750-100-100 | Head Office payroll |
| Other 750-100-* | Overhead expenses |
| Revenue with OTHER_REVENUE, including 760-100-100/101 | Nonoperating income, below GOP |
| Expense with OTHER_EXPENSE, including 760-100-* expenses | Under expenses |

Department classification recognizes Board of Directur as BOD. Explicit saved
expense category settings continue to override the defaults. Tax assets and
liabilities do not enter P&L because financial account type controls eligibility.
Account names alone never turn a tax or liability into revenue.

Rooms cost is an explicit summary line. The registered combined Food & Beverage
revenue stays combined, and Beban Pokok Langsung stays a distinct detail line.
The report does not fabricate Food/Beverage splits or allocate journal amounts.
Unmatched real activity remains visible. Nonoperating income adds to NOP without
increasing operating revenue or GOP. Executive expense cards exclude income.

Excel retains the template columns and schedules with compact Aptos typography,
navy headers, teal final totals, alternating detail rows, frozen headings and
account labels, typed numeric cells, percentage formats, landscape printing and
repeated column headings. The style XML is self-contained rather than copying
legacy extension namespaces. No source journals, opening balances or COA records
are changed by reading or exporting a report.

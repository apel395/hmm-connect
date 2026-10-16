# Profit & Loss Excel layout

The approved layout reference is `Template PL REV.xlsx`. Its sample amounts and
broken formulas are not imported into accounting.

Excel exports start with Summary. Consolidated exports also include separate
Hotel and Project Catering summaries. Detail sheets follow the actual authorized
Hotel departments and Catering locations, including historical attribution.
Revenue-producing departments precede other departments. Sheet names are unique
and limited to Excel's 31 characters.

Each sheet contains MTD current, budget, last month and last year, with matching
revenue percentages, followed by MTD variance and the YTD comparison columns.
The template's variance means current minus last month and is explicitly labeled
`Variance vs Last Month`. The on-screen comparison's budget variance retains its
existing definition. Missing budgets/comparisons are blank, not fabricated zero.

Department sheets use Revenue, Cost of Sales, Gross Profit, Payroll and Related
Expenses, Other Operating Expenses, GOI, Overhead Payroll, Overhead Expenses,
GOP, Other Deductions and NOP. Detail accounts remain in the P&L categories
configured in Finance Report Setup. All account detail, including zero accounts,
is exported regardless of the screen's header-only or zero-value setting.
The expense list follows the reference order where names match. Other registered
accounts remain visible rather than being dropped or assigned to an unrelated
template line.

Only separately identifiable P&L service charge accounts are shown in the service
charge lines. Combined payroll/revenue/utility accounts retain their full source
amount; this layout does not manufacture a finer allocation. Gross profit and
department profit include service charge revenue and deduct its payroll expense
once. Department/location residuals remain visible in the summary. Presentation
does not mutate accounts, budgets, source journals, opening balances or GL.

Room occupancy/ADR statistics and separate utilities are not inferred from
combined financial accounts. This change formats the financial figures already
supported by the report, and does not claim to populate unsupported template
statistics. The original template's division errors, broken references and sums
of monthly rates are not reused.

Print layout is landscape A3, one page wide with unconstrained vertical pages,
repeated rows 1–6, frozen headings/name column, numeric amounts and native percent
formats. The P&L drilldown opens centered, up to 1440px wide with internal scrolling
and sticky headings. Ledger links retain the selected dates and organization.

Validation: full backend regression suite, numeric export read-back, independent
profit/category reconciliation, missing comparison and service charge cases,
rendered synthetic exports, frontend build, and browser dialog checks.
No schema migration or data repair is required.

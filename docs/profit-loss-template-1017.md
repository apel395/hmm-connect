# Profit & Loss Excel layout

The approved layout reference is `Template PL REV.xlsx`. Its sample amounts and
broken formulas are not imported into accounting.

Excel exports start with Summary. Consolidated exports also include separate
Hotel and Project Catering summaries. Detail sheets follow the actual authorized
Hotel departments and Catering locations, including historical attribution.
Hotel department sheets use a stable order: Front Office, Food and Beverage,
Swimming Pool, Laundry, House Keeping, Admin and General, Accounting, Human
Resources, Sales and Marketing, Pomec, BOD, then other and unassigned departments.
This is a local adaptation of USALI operated-department/support-department ordering;
it does not allocate support costs or change account categories. Sheet names are unique
and limited to Excel's 31 characters.

Each sheet contains MTD current, budget, last month and last year, with matching
revenue percentages, followed by MTD variance and the YTD comparison columns.
The template's variance means current minus last month and is explicitly labeled
`Variance vs Last Month`. The on-screen comparison's budget variance retains its
existing definition. Missing budgets/comparisons are blank, not fabricated zero.

Department sheets use Revenue, Cost of Sales, Gross Profit, Payroll and Related
Expenses, Other Operating Expenses, GOI, Overhead Payroll, Overhead Expenses,
GOP, Other Deductions and NOP. Detail accounts remain in the P&L categories
configured in Finance Report Setup. All related account detail, including zero accounts,
is exported regardless of the screen's header-only or zero-value setting.
The expense list follows the reference order where names match. Other registered
accounts remain visible rather than being dropped or assigned to an unrelated
template line.

Only separately identifiable P&L service charge accounts are shown in the service
charge lines. Combined payroll/revenue/utility accounts retain their full source
amount; this layout does not manufacture a finer allocation. Gross profit and
department profit include service charge revenue and deduct its payroll expense
once. Unassigned postings retain their own detail sheet and remain in Summary totals. Presentation
does not mutate accounts, budgets, source journals, opening balances or GL.

Operating statistics are read from the separate monthly Statistics register.
The six accounts Finance created are recognized by their exact codes:

| Code | Report metric | Period calculation |
| --- | --- | --- |
| 900-100-100 | Room Available | Sum of monthly room-nights |
| 900-100-101 | Room Occupied | Sum of monthly occupied room-nights |
| 900-100-102 | Bookkeeping Rate | Latest rate, never summed |
| 900-100-103 | Number of Guest | Sum |
| 900-200-100 | Food Cover | Sum |
| 900-200-101 | Beverage Cover | Sum |

Report Setup has optional source overrides, a Room Saleable source and a Paid
Room Nights Sold source. Defaults do not write mappings or change COA records.
The original default Room Revenue source is 400-100-100; a different revenue
account or revenue parent can be selected for ADR. ADR requires an explicitly
selected paid-room source. Finance can select Room Occupied for paid rooms only
when that count excludes complimentary rooms. Bookkeeping Rate is separate.

Occupancy = occupied room-nights / available room-nights. ADR = Hotel room revenue
/ paid room-nights sold. YTD uses the cumulative numerator and denominator, not
an average or sum of monthly ratios. Room revenue uses the same scoped posted
financial data (and selected financial budget for budget ADR). Statistical budgets
come from the Statistics register and are not separate named budget versions.
The register stores monthly values: current-month statistics are the latest values
entered for that month, rather than a reconstructed daily history.

A location total takes precedence over its departmental component records for the
same metric, period and actual/budget field. A department-scoped report uses only
that department's records. Hotel room statistics and ADR never include Catering
room data/revenue even when the same COA is used. Food/beverage covers follow the
selected scope. Historical comparisons require recorded statistics; missing values
stay unavailable. Zero denominators and inconsistent units yield no calculated
ratio. Different currency pairs are never averaged or compared as a single rate.

Operating Statistics is removed from the P&L page and Summary Excel sheet.
Statistics remain available in the Statistics module, print and detail Excel sheets.
This does not post journals/GL, change opening balances, or seed any statistical
actuals or budgets. Separate utility/revenue/payroll detail still depends on real
source attribution. The template's division errors, broken references and sums of
monthly rates are not reused.

Print layout is landscape A3, one page wide with unconstrained vertical pages,
repeated rows 1–6, frozen headings/name column, numeric amounts and native percent
formats. The P&L drilldown opens centered, up to 1440px wide with internal scrolling
and sticky headings. Ledger links retain the selected dates and organization.

Validation: full backend regression suite, numeric export read-back, independent
profit/category reconciliation, missing comparison and service charge cases,
rendered synthetic exports, frontend build, and browser dialog checks.
No schema migration or data repair is required.

## Summary and related account corrections (2026-10-17)

Summary contains exactly the P&L page category/subtotal labels, in the same order,
without department repetitions, account detail or operating statistics. Each
Hotel department has its own detail sheet. Comparison and percentage columns
continue to use the supplied template; Excel variance remains explicitly
current minus last month, not the page's budget variance.

Zero Hotel revenue accounts in the registered `400-100` family are excluded from
Catering, and zero `400-200` Catering revenue from Hotel. Hotel room/F&B/laundry/
pool revenue follows exact registered codes; department-prefixed accounts follow
their named department. Generic shared or unknown accounts remain available.
Scoped posted evidence (including debit/credit cancellations) and any actual or
budget comparison override zero-account display defaults: real mispostings stay
visible. No accounting records or mappings are changed.

References: HFTP USALI Rooms Schedule 1, Food and Beverage Schedule 2, Other
Operated Departments Schedule 3, and undistributed operating departments:
- https://www.hftp.org/downloads/documents/usali/usali12_060624_rooms.pdf
- https://www.hftp.org/downloads/documents/annual-convention/ac24-pres-usali02.pdf
- https://iahfme.org/ws/media-library/e82a00a759b8fcec1483089be4a0890f/sig-meeting_usali_chrie2024.pdf

Catering location layout: Summary uses the same management totals; one detail sheet
per authorized project location. Use Catering contract/service revenue, food and
beverage HPP, operational payroll, operational expenses, project contribution,
overhead payroll/expenses, GOP and under expenses/NOP. No Rooms department or
room-specific statistics. Shared costs require recorded location attribution;
no automatic allocation from Hotel or Head Office. Retain real exceptions for
finance to correct rather than hide them.


Catering exports use the page's exact management rows with each related account
listed once under its category. Summary retains header/subtotal rows only.
Each location sheet includes its own actuals, budget and comparisons; no Hotel
Rooms schedule, room statistics, assumed service-charge totals or distribution
rows. Existing service-charge accounts, if any, remain ordinary detail counted
once. Consolidated workbooks dispatch Hotel department and Catering location
layouts separately. No cost allocation or account reclassification is implied.

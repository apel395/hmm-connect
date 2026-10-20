# Hotel support department P&L — 20 October 2026

## Purpose and report structure
Accounting, Admin and General, Human Resources and Board of Directors remain distinct source departments and Excel schedules. Accounting and HR operational support costs roll into the A&G summary bucket, without copying or allocating transactions between departments. BOD management costs can also be overhead; owner-specific costs are below GOP. NOP remains GOP minus under expenses plus non-operating income.

Account number identifies the nature of the expense. Department identifies who incurred it, not who processed or paid the document. HR processing a payroll batch does not move all hotel salaries into HR. No journal, account master, budget, department or GL record is rewritten by these presentation rules.

## Related zero accounts
The four support departments no longer repeat every unused expense COA. Defaults use the registered MMH account codes:

| Purpose | Codes | Default supporting schedules |
| --- | --- | --- |
| Payroll and employee benefits | `600-100-*` | All four; actual department determines the amount |
| Travel, stationery, communications, supplies, courier, depreciation, miscellaneous | `700-500-100/103/107/119/125/133/999` | All four |
| Recruitment, medical, housing, staff activities, training and uniforms | `700-500-101/110/128/129` | HR |
| Bank administration and cash over/short | `700-500-122/131` | Accounting |
| Legal/audit | `700-500-126` | Accounting and A&G; actual HR legal costs remain HR |
| Computer/software costs | `700-500-121` | Accounting and A&G |
| General management, hotel system, contract services and head-office administration | Relevant registered `700-500-*` and `750-100-*` | A&G |
| Director/owner expense | `750-100-104` | BOD |
| Non-operating financial income and related expense | `760-100-*` | Accounting, below GOP according to account type/group |

Repair, marketing, laundry and similar specialized zero accounts do not populate these four schedules. Their existing other-department behavior is retained. Explicit department-prefixed accounts keep their ownership. Unknown zero accounts remain in the full Hotel account catalogue; they are not assigned arbitrarily to all four schedules.

Actual posted activity, including debit/credit entries that net to zero, and nonzero comparison/budget evidence ALWAYS override zero-account defaults. Thus an incorrectly attributed building repair posted to HR remains visible there for investigation. No real cost is hidden to make a schedule appear normal.

## BOD classification
The BOD department tag alone no longer sends all expenses below GOP. Ordinary salaries and operational support expenses use overhead classification. Explicit director/owner expense COA `750-100-104`, and identifiable owner-expense descriptions, use UNDER_EXPENSE for Hotel. Explicit finance category settings retain precedence. Catering classification is unchanged.

Verified January import evidence retains exact legacy purposes: `591007` owner expenses and `591050` BOD complimentary checks remain below GOP. Legacy `602070` bank administration retains its established below-GOP source attribution; ordinary new bank administration keeps its normal operating-overhead classification. Loan/repayment balance-sheet accounts never become expense merely because the department is BOD.

## Excel and controls
Existing comparison columns, print layout and formula-based totals are retained. The four support schedules omit empty template expense slots with no related account. Relevant zero accounts and actual exceptions are still listed. The copied template footer 'Total Revenue' is corrected to 'TOTAL DEPARTMENT EXPENSES' on these cost-centre schedules. Actual revenue, if posted, is still visible, and separate non-operating income/expense sections retain the net-result calculation.

Regression checks verify expected zero lists, offsetting evidence, budget evidence, unchanged Catering, source-safe January attribution, formulas and summary = sum of department totals. These changes deploy to Lambda from backend. No schema migration or EC2 data correction is required.

## References
- HFTP, USALI evolution: Accounting/HR support schedules and A&G summary: https://www.hftp.org/downloads/documents/usali/resources/evolution-of-hotel-accounting.pdf
- HFTP, USALI 12 presentation, HR recruitment/employee relations: https://www.hftp.org/downloads/documents/usali/usali12_presentation.pdf
- HFTP, USALI FAQs, owner expenses in non-operating income/expenses: https://www.hftp.org/downloads/documents/usali/usali_faqs.pdf

These references inform the design. MMH's approved chart and historical source evidence determine the exact implementation; this is not a claim that the entire custom report is an unmodified USALI statement.

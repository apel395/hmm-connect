# Hotel Accounting and A&G responsibility reports

For Hotel P&L reporting, Accounting includes the legacy postings recorded under
Admin and General, plus postings recorded explicitly under Accounting. Human
Resources retains its own recorded costs. Admin and General is the subtotal of
these two schedules. Board of Directors is separate, including in the workbook's
overhead summary.

The rule uses uniquely registered department names within the Hotel unit; it
does not assume production IDs. Missing or ambiguous Accounting/A&G setup falls
back to the recorded department. Catering and the balance sheet remain exact
recorded-dimension reports.

Actuals, budgets, prior month/year comparisons and verified January import
attribution use the same source scopes. A&G is flagged `is_department_rollup`;
split controls and workbook summary totals exclude it when summing leaf
departments. Its separate detail sheet remains available. Relevant zero
accounts for the subtotal include both Accounting and HR account families.

The API disables scope expansion for a department-restricted login. Existing
unit/location access applies to all reads. Rollup account drill-down supplies
the original source department links rather than linking the aggregate to a
single incorrect department ledger.

No migration, EC2 script, journal reclassification or balance correction is
required. Source journals, General Ledger and opening balances are unchanged.

Regression coverage includes actual/budget/comparison reconciliation, workbook
cached totals and formulas, January import evidence with request caching,
department access, Catering isolation and exact balance-sheet scope.

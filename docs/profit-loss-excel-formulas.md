# P&L Excel totals

Hotel, Catering and consolidated exports retain their existing report layouts and monetary values. Monetary total and subtotal cells now contain native Excel formulas referencing the actual emitted detail rows. Extra account rows are included before their subtotal, so inserting real account evidence does not shift a fixed template reference onto the wrong cell.

Department gross profit subtracts cost of sales from revenue; its operating result subtracts payroll (including any separate service-charge distribution) and other expenses. Summary GOP deducts operating and overhead costs once. NOP references GOP minus Total expenses below GOP. That subtotal equals under expenses minus all nonoperating income, including January Hotel Jasa Giro. The same signed contributions appear in page drilldowns. Department and Catering totals use the same bridge; costs included in GOP are not deducted twice.

Missing comparisons remain blank. Formulas include numeric cached results so previews and data-only readers retain the same values before Excel recalculates. The workbook requests automatic recalculation on opening. Formula text comes only from server-selected cell references; account names remain literal strings.

Editing an exported workbook changes that workbook only. It does not update journals, GL, opening balances, budgets, approval states or the application's report values.

## January 2026 investigation

The supplied January source, approved account mapping and read-only production account output differ by these missing posted net expenses:

| COA | Expense | Source minus posted |
| --- | --- | ---: |
| 700-500-104 | Pest control | 4,500,000 |
| 700-500-107 | Telephone / communication | 6,771,287 |
| 700-500-140 | Maintenance Hotel System (IHS) | 1,500,000 |
| 700-500-141 | Contract service | 2,695,917 |
| Total | | 15,467,204 |

The read-only output also shows the matching accrued-expense documents as VOID: journal 1430 (HK, 13,300,917), 1431 (FO, 666,287), and 1432 (A&G, 1,500,000). The three accruals were subsequently restored through a guarded correction. The approved Dana Proyek mapping was revised to the registered BOD expense account with a separate correction command. This export change does not modify journals or GL. Jasa Giro remains income in both ledger and report. The corrected layout subtracts income from under expenses, and report NOP reconciles directly to ledger profit.

Validation covers formula dependencies and cached values, edits flowing from detail through GOP/NOP, blank budgets, extra accounts, service charges and combined Hotel/Catering workbooks. The provided full January source is replayed only in an isolated database; it is never used to overwrite production values during export.

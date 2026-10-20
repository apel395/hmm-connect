# General Cashier and petty cash — 20 October 2026

## Workflow
General Cashier handles direct revenue receipts, direct operating-expense payments and cash/bank transfers. Supplier invoice settlement remains in Payments; customer invoice settlement remains in Customer Payments. There is no second AP/AR allocation flow here.

Petty Cash Usage supports:
1. Replenishment / transfer in: debit the selected petty-cash account, credit the funding cash/bank account.
2. Expense/payment: debit the selected expense account, credit petty cash.
3. Transfer out / return: debit the destination cash/bank account, credit petty cash.

Replenishment and return are internal cash transfers, not revenue or expense. They affect each account's physical cash book but not operating cash-flow totals. Spending recognizes expense once. Opening balances are never generated or adjusted by this flow. A real negative book balance is shown, not corrected automatically.

## Draft, post and void
Create saves a draft without GL. Draft editing uses PATCH on the same journal ID and retains the document number. Two source lines are replaced inside that draft; there is no new payment or journal on save. Metadata and before/after values are audited. Closed periods block creation, editing and posting through the existing fiscal-period controls.

Post revalidates active cash/expense/revenue account roles, balanced source structure and organization. The validation also runs when posting from Journals, so that route cannot bypass the cashier source controls. Existing ledger rows on a draft block another post. A repeat POST against an already posted cashier entry returns its existing state without duplicating GL.

Void is for drafts and records its time/audit. Posted entries cannot be edited/voided through these endpoints. Existing administrator-controlled journal unposting remains the route to reopen a posted journal; only after successful unposting may its draft be corrected and reposted.

## Access and UI
Finance view permission reads the book; finance manage creates, edits, posts and voids. Server-side location, unit and assigned department scope applies to cashier listing/details/actions and cash-account balances/activity. Cashier source lines must retain the header organization when posted.

General Cashier and Petty Cash Usage now have From/To dates, refresh and draft edit actions. Print uses the same date range. Replenishment labels identify the receiving cash account and funding bank/cash account. Create and edit recovery keys are separate, preventing a recovered edit from becoming a new draft.

Existing SELL catalogue/code/treatment tests and purchasing creator timestamp/print-count tests were rerun. This release does not seed selling items, configure outlets or upload signature assets; setup remains deferred by the user.

## Deployment and checks
Backend deploys to Lambda from backend; UI deploys through main/Vercel. No schema migration, EC2 command or production balance correction is required.

Regression tests cover replenish → spend → return, exact account balances, one expense recognition, repeat posting, same-ID draft editing, closed periods, account-role revalidation through both post routes, organization restrictions and void protection. These tests use isolated databases; they do not post production test transactions.

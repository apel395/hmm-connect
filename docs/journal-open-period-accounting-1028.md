# Open-period journal accounting

No migration is required. Keep `DRAFT`, `POSTED`, and `VOID` statuses.

## Recognition and reporting

Financial reads use Journal Lines once, not a union with the physical General Ledger cache. Existing POSTED history remains visible. An open-period DRAFT contributes only when it has a header location, valid active financial posting accounts, one positive side per line, matching explicit organization dimensions, and equal positive debit/credit totals. Missing line dimensions inherit the header. VOID, incomplete, zero-value and unbalanced DRAFT journals do not contribute.

Trial Balance, GL, P&L, Balance Sheet, Cash Flow and reconciliation share this rule. Finalizing a recognized DRAFT changes lifecycle status and writes the physical GL cache without adding a second reporting contribution. Existing one-sided POSTED manual journals remain real accounting differences. The existing explicit manual-post exception is retained; automatic closing refuses unbalanced drafts.

## Source documents

Posted receiving with a recognized DRAFT receiving journal can support invoice verification. The verified invoice's complete DRAFT journal makes it eligible for payment without manual journal posting. Source statuses remain separate from accounting recognition.

AP accounting movement and reconciliation include recognized verified invoices and recognized approved payments/adjustments. Actual source settlement caches (`paid_amount`, allocations, bank funding) change only through existing settlement workflows. An approved payment with a complete journal is therefore provisional accounting movement before settlement finalization; no paid cache is automatically overwritten.

Reopening a verified invoice retains its journal identity but clears its obsolete DRAFT lines, with an audit snapshot. Re-verification rebuilds that same journal. Accounted dependent payments/adjustments block invoice withdrawal. Source-owned journals must be corrected through their source module.

## Closing and reopening

Closing holds the period lock, validates all drafts, finalizes them once, and creates existing dimension-scoped closing entries. A savepoint rolls back all these steps if any later validation fails. Existing POSTED journals remain POSTED. Manual unbalanced drafts and source dependency failures block closing with errors.

Closed periods reject journal edits, voids, posting and unposting. Reopening requires the existing permission and a recorded reason, voids only audited system closing entries, and leaves operational journal statuses unchanged. Reclosing generates current closing evidence without duplicating operational journals. Existing-date corrections are controlled by period openness, independently from the switch for creating new backdated documents.

Opening balance input is never changed, converted into a journal or silently balanced.

## Verification and rollout

Regression coverage includes financial read consistency, invalid drafts, edit/finalize behavior, close/reopen/reclose, rollback on late failure, role permissions, receiving verification, AP payment eligibility and double-settlement protection. Tests use disposable SQLite databases; PostgreSQL concurrent lock behavior still requires staging verification. No production financial data is used or rewritten by this patch.

The journal feature PRs must remain unmerged until approved. Merging backend deploys Lambda; merging frontend deploys Vercel.

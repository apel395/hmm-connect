# Purchasing print-attempt and PDF-download audit

Supported documents: Purchase Requisition, Market List, Purchase Order and Receiving Report, including linked-document previews. Purchasing list/report print controls and expected-receiving reports also record print attempts. Existing warehouse document tracking remains compatible.

Opening or refreshing a preview is read-only. Clicking Print records a **print attempt**, not a confirmed physical print. Cancelling the browser dialog still leaves that attempt in history. A browser cannot tell the app whether paper printed, how many printer copies were selected, or whether the user chose Save as PDF. That native Save as PDF remains a print attempt.

The explicit Download PDF button on purchasing document previews records a separate **PDF download request**. It generates a real PDF containing the current document rows, totals, notes, creator/approver names and dates, logo and signature images. A browser/device file write is not independently confirmed by the server. Download requests do not increment the print counter.

Each event records the document number, actor snapshot, UTC time (displayed in WIB), request UUID, channel, content revision and sequence. Repeated request UUIDs return their original stamp without incrementing counters; source-row locking serializes simultaneous document requests. Report requests use an existing transactional sequence row and carry a hash of the rendered report snapshot. Report counters/history are per user; document counters are shared among authorized document viewers. Existing PRINT audit records are retained and included.

Document content and approval decisions determine the revision hash. A new document preview carries this hash; a stale preview is rejected if the source changed before printing/downloading. Revisions here mean distinct content versions recorded by this print audit, not a new accounting document status. Print/PDF actions never modify source quantities, approvals, stock, journals, GL or opening balances.

Print history is available in the document's Activity History (click the print/PDF counts to filter), and through GET /document-events/{kind}/{id}/print-history. The print stamp contains the attempt/download sequence, revision, actor and date/time. Closing the preview refreshes the source document's activity history.

Browser Ctrl/Cmd+P is routed through tracked preparation on purchasing print pages and purchasing lists/reports. Native browser-menu printing is recorded through beforeprint on a best-effort basis: browsers do not allow the app to pause that menu's rendering while a network audit request completes. Application print/PDF buttons wait for a successful audit request and refuse stale/unrecorded output. Native afterprint never marks physical printing successful.

No migration is required. AuditLog and DocumentSequence are reused. Backend must be released before frontend; no EC2 worker changes are needed. Regression coverage includes counters, retries, original-stamp replay, revision mismatch, view/location permissions, report targets, actual PostgreSQL concurrency and real Chromium PDF generation. Keep both feature PRs unmerged until approved.

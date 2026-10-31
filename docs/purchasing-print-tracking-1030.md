# Purchasing print tracking

The shared AuditLog tracks print attempts and explicit PDF download requests separately. Viewing previews does not increment either counter. Application print buttons wait for the audit event; native browser-menu printing is best effort because browsers cannot await the audit call before rendering. afterprint does not prove physical printing.

PR/ML/PO/RR source-row locks serialize counts and request UUIDs make retries idempotent. Replaying an earlier UUID returns that event's original sequence even after later prints. Print and PDF requests record source content revisions, user identity and UTC time; stale previews are rejected. PDF downloads do not increment print counts. Historical PRINT rows are retained.

Purchasing report targets use existing DocumentSequence row locks and per-user audit history. They store a client-rendered snapshot hash, not report data. Expected-receiving single-PO requests also enforce the source PO location scope. Document history enforces existing view and location permissions.

No database migration, EC2 worker update or financial-data change is required. POST /document-events/{kind}/{id}/print accepts request_id UUID, action PRINT_DIALOG/PDF_DOWNLOAD, expected_revision and report snapshot_hash. GET /document-events/{kind}/{id}/print-history returns counters, current source revision and up to 100 recent events. physical_print_confirmed is always false.

Tests: test_purchasing_print_tracking_1030.py covers semantics and permissions; test_purchasing_print_concurrency_1030.py uses disposable PostgreSQL to verify both idempotency and concurrent sequencing for document and report targets. Companion frontend includes a real Chromium PDF-generation check.

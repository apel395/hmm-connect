# Async Bulk Journal Import — PostgreSQL queue on existing EC2 worker

Journal Bulk Import uses the same EC2 service that generates asynchronous XLS
exports. The API no longer sends AWS SSM Run Command and does not need network
access to the SSM public endpoint or a paid SSM Interface VPC Endpoint.

## Current runtime flow

1. Frontend creates a JOURNAL_BULK_IMPORT batch and immediately saves its ID in
   per-user session storage. Reopening/refreshing the form resumes that batch.
2. Lambda returns a private S3 presigned PUT URL. The browser uploads XLSX/CSV.
3. Frontend marks the upload complete; the API verifies the object in S3.
4. POST `/journal-imports/{id}/start` atomically records QUEUED in PostgreSQL
   and returns HTTP 202. It **does not call SSM**.
5. The existing `hmm-connect-export-worker.service` polls journal imports every
   10 seconds (exports remain polled at their configured interval).
6. The worker atomically claims QUEUED -> PROCESSING, downloads the S3 object
   and validates it. It records VALIDATED, error rows, preview and audit data.
7. The user reviews the preview and confirms "Import Valid as Draft" or
   "Import & Post Valid". POST `/journal-imports/{id}/confirm` durably stores
   import_mode=DRAFT or POST and atomically records IMPORT_QUEUED.
8. Worker claims IMPORT_QUEUED -> IMPORTING, imports valid documents separately,
   then records IMPORTED or IMPORTED_WITH_ERRORS.
9. Each document_number is one journal; debits/credits must balance per document.
   Posting uses the normal journal/GL path, not an alternative accounting path.

Only one runner can claim a batch, even during transition while the legacy
S3-triggered Lambda/SSM path still exists. The claim is a conditional database
UPDATE; a losing worker exits without touching rows or GL.

## Limits and safety

- Maximum 5,000 spreadsheet rows and 500 journal documents per batch.
- Start/confirm are idempotent; retries must not create new jobs.
- Confirmed DRAFT/POST mode is stored before the worker starts and cannot be
  silently switched after a confirmation.
- Worker failure marks FAILED. Do **not** automatically requeue a failed or
  interrupted IMPORTING batch: earlier documents may already be committed.
  Inspect ImportRow statuses, created JournalEntry records and audit evidence
  before any manual retry. Do not blindly upload/confirm the same file.
- Partial validation is separate from any journal, payment or GL posting.
- No new tables, schema migration, queues, services, instances or paid endpoints
  are needed. S3 storage and existing EC2/PostgreSQL resource usage remain.

## Safe production rollout (order matters)

1. Merge backend PR after passing CI. Do **not** disable the old S3 event yet.
2. On the existing EC2 checkout, update to the merged `backend` revision,
   ensure `requirements-worker.txt` is installed and restart only the worker:
   ```bash
   cd /opt/hmm-connect
   git fetch origin backend
   git checkout backend
   git pull --ff-only origin backend
   .venv/bin/python -m compileall -q app/scripts/export_worker.py app/scripts/journal_import_worker.py
   sudo systemctl restart hmm-connect-export-worker.service
   sudo systemctl status hmm-connect-export-worker.service --no-pager
   sudo journalctl -u hmm-connect-export-worker.service -n 30 --no-pager
   ```
3. Verify the worker log says it polls the journal import queue.
4. Verify the deployed API is the merged backend revision. Backend deployment to
   Lambda is handled by the existing backend GitHub Actions workflow.
5. On a **small fresh batch**, verify DRAFT -> UPLOADED -> QUEUED -> PROCESSING
   -> VALIDATED. Then confirm Draft and verify IMPORT_QUEUED -> IMPORTING
   -> IMPORTED, with exactly one journal per document and no GL posting.
6. Only after the new polling path works, disable/remove **only** the S3
   notification that invokes `hmm-connect-journal-import-trigger` on prefix
   `journal-imports/`. Inspect the bucket notification configuration first.
   Do not delete unrelated S3 event notifications or the shared S3 bucket.
7. Keep the Lambda trigger until the rollout is verified; the conditional claim
   prevents duplicate processing while both are present.

## Monitoring and troubleshooting

```bash
sudo journalctl -u hmm-connect-export-worker.service -f
```

A missing `worker_command_id` is **normal** for the database queue; SSM is not
used for new jobs. The durable evidence is `import_batches.status`,
`worker_started_at`, `worker_completed_at`, and linked `import_rows`.

Batch #153 (2026-11-17) was validated successfully before migration and was
not imported at the time of investigation. Existing VALIDATED batches remain
reviewable/confirmable using the new worker after deployment.

## IAM and hosting

Existing EC2 role needs `s3:GetObject` on `journal-imports/*` and normal
PostgreSQL access. The API still needs S3 permissions to sign URLs/head objects.
It no longer needs `ssm:SendCommand` for **journal imports**; other workflows
such as exports might still require SSM until separately migrated. Do not
remove their permissions without checking those consumers.

EC2 service installation/update follows `scripts/setup_export_worker.sh` and
`requirements-worker.txt`. The API Lambda and worker use the same DB.

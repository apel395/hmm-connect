# Async Bulk Journal Import

Bulk Journal Import keeps spreadsheet parsing off Lambda.

## Runtime flow

1. Journal page creates a JOURNAL_BULK_IMPORT batch through Lambda.
2. Lambda returns an S3 presigned PUT URL.
3. Browser uploads XLSX/CSV directly to private S3.
4. Browser marks upload complete.
5. Lambda calls SSM AWS-RunShellScript on the existing EC2 worker.
6. EC2 runs: `.venv/bin/python -m app.scripts.journal_import_worker --job-id <id>`.
7. EC2 downloads the file from S3 and uses openpyxl for XLSX parsing.
8. Worker validates the entire batch before creating journals.
9. Each document_number becomes one Journal Entry; repeated document_number rows become its lines.
10. DRAFT journals remain drafts. POSTED rows use the same journal posting path as the Journal page, including General Ledger creation.
11. ImportBatch and ImportRow retain the import audit trail.

## Spreadsheet format

Required: document_number, posting_date, account_code, debit, credit.

Recommended: description, reference_type, reference_id, business_unit_code, department_code, location_code, line_description, supplier_code, external_reference, status.

Rules:
- Repeat document_number for every line of one journal.
- Every journal must balance.
- Every account must be an active posting COA.
- Business unit and location must resolve to active master data.
- Location access is enforced for the importing user.
- Department and supplier are optional.
- Status is DRAFT or POSTED; default is DRAFT.
- Existing journal document numbers are rejected.
- The worker validates the full batch before writing journals.
- Maximum 5,000 spreadsheet rows and 500 journal documents per import.

## AWS permissions

Existing export worker settings are reused: EXPORT_EC2_INSTANCE_ID, EXPORT_WORKDIR, EXPORT_PYTHON_BIN, EXPORT_S3_BUCKET or S3_BUCKET, and AWS_REGION.

Lambda needs ssm:SendCommand and s3:PutObject on journal-imports/*.
EC2 needs s3:GetObject on journal-imports/*.

Policy templates:
- infra/aws/lambda-export-policy.json
- infra/aws/ec2-export-policy.json

## S3 browser upload

Because the browser uploads directly to S3, configure bucket CORS for the production frontend origin and allow PUT with the Content-Type header. Keep Block Public Access enabled.

## Lambda dependency rule

openpyxl remains worker-only. The Lambda deployment workflow removes app/scripts/journal_import_worker.py and rejects spreadsheet-parser dependencies/imports in the Lambda build.

## EC2

The existing worker environment installs requirements-worker.txt, which contains openpyxl.

Production invocation is performed by Lambda through SSM:

`.venv/bin/python -m app.scripts.journal_import_worker --job-id <id>`
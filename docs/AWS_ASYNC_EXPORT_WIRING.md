# AWS Async XLS Export Wiring

This feature keeps XLS generation off Lambda. Lambda creates an export job and calls AWS Systems Manager Run Command. EC2 generates the workbook, uploads it to private S3, and the API returns a short-lived presigned download URL when the frontend polls the job as READY.

## Runtime flow

1. Frontend POSTs `/api/v1/exports`.
2. Lambda inserts `export_jobs` with `PENDING`.
3. Lambda calls `ssm:SendCommand` for the configured EC2 instance.
4. Lambda immediately returns HTTP 202 with `job_id`.
5. EC2 executes `python -m app.scripts.export_worker --job-id <id>`.
6. Worker updates the job to `PROCESSING`, generates XLSX, uploads it to S3, then marks it `READY`.
7. Frontend polls `GET /api/v1/exports/{job_id}`.
8. Lambda creates a short-lived S3 presigned GET URL and the browser downloads directly from S3.

## GitHub production variables

Configure these in the `production` GitHub environment before deploying the backend branch:

- `AWS_REGION` — region containing Lambda, EC2, SSM and S3.
- `AWS_LAMBDA_FUNCTION_NAME` — existing HMM Connect Lambda function.
- `EXPORT_EC2_INSTANCE_ID` — SSM-managed EC2 instance ID, for example `i-0123456789abcdef0`.
- `EXPORT_S3_BUCKET` — private bucket that receives generated exports.
- `EXPORT_WORKDIR` — optional; defaults to `/opt/hmm-connect`.
- `EXPORT_PYTHON_BIN` — optional; defaults to `.venv/bin/python`.
- `EXPORT_S3_PREFIX` — optional; defaults to `exports`.

The existing `AWS_LAMBDA_DEPLOY_ROLE_ARN` secret remains unchanged. The deploy workflow merges the export variables into the Lambda environment instead of replacing existing Lambda variables.

## Lambda execution role

Attach the permissions represented by `infra/aws/lambda-export-policy.json` after replacing placeholders. Lambda needs:

- `ssm:SendCommand` for `AWS-RunShellScript` and only the export EC2 instance.
- `s3:GetObject` for only the export prefix, because presigned downloads are signed with Lambda's execution credentials.

If the S3 bucket uses a customer-managed KMS key, also grant the minimum KMS permissions required by the bucket/key policy.

## EC2 instance role

The EC2 instance must be registered with Systems Manager. Its instance profile should include AWS managed policy `AmazonSSMManagedInstanceCore` plus the restricted upload policy represented by `infra/aws/ec2-export-policy.json`.

The export worker only needs `s3:PutObject` and `s3:AbortMultipartUpload` on the configured export prefix. It does not need public S3 access.

Check the SSM agent on EC2:

```bash
sudo systemctl status amazon-ssm-agent
```

Then confirm the instance is visible to Systems Manager from an AWS CLI session with appropriate read permission:

```bash
aws ssm describe-instance-information \
  --filters Key=InstanceIds,Values=<EXPORT_EC2_INSTANCE_ID>
```

## EC2 worker installation

The code at `EXPORT_WORKDIR` must contain the same backend revision as Lambda and have database connectivity to PostgreSQL.

From the backend checkout on EC2:

```bash
sudo bash scripts/setup_export_worker.sh /opt/hmm-connect python3
```

The setup installs `requirements-worker.txt`, which contains `openpyxl`, and validates database connectivity plus export settings.

Required EC2 environment values:

```bash
AWS_REGION=<region>
EXPORT_S3_BUCKET=<private-export-bucket>
EXPORT_S3_PREFIX=exports
EXPORT_TMP_DIR=/tmp/hmm-connect-exports
DATABASE_URL=<existing-postgresql-url>
SECRET_KEY=<existing-backend-secret>
```

Keep these in the existing protected backend environment configuration used on EC2; do not commit production secrets.

## S3 bucket

The export bucket should remain private with Block Public Access enabled. Apply `infra/aws/export-bucket-lifecycle.json` to remove generated objects after one day:

```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket <EXPORT_S3_BUCKET> \
  --lifecycle-configuration file://infra/aws/export-bucket-lifecycle.json
```

The lifecycle template targets the `exports/` prefix. If `EXPORT_S3_PREFIX` is changed, update the lifecycle prefix to match.

## Database migration

Before using the endpoint, apply the migration containing the `export_jobs` table:

```bash
alembic upgrade head
```

## End-to-end verification

After deployment:

1. Confirm Lambda environment contains `EXPORT_EC2_INSTANCE_ID` and `EXPORT_S3_BUCKET`.
2. Confirm EC2 is online in Systems Manager.
3. Trigger a product export from the Product Master UI.
4. Confirm the first API response is HTTP 202 and contains a `job_id`.
5. Confirm an SSM command is created without Lambda waiting for XLS generation.
6. Confirm the database transitions `PENDING -> PROCESSING -> READY`.
7. Confirm the object is private in S3 under `exports/<user_id>/<job_id>/...xlsx`.
8. Confirm the browser downloads via the returned presigned URL.
9. Confirm failed worker executions transition the job to `FAILED` and expose the worker error through the job status endpoint.

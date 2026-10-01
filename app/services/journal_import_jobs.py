import boto3

from app.core.config import settings


def _bucket() -> str:
    bucket = settings.EXPORT_S3_BUCKET or settings.S3_BUCKET
    if not bucket:
        raise RuntimeError("EXPORT_S3_BUCKET or S3_BUCKET must be configured")
    return bucket


def trigger_journal_import_job(
    job_id: int,
    *,
    mode: str = "validate",
    post_valid: bool = False,
) -> str:
    if not settings.EXPORT_EC2_INSTANCE_ID:
        raise RuntimeError("EXPORT_EC2_INSTANCE_ID is not configured")
    if mode not in {"validate", "import"}:
        raise ValueError("Unsupported journal import worker mode")

    command = (
        f"cd {settings.EXPORT_WORKDIR} && "
        f"{settings.EXPORT_PYTHON_BIN} -m app.scripts.journal_import_worker "
        f"--job-id {int(job_id)} --mode {mode}"
    )
    if post_valid:
        command += " --post-valid"

    ssm = boto3.client("ssm", region_name=settings.AWS_REGION or None)
    response = ssm.send_command(
        InstanceIds=[settings.EXPORT_EC2_INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [command]},
        Comment=f"HMM Connect journal import {job_id} ({mode})",
        TimeoutSeconds=settings.EXPORT_COMMAND_TIMEOUT_SECONDS,
    )
    return response["Command"]["CommandId"]


def journal_import_object_key(user_id: int, job_id: int, filename: str) -> str:
    safe_name = filename.replace("\\", "/").split("/")[-1].strip() or "journal-import.xlsx"
    safe_name = "".join(
        character if character.isalnum() or character in "._-" else "_"
        for character in safe_name
    )
    prefix = settings.JOURNAL_IMPORT_S3_PREFIX.strip("/")
    return f"{prefix}/{user_id}/{job_id}/{safe_name}"


def presigned_upload_url(*, user_id: int, job_id: int, filename: str, content_type: str) -> tuple[str, str]:
    key = journal_import_object_key(user_id, job_id, filename)
    s3 = boto3.client("s3", region_name=settings.AWS_REGION or None)
    url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": _bucket(), "Key": key, "ContentType": content_type},
        ExpiresIn=settings.JOURNAL_IMPORT_UPLOAD_URL_EXPIRES_SECONDS,
        HttpMethod="PUT",
    )
    return key, url


def head_journal_import_object(key: str) -> dict:
    s3 = boto3.client("s3", region_name=settings.AWS_REGION or None)
    return s3.head_object(Bucket=_bucket(), Key=key)

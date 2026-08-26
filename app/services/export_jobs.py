import boto3

from app.core.config import settings


def trigger_export_job(job_id: str) -> str:
    if not settings.EXPORT_EC2_INSTANCE_ID:
        raise RuntimeError("EXPORT_EC2_INSTANCE_ID is not configured")

    ssm = boto3.client("ssm", region_name=settings.AWS_REGION or None)
    command = f"cd {settings.EXPORT_WORKDIR} && {settings.EXPORT_PYTHON_BIN} -m app.scripts.export_worker --job-id {job_id}"
    response = ssm.send_command(
        InstanceIds=[settings.EXPORT_EC2_INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [command]},
        Comment=f"HMM Connect XLS export {job_id}",
        TimeoutSeconds=settings.EXPORT_COMMAND_TIMEOUT_SECONDS,
    )
    return response["Command"]["CommandId"]

import boto3
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.export_job import ExportJob
from app.models.user import User
from app.services.export_jobs import trigger_export_job


router = APIRouter(prefix="/exports", tags=["Exports"])
SUPPORTED_EXPORTS = {"products"}


class ExportRequest(BaseModel):
    export_type: str


def _serialize(job: ExportJob) -> dict:
    payload = {
        "job_id": job.id,
        "export_type": job.export_type,
        "status": job.status,
        "filename": job.filename,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
    }
    if job.status == "READY" and job.file_key:
        bucket = settings.EXPORT_S3_BUCKET or settings.S3_BUCKET
        if not bucket:
            raise HTTPException(status_code=500, detail="Export S3 bucket is not configured")
        s3 = boto3.client("s3", region_name=settings.AWS_REGION or None)
        payload["download_url"] = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": job.file_key,
                "ResponseContentDisposition": f'attachment; filename="{job.filename or "export.xlsx"}"',
            },
            ExpiresIn=settings.EXPORT_DOWNLOAD_URL_EXPIRES_SECONDS,
        )
    return payload


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_export(
    data: ExportRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    export_type = data.export_type.strip().lower()
    if export_type not in SUPPORTED_EXPORTS:
        raise HTTPException(status_code=400, detail=f"Unsupported export type: {export_type}")

    job = ExportJob(user_id=current_user.id, export_type=export_type, status="PENDING")
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        command_id = trigger_export_job(job.id)
    except Exception as exc:
        job.status = "FAILED"
        job.error_message = f"Unable to trigger export worker: {exc}"
        db.commit()
        raise HTTPException(status_code=503, detail="Export worker could not be triggered") from exc

    job.trigger_command_id = command_id
    db.commit()
    db.refresh(job)
    response.status_code = status.HTTP_202_ACCEPTED
    return _serialize(job)


@router.get("/{job_id}")
def get_export(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(ExportJob).filter(ExportJob.id == job_id, ExportJob.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")
    return _serialize(job)

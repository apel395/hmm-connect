import boto3
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.export_job import ExportJob
from app.models.user import User


router = APIRouter(prefix="/exports", tags=["Exports"])
SUPPORTED_EXPORTS = {"products", "general_ledger"}


class ExportRequest(BaseModel):
    export_type: str
    params: dict | None = None


def _serialize(job: ExportJob) -> dict:
    payload = {
        "job_id": job.id,
        "export_type": job.export_type,
        "params": job.params,
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Queue an export and return immediately.

    The API/Lambda intentionally does not contact EC2, SSM, or generate XLS files.
    The persistent EC2 export worker polls the shared PostgreSQL export_jobs table
    and processes PENDING jobs asynchronously.
    """
    export_type = data.export_type.strip().lower()
    if export_type not in SUPPORTED_EXPORTS:
        raise HTTPException(status_code=400, detail=f"Unsupported export type: {export_type}")

    if export_type == "products" and (data.params or {}).get("catalog_type") not in {None, "CATERING", "HOTEL"}:
        raise HTTPException(422, "Choose Catering or Hotel Items")

    job = ExportJob(user_id=current_user.id, export_type=export_type, params=data.params, status="PENDING")
    db.add(job)
    db.commit()
    db.refresh(job)
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

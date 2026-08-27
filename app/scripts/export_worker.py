import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
from openpyxl import Workbook

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.export_job import ExportJob
from app.models.product import Product


MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _generate_products_xlsx(db, output_path: Path) -> None:
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Products")
    ws.append([
        "Code",
        "Name",
        "Group Code",
        "Group Name",
        "Subgroup Code",
        "Subgroup Name",
        "Purchase UOM",
        "Usage UOM",
        "Conversion",
        "Cost Price",
        "Selling Price",
        "Minimum Stock",
        "Reorder Level",
        "Maximum Stock",
        "Lead Time Days",
        "Tax Category",
        "Taxable",
        "Tax Rate",
        "Active",
    ])

    query = db.query(Product).order_by(Product.code).yield_per(1000)
    for row in query:
        ws.append([
            row.code,
            row.name,
            row.group_code,
            row.group_name,
            row.subgroup_code,
            row.subgroup_name,
            row.uom,
            row.usage_uom,
            float(row.conversion or 0),
            float(row.cost_price or 0),
            float(row.selling_price or 0),
            float(row.minimum_stock or 0),
            float(row.reorder_level or 0),
            float(row.maximum_stock or 0),
            row.lead_time_days,
            row.tax_category,
            bool(row.is_taxable),
            float(row.tax_rate or 0),
            bool(row.is_active),
        ])
    wb.save(output_path)


def run_job(job_id: str) -> None:
    db = SessionLocal()
    output_path: Path | None = None
    try:
        job = db.get(ExportJob, job_id)
        if not job or job.status not in {"PENDING", "PROCESSING"}:
            return

        job.status = "PROCESSING"
        job.started_at = datetime.now(timezone.utc)
        job.error_message = None
        db.commit()

        if job.export_type == "products":
            filename = f"HMM-Master-Products-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.xlsx"
        else:
            raise ValueError(f"Unsupported export type: {job.export_type}")

        tmp_dir = Path(settings.EXPORT_TMP_DIR)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        output_path = tmp_dir / f"{job.id}.xlsx"

        if job.export_type == "products":
            _generate_products_xlsx(db, output_path)

        bucket = settings.EXPORT_S3_BUCKET or settings.S3_BUCKET
        if not bucket:
            raise RuntimeError("EXPORT_S3_BUCKET or S3_BUCKET must be configured")

        key = f"{settings.EXPORT_S3_PREFIX.strip('/')}/{job.user_id}/{job.id}/{filename}"
        boto3.client("s3", region_name=settings.AWS_REGION or None).upload_file(
            str(output_path),
            bucket,
            key,
            ExtraArgs={
                "ContentType": MIME_XLSX,
                "ContentDisposition": f'attachment; filename="{filename}"',
            },
        )

        job.file_key = key
        job.filename = filename
        job.status = "READY"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.get(ExportJob, job_id)
        if job:
            job.status = "FAILED"
            job.error_message = str(exc)[:2000]
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        raise
    finally:
        if output_path and output_path.exists():
            output_path.unlink(missing_ok=True)
        db.close()


def next_pending_job_id() -> str | None:
    """Return the oldest pending job.

    HMM currently runs one export-worker service on the EC2 host, so one consumer
    is sufficient and keeps the queue semantics intentionally simple.
    """
    with SessionLocal() as db:
        job = (
            db.query(ExportJob)
            .filter(ExportJob.status == "PENDING")
            .order_by(ExportJob.created_at.asc(), ExportJob.id.asc())
            .first()
        )
        return job.id if job else None


def poll(interval: float) -> None:
    print(f"HMM export worker polling every {interval:g}s", flush=True)
    while True:
        job_id = next_pending_job_id()
        if not job_id:
            time.sleep(interval)
            continue
        try:
            print(f"Processing export job {job_id}", flush=True)
            run_job(job_id)
            print(f"Export job {job_id} ready", flush=True)
        except Exception as exc:
            print(f"Export job {job_id} failed: {exc}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="HMM Connect XLS export worker")
    parser.add_argument("--job-id")
    parser.add_argument("--poll", action="store_true")
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()

    if args.poll:
        poll(max(0.5, args.interval))
        return
    if not args.job_id:
        parser.error("either --job-id or --poll is required")
    run_job(args.job_id)


if __name__ == "__main__":
    main()

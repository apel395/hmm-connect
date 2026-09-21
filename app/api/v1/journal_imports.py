import base64
import io
import zipfile
from xml.sax.saxutils import escape
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.authorization import require_permission
from app.models.import_batch import ImportBatch, ImportRow
from app.models.user import User
from app.services.journal_import_jobs import (
    head_journal_import_object,
    presigned_upload_url,
    trigger_journal_import_job,
)


router = APIRouter(prefix="/journal-imports", tags=["Journal Imports"])
journal_import_user = require_permission("journal.manage")

ALLOWED_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
    "application/csv",
    "application/octet-stream",
}


class JournalImportCreate(BaseModel):
    batch_name: str = Field(min_length=1, max_length=150)
    notes: str | None = None


class JournalImportUploadUrl(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _get_batch(db: Session, job_id: int, user: User) -> ImportBatch:
    batch = (
        db.query(ImportBatch)
        .filter(
            ImportBatch.id == job_id,
            ImportBatch.created_by_id == user.id,
            ImportBatch.import_type == "JOURNAL_ENTRY",
            ImportBatch.source == "JOURNAL_BULK_IMPORT",
        )
        .first()
    )
    if not batch:
        raise HTTPException(404, "Journal import job not found")
    return batch


def _serialize(batch: ImportBatch) -> dict:
    return {
        "id": batch.id,
        "batch_number": batch.batch_number,
        "batch_name": batch.batch_name,
        "status": batch.status,
        "source": batch.source,
        "original_file_name": batch.original_file_name,
        "total_rows": batch.total_rows,
        "valid_rows": batch.valid_rows,
        "warning_rows": batch.warning_rows,
        "error_rows": batch.error_rows,
        "imported_rows": batch.imported_rows,
        "failed_rows": batch.failed_rows,
        "total_documents": batch.total_documents,
        "success_count": batch.success_count,
        "failed_count": batch.failed_count,
        "period_from": batch.period_from,
        "period_to": batch.period_to,
        "worker_command_id": batch.worker_command_id,
        "worker_started_at": batch.worker_started_at,
        "worker_completed_at": batch.worker_completed_at,
        "worker_error_message": batch.worker_error_message,
        "created_at": batch.created_at,
        "validated_at": batch.validated_at,
        "imported_at": batch.imported_at,
        "notes": batch.notes,
    }


def _xlsx_text_cell(ref: str, value: str) -> str:
    return (
        f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">'
        f'{escape(str(value))}</t></is></c>'
    )


def _build_journal_template_xlsx() -> bytes:
    headers = [
        "document_number", "posting_date", "description", "reference_type",
        "reference_id", "business_unit_code", "department_code", "location_code",
        "account_code", "line_description", "debit", "credit", "supplier_code",
        "external_reference", "status",
    ]
    rows = [
        [
            "TEST-BULK-001", "2026-01-15", "Example balanced journal", "MANUAL",
            "0", "001", "005", "001", "100-100-100", "Example debit line",
            "100000", "0", "", "TEST-001", "DRAFT",
        ],
        [
            "TEST-BULK-001", "2026-01-15", "Example balanced journal", "MANUAL",
            "0", "001", "005", "001", "100-110-100", "Example credit line",
            "0", "100000", "", "TEST-001", "DRAFT",
        ],
    ]

    def col_name(index: int) -> str:
        result = ""
        while index:
            index, remainder = divmod(index - 1, 26)
            result = chr(65 + remainder) + result
        return result

    sheet_rows = []
    for row_index, row in enumerate([headers, *rows], start=1):
        cells = "".join(
            _xlsx_text_cell(f"{col_name(col_index)}{row_index}", value)
            for col_index, value in enumerate(row, start=1)
        )
        sheet_rows.append(f'<row r="{row_index}">{cells}</row>')

    widths = [20, 14, 28, 16, 12, 20, 18, 16, 18, 24, 14, 14, 16, 20, 12]
    cols = "".join(
        f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>'
        for i, width in enumerate(widths, start=1)
    )
    worksheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
        'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f'<cols>{cols}</cols><sheetData>{"".join(sheet_rows)}</sheetData>'
        '<autoFilter ref="A1:O3"/>'
        '</worksheet>'
    )

    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>'''
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''
    workbook = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Journal Import" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''
    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>'''

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
    return output.getvalue()


@router.get("/template")
def template(user: User = Depends(journal_import_user)):
    del user
    payload = _build_journal_template_xlsx()
    return {
        "filename": "hmm-journal-import-template.xlsx",
        "content_base64": base64.b64encode(payload).decode("ascii"),
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "format": "XLSX",
        "notes": [
            "Repeat document_number for every line belonging to the same journal.",
            "Each journal must be balanced: total debit equals total credit.",
            "Business unit and location codes must exist and be active.",
            "Department and supplier codes are optional; when supplied they must exist.",
            "Account code must be an active posting account.",
            "Status must be DRAFT or POSTED and defaults to DRAFT.",
            "Maximum 5,000 rows and 500 journal documents per import.",
        ],
    }


@router.post("", status_code=201)
def create_job(
    data: JournalImportCreate,
    db: Session = Depends(get_db),
    user: User = Depends(journal_import_user),
):
    from uuid import uuid4

    batch_number = f"JIMP-{uuid4().hex[:12].upper()}"
    batch = ImportBatch(
        batch_number=batch_number,
        source="JOURNAL_BULK_IMPORT",
        description=data.notes,
        batch_name=data.batch_name,
        import_type="JOURNAL_ENTRY",
        import_mode="STRICT",
        source_type="JOURNAL_BULK_IMPORT",
        status="DRAFT",
        created_by_id=user.id,
        imported_by_id=user.id,
        notes=data.notes,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return _serialize(batch)


@router.post("/{job_id}/upload-url")
def upload_url(
    job_id: int,
    data: JournalImportUploadUrl,
    db: Session = Depends(get_db),
    user: User = Depends(journal_import_user),
):
    batch = _get_batch(db, job_id, user)
    if batch.status not in {"DRAFT", "UPLOADED"}:
        raise HTTPException(409, "This import job is no longer accepting a file")

    suffix = data.filename.lower().rsplit(".", 1)[-1] if "." in data.filename else ""
    if suffix not in {"xlsx", "csv"}:
        raise HTTPException(415, "Only XLSX and CSV files are supported")
    if data.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Unsupported upload content type")

    key, url = presigned_upload_url(
        user_id=user.id,
        job_id=job_id,
        filename=data.filename,
        content_type=data.content_type,
    )
    batch.file_name = data.filename
    batch.original_file_name = data.filename
    batch.stored_file_path = key
    db.commit()
    return {
        "job_id": job_id,
        "upload_url": url,
        "object_key": key,
        "expires_in": settings.JOURNAL_IMPORT_UPLOAD_URL_EXPIRES_SECONDS,
        "content_type": data.content_type,
    }


@router.post("/{job_id}/complete")
def complete_upload(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(journal_import_user),
):
    batch = _get_batch(db, job_id, user)
    if batch.status not in {"DRAFT", "UPLOADED"}:
        raise HTTPException(409, "This import job cannot be completed")

    if not batch.stored_file_path:
        raise HTTPException(409, "Upload URL has not been created")

    try:
        metadata = head_journal_import_object(batch.stored_file_path)
    except Exception as exc:
        raise HTTPException(409, "Uploaded file was not found in storage") from exc

    size = int(metadata.get("ContentLength") or 0)
    max_size = settings.JOURNAL_IMPORT_MAX_SIZE_MB * 1024 * 1024
    if size <= 0:
        raise HTTPException(409, "Uploaded file is empty")
    if size > max_size:
        raise HTTPException(413, f"Journal import file exceeds {settings.JOURNAL_IMPORT_MAX_SIZE_MB} MB")

    batch.status = "UPLOADED"
    batch.worker_error_message = None
    batch.notes = (
        f"{batch.notes}\n" if batch.notes else ""
    ) + f"Uploaded file size: {size} bytes"
    db.commit()
    db.refresh(batch)
    return _serialize(batch)


@router.post("/{job_id}/start", status_code=202)
def start_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(journal_import_user),
):
    batch = _get_batch(db, job_id, user)
    if batch.status != "UPLOADED":
        raise HTTPException(409, "Complete the file upload before starting the import")

    # Persist QUEUED before SSM dispatch so a fast EC2 worker cannot observe
    # the previous UPLOADED state and exit before processing starts.
    batch.status = "QUEUED"
    batch.worker_error_message = None
    db.commit()

    try:
        command_id = trigger_journal_import_job(job_id)
    except Exception as exc:
        batch.status = "FAILED"
        batch.worker_error_message = str(exc)[:2000]
        batch.worker_completed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(503, "Journal import worker could not be triggered") from exc

    batch.worker_command_id = command_id
    db.commit()
    db.refresh(batch)
    return _serialize(batch)


@router.get("/{job_id}")
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(journal_import_user),
):
    return _serialize(_get_batch(db, job_id, user))


@router.get("/{job_id}/errors")
def get_errors(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(journal_import_user),
):
    batch = _get_batch(db, job_id, user)
    rows = (
        db.query(ImportRow)
        .filter(
            ImportRow.import_batch_id == batch.id,
            ImportRow.status.in_({"ERROR", "FAILED"}),
        )
        .order_by(ImportRow.row_number.asc())
        .limit(500)
        .all()
    )
    return {
        "job_id": batch.id,
        "rows": [
            {
                "row_number": row.row_number,
                "sheet_name": row.sheet_name,
                "document_number": row.document_number,
                "status": row.status,
                "errors": row.error_messages_json or [],
                "warnings": row.warning_messages_json or [],
            }
            for row in rows
        ],
    }

import base64
import io
import re
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from xml.sax.saxutils import escape, quoteattr

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.authorization import require_permission
from app.models.business_unit import BusinessUnit
from app.models.chart_of_account import ChartOfAccount
from app.models.department import Department
from app.models.import_batch import ImportBatch, ImportRow
from app.models.location import Location
from app.models.supplier import Supplier
from app.models.user import User
from app.services.journal_import_jobs import (
    head_journal_import_object,
    presigned_upload_url,
    trigger_journal_import_job,
)
from app.services.location_access import assigned_location_id


router = APIRouter(prefix="/journal-imports", tags=["Journal Imports"])
journal_import_user = require_permission("journal.manage")

ALLOWED_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
    "application/csv",
    "application/octet-stream",
}

TEMPLATE_KEYS = [
    "posting_date", "document_number", "description", "business_unit_code",
    "location_code", "line_department_code", "account_code", "line_description", "debit", "credit",
]
TEMPLATE_HEADERS = [
    "posting_date", "document_number", "description", "business_unit_code (optional)",
    "location_code", "line_department_code (optional)", "account_code", "line_description", "debit", "credit",
]


class JournalImportCreate(BaseModel):
    batch_name: str = Field(min_length=1, max_length=150)
    notes: str | None = None


class JournalImportUploadUrl(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class JournalImportConfirm(BaseModel):
    post_valid: bool = False


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


def _decimal(value) -> Decimal:
    if value is None or str(value).strip() == "":
        return Decimal("0")
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    raw = re.sub(r"(?i)rp", "", str(value)).replace(" ", "")
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".") if raw.rfind(",") > raw.rfind(".") else raw.replace(",", "")
    elif raw.count(".") > 1:
        raw = raw.replace(".", "")
    elif raw.count(",") > 1:
        raw = raw.replace(",", "")
    elif "," in raw:
        left, right = raw.split(",", 1)
        raw = f"{left}.{right}" if len(right) in {1, 2} else left + right
    elif "." in raw:
        left, right = raw.split(".", 1)
        if len(right) == 3 and left not in {"0", "-0"}:
            raw = left + right
    try:
        return Decimal(raw)
    except InvalidOperation:
        return Decimal("0")


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _sheet_xml(
    rows: list[list],
    *,
    widths: list[int] | None = None,
    validations: list[tuple[str, str]] | None = None,
    auto_filter: str | None = None,
) -> str:
    row_xml = []
    for row_index, row in enumerate(rows, 1):
        cells = []
        for column_index, value in enumerate(row, 1):
            if value is None or value == "":
                continue
            reference = f"{_column_name(column_index)}{row_index}"
            cells.append(
                f'<c r="{reference}" t="inlineStr"><is><t xml:space="preserve">'
                f'{escape(str(value))}</t></is></c>'
            )
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    columns = ""
    if widths:
        columns = "<cols>" + "".join(
            f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
            for index, width in enumerate(widths, 1)
        ) + "</cols>"
    filter_xml = f'<autoFilter ref="{auto_filter}"/>' if auto_filter else ""
    validation_xml = ""
    if validations:
        entries = "".join(
            '<dataValidation type="list" allowBlank="1" showErrorMessage="1" '
            f'errorTitle="Invalid master-data code" '
            f'error="Select a value from current ERP master data." sqref="{cell_range}">'
            f'<formula1>{escape(range_name)}</formula1></dataValidation>'
            for cell_range, range_name in validations
        )
        validation_xml = f'<dataValidations count="{len(validations)}">{entries}</dataValidations>'
    pane = (
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
        'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'{pane}{columns}<sheetData>{"".join(row_xml)}</sheetData>{filter_xml}{validation_xml}'
        '</worksheet>'
    )


def _build_xlsx(
    sheets: list[dict],
    *,
    defined_names: list[tuple[str, str]] | None = None,
) -> bytes:
    content_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, len(sheets) + 1)
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f'{content_overrides}</Types>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    sheet_entries = "".join(
        f'<sheet name={quoteattr(sheet["title"])} sheetId="{index}" r:id="rId{index}"'
        f'{" state=\"hidden\"" if sheet.get("hidden") else ""}/>'
        for index, sheet in enumerate(sheets, 1)
    )
    names_xml = ""
    if defined_names:
        names_xml = "<definedNames>" + "".join(
            f'<definedName name={quoteattr(name)}>{escape(reference)}</definedName>'
            for name, reference in defined_names
        ) + "</definedNames>"
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{sheet_entries}</sheets>{names_xml}</workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
            for index in range(1, len(sheets) + 1)
        )
        + '</Relationships>'
    )

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        for index, sheet in enumerate(sheets, 1):
            archive.writestr(
                f"xl/worksheets/sheet{index}.xml",
                _sheet_xml(
                    sheet["rows"],
                    widths=sheet.get("widths"),
                    validations=sheet.get("validations"),
                    auto_filter=sheet.get("auto_filter"),
                ),
            )
    return output.getvalue()


def _build_template(db: Session, user: User) -> bytes:
    location_query = db.query(Location).filter(Location.is_active.is_(True))
    scoped_location = assigned_location_id(user)
    if scoped_location is not None:
        location_query = location_query.filter(Location.id == scoped_location)
    locations = location_query.order_by(Location.code).all()
    units = db.query(BusinessUnit).filter(BusinessUnit.is_active.is_(True)).order_by(BusinessUnit.code).all()
    departments = db.query(Department).filter(Department.is_active.is_(True)).order_by(Department.code).all()
    accounts = db.query(ChartOfAccount).filter(
        ChartOfAccount.is_active.is_(True),
        ChartOfAccount.is_posting.is_(True),
    ).order_by(ChartOfAccount.account_number).all()
    suppliers = db.query(Supplier).filter(Supplier.is_active.is_(True)).order_by(Supplier.code).all()

    instructions = [
        ["Easy Bulk Journal Import"],
        ["1", "Use Document Number to identify each journal, as in Create Journal Entry. Repeat it on separated lines of the same journal; blank cells continue the preceding journal."],
        ["2", "Enter Posting Date, Description, Business Unit and Work Location on the first line; blank header cells inherit them. Department belongs to each line: fill it independently or leave it unassigned. Business Unit may be inferred from Work Location."],
        ["3", "Enter one account line per row. Each row must contain either debit or credit. Total debit and credit must balance per document."],
        ["4", "Upload first validates only. Review the preview, then import valid journals as Draft or Post them."],
        ["5", "One invalid journal does not block other valid journals. If Document Number is blank throughout, the file is one journal with a generated document number."],
    ]
    validations = []
    defined_names = []
    master_specs = [
        ("E2:E501", "LocationCodes", "Master Locations", locations),
        ("D2:D501", "BusinessUnitCodes", "Master Business Units", units),
        ("F2:F501", "DepartmentCodes", "Master Departments", departments),
        ("G2:G501", "AccountCodes", "Master Accounts", accounts),
        
    ]
    for cell_range, range_name, sheet_name, values in master_specs:
        if values:
            validations.append((cell_range, range_name))
            defined_names.append((range_name, f"'{sheet_name}'!$A$2:$A${len(values) + 1}"))

    sheets = [
        {"title": "Instructions", "rows": instructions, "widths": [8, 110]},
        {
            "title": "Journal Import",
            "rows": [TEMPLATE_HEADERS],
            "widths": [15, 25, 30, 24, 18, 22, 18, 30, 18, 18],
            "validations": validations,
            "auto_filter": "A1:J501",
        },
        {
            "title": "Master Locations",
            "hidden": True,
            "rows": [["code", "name", "business_unit"], *[
                [row.code, row.name, row.business_unit.code if row.business_unit else ""] for row in locations
            ]],
        },
        {"title": "Master Business Units", "hidden": True, "rows": [["code", "name"], *[[row.code, row.name] for row in units]]},
        {"title": "Master Departments", "hidden": True, "rows": [["code", "name"], *[[row.code, row.name] for row in departments]]},
        {"title": "Master Accounts", "hidden": True, "rows": [["code", "name"], *[[row.account_number, row.account_name] for row in accounts]]},
        {"title": "Master Suppliers", "hidden": True, "rows": [["code", "name"], *[[row.code, row.name] for row in suppliers]]},
    ]
    return _build_xlsx(sheets, defined_names=defined_names)


@router.get("/template")
def template(
    db: Session = Depends(get_db),
    user: User = Depends(journal_import_user),
):
    payload = _build_template(db, user)
    return {
        "filename": "hmm-journal-import-easy-template.xlsx",
        "content_base64": base64.b64encode(payload).decode("ascii"),
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "format": "XLSX",
    }


@router.post("", status_code=201)
def create_job(
    data: JournalImportCreate,
    db: Session = Depends(get_db),
    user: User = Depends(journal_import_user),
):
    from uuid import uuid4

    batch = ImportBatch(
        batch_number=f"JIMP-{uuid4().hex[:12].upper()}",
        source="JOURNAL_BULK_IMPORT",
        description=data.notes,
        batch_name=data.batch_name,
        import_type="JOURNAL_ENTRY",
        import_mode="PREVIEW",
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
    maximum = settings.JOURNAL_IMPORT_MAX_SIZE_MB * 1024 * 1024
    if size <= 0:
        raise HTTPException(409, "Uploaded file is empty")
    if size > maximum:
        raise HTTPException(413, f"Journal import file exceeds {settings.JOURNAL_IMPORT_MAX_SIZE_MB} MB")
    batch.status = "UPLOADED"
    batch.worker_error_message = None
    db.commit()
    db.refresh(batch)
    return _serialize(batch)


@router.post("/{job_id}/start", status_code=202)
def start_validation(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(journal_import_user),
):
    batch = _get_batch(db, job_id, user)
    if batch.status != "UPLOADED":
        raise HTTPException(409, "Complete the file upload before validation")
    batch.status = "QUEUED"
    batch.worker_error_message = None
    db.commit()
    try:
        command_id = trigger_journal_import_job(job_id, mode="validate")
    except Exception as exc:
        batch.status = "FAILED"
        batch.worker_error_message = str(exc)[:2000]
        batch.worker_completed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(503, "Journal validation worker could not be triggered") from exc
    batch.worker_command_id = command_id
    db.commit()
    db.refresh(batch)
    return _serialize(batch)


@router.post("/{job_id}/confirm", status_code=202)
def confirm_import(
    job_id: int,
    data: JournalImportConfirm,
    db: Session = Depends(get_db),
    user: User = Depends(journal_import_user),
):
    batch = _get_batch(db, job_id, user)
    if batch.status != "VALIDATED":
        raise HTTPException(409, "Validate and review this import before confirming")
    valid_rows = db.query(ImportRow).filter(
        ImportRow.import_batch_id == batch.id,
        ImportRow.status == "VALID",
    ).count()
    if not valid_rows:
        raise HTTPException(409, "There are no valid journals to import")
    batch.status = "IMPORT_QUEUED"
    batch.worker_error_message = None
    db.commit()
    try:
        command_id = trigger_journal_import_job(job_id, mode="import", post_valid=data.post_valid)
    except Exception as exc:
        batch.status = "VALIDATED"
        batch.worker_error_message = str(exc)[:2000]
        db.commit()
        raise HTTPException(503, "Journal import worker could not be triggered") from exc
    batch.worker_command_id = command_id
    db.commit()
    db.refresh(batch)
    return _serialize(batch)


@router.get("/{job_id}/preview")
def get_preview(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(journal_import_user),
):
    batch = _get_batch(db, job_id, user)
    rows = db.query(ImportRow).filter(ImportRow.import_batch_id == batch.id).order_by(ImportRow.id).all()
    groups = defaultdict(list)
    for row in rows:
        data = row.normalized_data_json or {}
        groups[data.get("_group_key") or row.document_number or str(row.id)].append(row)
    result = []
    for group_rows in groups.values():
        first = group_rows[0].normalized_data_json or {}
        debit = sum((_decimal((row.normalized_data_json or {}).get("debit")) for row in group_rows), Decimal("0"))
        credit = sum((_decimal((row.normalized_data_json or {}).get("credit")) for row in group_rows), Decimal("0"))
        errors = list(dict.fromkeys(message for row in group_rows for message in (row.error_messages_json or [])))
        result.append({
            "journal_group": first.get("_group_label"),
            "document_number": first.get("document_number"),
            "posting_date": first.get("posting_date"),
            "description": first.get("description"),
            "location": first.get("location_code") or first.get("location"),
            "line_count": len(group_rows),
            "debit": debit,
            "credit": credit,
            "difference": debit - credit,
            "status": "ERROR" if errors else "VALID",
            "errors": errors,
        })
    return {"job_id": batch.id, "status": batch.status, "journals": result}


@router.get("/{job_id}/errors")
def get_errors(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(journal_import_user),
):
    batch = _get_batch(db, job_id, user)
    rows = db.query(ImportRow).filter(
        ImportRow.import_batch_id == batch.id,
        ImportRow.status.in_({"ERROR", "FAILED"}),
    ).order_by(ImportRow.row_number).limit(1000).all()
    return {
        "job_id": batch.id,
        "rows": [{
            "row_number": row.row_number,
            "sheet_name": row.sheet_name,
            "document_number": row.document_number,
            "journal_group": (row.normalized_data_json or {}).get("_group_label"),
            "status": row.status,
            "errors": row.error_messages_json or [],
            "warnings": row.warning_messages_json or [],
            "data": row.normalized_data_json or {},
        } for row in rows],
    }


@router.get("/{job_id}/correction-file")
def correction_file(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(journal_import_user),
):
    batch = _get_batch(db, job_id, user)
    rows = db.query(ImportRow).filter(
        ImportRow.import_batch_id == batch.id,
        ImportRow.status.in_({"ERROR", "FAILED"}),
    ).order_by(ImportRow.id).all()
    if not rows:
        raise HTTPException(404, "This import has no rejected rows")
    # Preserve optional metadata from older templates when correcting rejected rows.
    extra_keys = [key for key in ("supplier_code", "supplier", "external_reference")
                  if any((row.normalized_data_json or {}).get(key) for row in rows)]
    headers = [*TEMPLATE_HEADERS, *extra_keys, "validation_errors"]
    output_rows = [headers]
    department_codes = {value.name.casefold(): value.code for value in db.query(Department).all()}
    for row in rows:
        data = row.normalized_data_json or {}
        legacy_department = data.get("department_code") or department_codes.get(str(data.get("department") or "").casefold()) or data.get("department", "")
        values = [legacy_department if key == "line_department_code" and not data.get("_line_department_supplied") else data.get(key, "") for key in [*TEMPLATE_KEYS, *extra_keys]]
        values.append(" | ".join(row.error_messages_json or []))
        output_rows.append(values)
    payload = _build_xlsx([{
        "title": "Correction",
        "rows": output_rows,
        "widths": [22] * (len(headers) - 1) + [70],
        "auto_filter": f"A1:{chr(64 + len(headers))}{len(output_rows)}",
    }])
    return {
        "filename": f"{batch.batch_number}-corrections.xlsx",
        "content_base64": base64.b64encode(payload).decode("ascii"),
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }


@router.get("/{job_id}")
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(journal_import_user),
):
    return _serialize(_get_batch(db, job_id, user))

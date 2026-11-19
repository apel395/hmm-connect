"""Historical Catering AR Excel staging. No AR, receipt or GL posting endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.authorization import require_permission
from app.models.account_receivable import AccountReceivable
from app.models.business_unit import BusinessUnit
from app.models.department import Department
from app.models.import_batch import ImportBatch, ImportRow
from app.models.journal_entry import JournalEntry
from app.models.location import Location
from app.models.location_department import LocationDepartment
from app.models.sales_transaction import SalesTransaction
from app.models.user import User
from app.services.ar_import_staging import HARD, issue, parse_catering_workbook
from app.services.location_access import assigned_location_id

router = APIRouter(prefix="/ar-imports", tags=["AR Excel Import Staging"])
reviewer = require_permission("finance.manage")
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
SOURCE = "AR_INVOICE_EXCEL"


def owned_batch(db: Session, batch_id: int, user: User) -> ImportBatch:
    batch = db.query(ImportBatch).filter(
        ImportBatch.id == batch_id,
        ImportBatch.source == SOURCE,
        ImportBatch.import_type == "AR_INVOICE",
        ImportBatch.created_by_id == user.id,
    ).first()
    if not batch:
        raise HTTPException(404, "AR staging batch not found")
    return batch


def serialise(batch: ImportBatch) -> dict:
    return {
        "id": batch.id, "batch_number": batch.batch_number,
        "status": batch.status, "file_name": batch.original_file_name,
        "created_at": batch.created_at,
        "total_rows": batch.total_rows, "valid_rows": batch.valid_rows,
        "error_rows": batch.error_rows, "warning_rows": batch.warning_rows,
        "imported_rows": batch.imported_rows,
        "message": "STAGING ONLY. No sales invoice, receivable, receipt, journal or GL was created.",
    }


def validate_master_references(db: Session, user: User, rows: list[dict]) -> None:
    unit = db.query(BusinessUnit).filter(BusinessUnit.code == "002", BusinessUnit.is_active.is_(True)).first()
    dept = db.query(Department).filter(Department.code == "01", Department.is_active.is_(True)).first()
    locations = db.query(Location).filter(
        Location.code.in_({row["location_code"] for row in rows if row["location_code"]}),
        Location.is_active.is_(True),
    ).all()
    locations_by_code = {row.code: row for row in locations}
    links = set()
    if dept and locations:
        links = set(db.query(LocationDepartment.location_id, LocationDepartment.department_id).filter(
            LocationDepartment.location_id.in_([row.id for row in locations])
        ).all())

    invoice_numbers = {row["invoice_number"].strip().lower() for row in rows if row["invoice_number"]}
    existing_ar = set()
    existing_sale = set()
    existing_journal = set()
    if invoice_numbers:
        existing_ar = set(value[0] for value in db.query(func.lower(AccountReceivable.invoice_number)).filter(
            func.lower(AccountReceivable.invoice_number).in_(invoice_numbers)
        ).all())
        existing_sale = set(value[0] for value in db.query(func.lower(SalesTransaction.transaction_number)).filter(
            func.lower(SalesTransaction.transaction_number).in_(invoice_numbers)
        ).all())
        existing_journal = set(value[0] for value in db.query(func.lower(JournalEntry.document_number)).filter(
            func.lower(JournalEntry.document_number).in_(invoice_numbers)
        ).all())

    allowed_location = assigned_location_id(user)
    for row in rows:
        problems = row["issues"]
        code = row["location_code"]
        location = locations_by_code.get(code)
        if not unit or not dept or dept.business_unit_id != (unit.id if unit else None):
            problems.append(issue("INVALID_CATERING_DIMENSIONS", "Active Catering BU 002 / Operasional department 01 not configured"))
        if not location:
            problems.append(issue("UNKNOWN_LOCATION", f"Location {row['location_name']} / {code} missing or inactive"))
        elif unit and location.business_unit_id != unit.id:
            problems.append(issue("INVALID_CATERING_DIMENSIONS", "Location belongs to another Business Unit"))
        elif dept and (location.id, dept.id) not in links:
            problems.append(issue("INVALID_CATERING_DIMENSIONS", "Operasional department not mapped to this location"))
        if location and allowed_location is not None and location.id != allowed_location:
            problems.append(issue("LOCATION_ACCESS_DENIED", "User cannot stage invoices for this location"))
        key = row["invoice_number"].strip().lower()
        if key and key in existing_ar:
            problems.append(issue("DUPLICATE_EXISTING_AR", "Invoice already registered in AR"))
        if key and key in existing_sale:
            problems.append(issue("DUPLICATE_EXISTING_SALE", "Sales transaction already uses this invoice number"))
        if key and key in existing_journal:
            problems.append(issue("MATCH_EXISTING_JOURNAL", "Matching journal exists; reconcile before any AR activation"))


@router.post("/stage", status_code=201)
async def stage(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(reviewer),
):
    filename = (file.filename or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(415, "Upload the 2026 Catering revenue recap as .xlsx")
    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    if not contents or len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File must be non-empty and at most 5 MB")
    digest = "SHA256:" + sha256(contents).hexdigest()
    previous = db.query(ImportBatch).filter(
        ImportBatch.source == SOURCE, ImportBatch.created_by_id == user.id,
        ImportBatch.description == digest, ImportBatch.status == "STAGED",
    ).order_by(ImportBatch.id.desc()).first()
    if previous:
        return serialise(previous)
    try:
        parsed = parse_catering_workbook(contents)
    except (ValueError, OSError, KeyError, IndexError, TypeError) as exc:
        raise HTTPException(422, f"AR Excel structure invalid: {str(exc)[:500]}") from exc

    validate_master_references(db, user, parsed)
    batch = ImportBatch(
        batch_number=f"ARST-{uuid4().hex[:12].upper()}",
        source=SOURCE, import_type="AR_INVOICE",
        source_type="HISTORICAL_IMPORT", import_mode="PREVIEW",
        batch_name="Catering Revenue Invoice Recap", status="STAGED",
        description=digest, created_by_id=user.id,
        original_file_name=filename, file_name=filename,
        total_rows=len(parsed), total_documents=len(parsed),
        valid_rows=0,
        error_rows=sum(any(p["code"] in HARD for p in row["issues"]) for row in parsed),
        warning_rows=sum(any(p["severity"] == "REVIEW" for p in row["issues"]) for row in parsed),
        success_count=0,
        failed_count=0,
        imported_rows=0,
        notes="Source captured for financial mapping and bank/GL reconciliation. No AR or GL posted.",
        validated_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    db.flush()
    for row in parsed:
        problems = row.pop("issues")
        normalized = dict(row)
        db.add(ImportRow(
            import_batch_id=batch.id, row_number=row["source_row"],
            sheet_name=row["sheet_name"], document_type="AR_INVOICE",
            document_number=row["invoice_number"],
            raw_data_json=dict(normalized),
            normalized_data_json=dict(normalized),
            status="ERROR" if any(p["severity"] == "BLOCK" for p in problems) else "REVIEW",
            error_messages_json=[p["message"] for p in problems if p["severity"] == "BLOCK"],
            warning_messages_json=[p["message"] for p in problems if p["severity"] == "REVIEW"],
        ))
    db.commit()
    db.refresh(batch)
    return serialise(batch)


@router.get("/{batch_id}")
def get_batch(batch_id: int, db: Session = Depends(get_db), user: User = Depends(reviewer)):
    return serialise(owned_batch(db, batch_id, user))


@router.get("/{batch_id}/rows")
def list_rows(
    batch_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status: str | None = Query(None, pattern="^(ERROR|REVIEW)$"),
    db: Session = Depends(get_db),
    user: User = Depends(reviewer),
):
    batch = owned_batch(db, batch_id, user)
    query = db.query(ImportRow).filter(ImportRow.import_batch_id == batch.id)
    if status:
        query = query.filter(ImportRow.status == status)
    count = query.count()
    result = query.order_by(ImportRow.row_number).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "batch_id": batch.id, "page": page, "page_size": page_size,
        "total": count,
        "items": [{
            "row_number": row.row_number,
            "invoice_number": row.document_number,
            "status": row.status,
            "data": row.normalized_data_json,
            "errors": row.error_messages_json or [],
            "warnings": row.warning_messages_json or [],
        } for row in result],
    }


@router.get("/{batch_id}/summary")
def get_summary(batch_id: int, db: Session = Depends(get_db), user: User = Depends(reviewer)):
    batch = owned_batch(db, batch_id, user)
    rows = db.query(ImportRow).filter(ImportRow.import_batch_id == batch.id).all()
    locations: dict[str, dict] = {}
    totals = {"gross": Decimal("0"), "receipt": Decimal("0"), "aging": Decimal("0")}
    issue_counts: dict[str, int] = {}
    for row in rows:
        raw = row.normalized_data_json or {}
        location = raw.get("location_name") or "UNKNOWN"
        entry = locations.setdefault(location, {"invoices": 0, "gross": Decimal("0"), "receipt": Decimal("0"), "aging": Decimal("0")})
        entry["invoices"] += 1
        for attr in totals:
            value = Decimal(str(raw.get(attr) or "0"))
            totals[attr] += value
            entry[attr] += value
        for message in set((row.error_messages_json or []) + (row.warning_messages_json or [])):
            issue_counts[message] = issue_counts.get(message, 0) + 1
    return {
        **serialise(batch),
        "totals": {key: str(value.quantize(Decimal("0.01"))) for key, value in totals.items()},
        "locations": {site: {k: (str(v.quantize(Decimal("0.01"))) if isinstance(v, Decimal) else v) for k, v in values.items()} for site, values in locations.items()},
        "issues": issue_counts,
        "posting_enabled": False,
        "reason": "Source lacks customer, due date, revenue account and certified bank/tax reconciliation; existing GL must be matched first.",
    }

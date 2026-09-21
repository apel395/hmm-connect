from __future__ import annotations

import argparse
import csv
import os
import tempfile
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

import boto3
from openpyxl import load_workbook
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.business_unit import BusinessUnit
from app.models.chart_of_account import ChartOfAccount
from app.models.department import Department
from app.models.import_batch import ImportBatch, ImportRow
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.location import Location
from app.models.supplier import Supplier
from app.models.user import User
from app.services.activity_service import ActivityService
from app.services.document_number import next_document_number
from app.services.location_access import enforce_location_access
from app.api.v1.journals import post_locked_journal


REQUIRED_HEADERS = {
    "posting_date",
    "account_code",
    "debit",
    "credit",
}
MAX_ROWS = 5000
MAX_DOCUMENTS = 500

HEADER_ALIASES = {
    "document_no": "document_number",
    "document": "document_number",
    "date": "posting_date",
    "journal_date": "posting_date",
    "reference": "reference_type",
    "ref_type": "reference_type",
    "ref_id": "reference_id",
    "business_unit_name": "business_unit",
    "bu_name": "business_unit",
    "department_name": "department",
    "location_name": "location",
    "account": "account_code",
    "account_number": "account_code",
    "line_description": "line_description",
    "description_line": "line_description",
    "supplier_name": "supplier",
    "external_ref": "external_reference",
}


def text(value) -> str:
    return str(value).strip() if value is not None else ""


def json_safe(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def header(value) -> str:
    value = text(value).lower().replace("-", "_").replace(" ", "_")
    if value.endswith("_(optional)"):
        value = value[:-11]
    return HEADER_ALIASES.get(value, value)


def decimal(value, field: str) -> Decimal:
    raw = text(value).replace(",", "")
    if not raw:
        return Decimal("0")
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"{field}: invalid decimal {value!r}") from exc


def parse_date(value, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = text(value)
    if not raw:
        raise ValueError(f"{field}: required")
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            continue
    raise ValueError(f"{field}: invalid date {value!r}")


def parse_int(value, field: str, default: int = 0) -> int:
    raw = text(value)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{field}: invalid integer {value!r}") from exc


def read_rows(path: str, original_name: str) -> list[tuple[int, str, dict]]:
    suffix = os.path.splitext(original_name.lower())[1]
    result: list[tuple[int, str, dict]] = []

    if suffix == ".csv":
        with open(path, "r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            raw_headers = next(reader, None)
            if not raw_headers:
                raise ValueError("The import file is empty")
            headers = [header(value) for value in raw_headers]
            for row_number, values in enumerate(reader, 2):
                if not any(text(value) for value in values):
                    continue
                result.append(
                    (
                        row_number,
                        "CSV",
                        {key: json_safe(value) for key, value in zip(headers, values) if key},
                    )
                )
    elif suffix == ".xlsx":
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            for sheet in workbook.worksheets:
                values = sheet.iter_rows(values_only=True)
                raw_headers = next(values, None)
                if not raw_headers:
                    continue
                headers = [header(value) for value in raw_headers]
                for row_number, cells in enumerate(values, 2):
                    if not any(value is not None and text(value) for value in cells):
                        continue
                    result.append(
                        (
                            row_number,
                            sheet.title,
                            {key: json_safe(value) for key, value in zip(headers, cells) if key},
                        )
                    )
        finally:
            workbook.close()
    else:
        raise ValueError("Only XLSX and CSV files are supported")

    if not result:
        raise ValueError("The import file contains no data rows")
    if len(result) > MAX_ROWS:
        raise ValueError(f"Import exceeds the {MAX_ROWS}-row limit")
    return result


def normalize(raw: dict) -> dict:
    return {
        "document_number": text(raw.get("document_number")),
        "posting_date": text(raw.get("posting_date")),
        "description": text(raw.get("description")),
        "reference_type": text(raw.get("reference_type")).upper() or "MANUAL",
        "reference_id": text(raw.get("reference_id")) or "0",
        "business_unit": text(raw.get("business_unit")),
        "business_unit_code": text(raw.get("business_unit_code")).upper(),
        "department": text(raw.get("department")),
        "department_code": text(raw.get("department_code")).upper(),
        "location": text(raw.get("location")),
        "location_code": text(raw.get("location_code")).upper(),
        "account_code": text(raw.get("account_code")).upper(),
        "line_description": text(raw.get("line_description")),
        "debit": text(raw.get("debit")) or "0",
        "credit": text(raw.get("credit")) or "0",
        "supplier": text(raw.get("supplier")),
        "supplier_code": text(raw.get("supplier_code")).upper(),
        "external_reference": text(raw.get("external_reference")),
        "status": text(raw.get("status")).upper() or "DRAFT",
    }


def validate_group(
    db: Session,
    user: User,
    batch: ImportBatch,
    rows: list[ImportRow],
) -> list[str]:
    errors: list[str] = []
    first = rows[0].normalized_data_json or {}

    document_number = text(first.get("document_number"))

    try:
        posting_date = parse_date(first.get("posting_date"), "posting_date")
    except ValueError as exc:
        errors.append(str(exc))
        posting_date = None

    status = text(first.get("status") or "DRAFT").upper()
    if status not in {"DRAFT", "POSTED"}:
        errors.append("status must be DRAFT or POSTED")

    try:
        reference_id = parse_int(first.get("reference_id"), "reference_id")
        if reference_id < 0:
            errors.append("reference_id cannot be negative")
    except ValueError as exc:
        errors.append(str(exc))
        reference_id = 0

    business_unit_name = text(first.get("business_unit"))
    business_unit_code = text(first.get("business_unit_code")).upper()
    location_name = text(first.get("location"))
    location_code = text(first.get("location_code")).upper()
    department_name = text(first.get("department"))
    department_code = text(first.get("department_code")).upper()

    business_unit = None
    if business_unit_name:
        business_unit = db.query(BusinessUnit).filter(
            func.lower(BusinessUnit.name) == business_unit_name.lower()
        ).first()
    elif business_unit_code:
        business_unit = db.query(BusinessUnit).filter(BusinessUnit.code == business_unit_code).first()
    if not business_unit:
        errors.append(f"Unknown business_unit: {business_unit_name or business_unit_code}")

    location = None
    if location_name:
        location = db.query(Location).filter(
            func.lower(Location.name) == location_name.lower()
        ).first()
    elif location_code:
        location = db.query(Location).filter(Location.code == location_code).first()
    if not location:
        errors.append(f"Unknown location: {location_name or location_code}")
    else:
        try:
            enforce_location_access(user, location.id)
        except Exception as exc:
            errors.append(str(exc))

    department = None
    if department_name:
        department = db.query(Department).filter(
            func.lower(Department.name) == department_name.lower()
        ).first()
    elif department_code:
        department = db.query(Department).filter(Department.code == department_code).first()
    if (department_name or department_code) and not department:
        errors.append(f"Unknown department: {department_name or department_code}")

    if document_number and db.query(JournalEntry).filter(
        JournalEntry.document_number == document_number
    ).first():
        errors.append(f"Duplicate journal document_number already exists: {document_number}")

    header_fields = [
        "posting_date",
        "reference_type",
        "reference_id",
        "business_unit",
        "business_unit_code",
        "department",
        "department_code",
        "location",
        "location_code",
        "status",
    ]
    for row in rows:
        data = row.normalized_data_json or {}
        for field in header_fields:
            if text(data.get(field)) != text(first.get(field)):
                errors.append(
                    f"Row {row.row_number}: {field} differs from the first row of {document_number}"
                )

    if posting_date and batch.period_from is None:
        batch.period_from = posting_date
        batch.period_to = posting_date
    elif posting_date:
        batch.period_from = min(batch.period_from, posting_date)
        batch.period_to = max(batch.period_to, posting_date)

    debit_total = Decimal("0")
    credit_total = Decimal("0")

    for row in rows:
        data = row.normalized_data_json or {}
        try:
            debit = decimal(data.get("debit"), "debit")
            credit = decimal(data.get("credit"), "credit")
        except ValueError as exc:
            errors.append(f"Row {row.row_number}: {exc}")
            continue

        if debit < 0 or credit < 0:
            errors.append(f"Row {row.row_number}: debit and credit cannot be negative")
        if (debit > 0) == (credit > 0):
            errors.append(
                f"Row {row.row_number}: enter either debit or credit, not both and not zero/zero"
            )
        debit_total += debit
        credit_total += credit

        account_code = text(data.get("account_code")).upper()
        account = (
            db.query(ChartOfAccount)
            .filter(ChartOfAccount.account_number == account_code)
            .first()
        )
        if not account or not account.is_active or not account.is_posting:
            errors.append(f"Row {row.row_number}: invalid posting account {account_code}")

        supplier_name = text(data.get("supplier"))
        supplier_code = text(data.get("supplier_code")).upper()
        if supplier_name or supplier_code:
            if supplier_name:
                suppliers = db.query(Supplier).filter(
                    func.lower(Supplier.name) == supplier_name.lower()
                ).all()
                if len(suppliers) > 1:
                    errors.append(f"Row {row.row_number}: ambiguous supplier name {supplier_name}")
                    supplier = None
                else:
                    supplier = suppliers[0] if suppliers else None
            else:
                supplier = db.query(Supplier).filter(Supplier.code == supplier_code).first()
            if not supplier:
                errors.append(f"Row {row.row_number}: unknown supplier {supplier_name or supplier_code}")

    if debit_total != credit_total:
        errors.append(
            f"Journal {document_number} is unbalanced: debit {debit_total}, credit {credit_total}"
        )

    if status == "POSTED" and location is None:
        errors.append("POSTED journals require a valid location")

    if business_unit and not business_unit.is_active:
        errors.append(f"Business unit is inactive: {business_unit_code}")
    if location and not location.is_active:
        errors.append(f"Location is inactive: {location_code}")
    if department and not department.is_active:
        errors.append(f"Department is inactive: {department_code}")

    return errors


def run_job(job_id: int) -> None:
    db = SessionLocal()
    temp_path: str | None = None
    try:
        batch = db.get(ImportBatch, job_id)
        if not batch or batch.source != "JOURNAL_BULK_IMPORT":
            return
        if batch.status not in {"QUEUED", "PROCESSING"}:
            return

        user = db.get(User, batch.created_by_id)
        if not user:
            raise RuntimeError("Import creator no longer exists")

        batch.status = "PROCESSING"
        batch.worker_started_at = datetime.now(timezone.utc)
        batch.worker_error_message = None
        db.commit()

        bucket = settings.EXPORT_S3_BUCKET or settings.S3_BUCKET
        if not bucket or not batch.stored_file_path:
            raise RuntimeError("Journal import storage is not configured")

        suffix = os.path.splitext(batch.original_file_name or "")[1].lower() or ".xlsx"
        fd, temp_path = tempfile.mkstemp(
            prefix=f"hmm-journal-import-{batch.id}-",
            suffix=suffix,
            dir="/tmp",
        )
        os.close(fd)

        boto3.client("s3", region_name=settings.AWS_REGION or None).download_file(
            bucket,
            batch.stored_file_path,
            temp_path,
        )

        source_rows = read_rows(temp_path, batch.original_file_name or "")
        headers = set(source_rows[0][2].keys())
        missing = REQUIRED_HEADERS - headers
        if missing:
            raise ValueError(
                "Missing required columns: " + ", ".join(sorted(missing))
            )

        batch.rows.clear()
        db.flush()

        groups: dict[str, list[ImportRow]] = defaultdict(list)
        generated_document_number: str | None = None
        previous_explicit_document_number: str | None = None
        for row_number, sheet_name, raw in source_rows:
            normalized = normalize(raw)
            document_number = normalized["document_number"]
            if document_number:
                previous_explicit_document_number = document_number
                generated_document_number = None
            elif previous_explicit_document_number:
                # A blank document number continues the preceding explicit journal.
                document_number = previous_explicit_document_number
            else:
                # If the file starts with blanks, treat consecutive blank rows as
                # one journal and allocate a stable ERP document number for it.
                if generated_document_number is None:
                    generated_document_number = next_document_number(db, "JIMP", digits=6)
                document_number = generated_document_number

            normalized["document_number"] = document_number
            row = ImportRow(
                import_batch_id=batch.id,
                row_number=row_number,
                sheet_name=sheet_name,
                document_type="JOURNAL_ENTRY",
                raw_data_json=raw,
                normalized_data_json=normalized,
                status="PENDING",
                document_number=document_number,
            )
            db.add(row)
            groups[document_number].append(row)

        db.flush()

        if len(groups) > MAX_DOCUMENTS:
            raise ValueError(f"Import exceeds the {MAX_DOCUMENTS}-journal limit")

        total_errors = 0
        for document_number, rows in groups.items():
            errors = validate_group(db, user, batch, rows)
            if errors:
                total_errors += len(rows)
                for row in rows:
                    row.status = "ERROR"
                    row.error_messages_json = errors
            else:
                for row in rows:
                    row.status = "VALID"
                    row.error_messages_json = []
                    row.warning_messages_json = []

        batch.total_rows = len(source_rows)
        batch.total_documents = len(groups)
        batch.valid_rows = sum(row.status == "VALID" for row in batch.rows)
        batch.error_rows = sum(row.status == "ERROR" for row in batch.rows)
        batch.warning_rows = 0
        batch.failed_rows = 0

        if total_errors:
            batch.status = "FAILED"
            batch.failed_count = sum(
                1 for rows in groups.values()
                if any(row.status == "ERROR" for row in rows)
            )
            batch.success_count = 0
            batch.worker_error_message = (
                f"Validation failed for {batch.error_rows} spreadsheet rows."
            )
            batch.worker_completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        db.flush()

        imported_documents = 0
        imported_rows = 0

        for document_number, rows in groups.items():
            first = rows[0].normalized_data_json or {}
            business_unit_name = text(first.get("business_unit"))
            business_unit_code = text(first.get("business_unit_code")).upper()
            if business_unit_name:
                business_unit = db.query(BusinessUnit).filter(
                    func.lower(BusinessUnit.name) == business_unit_name.lower()
                ).one()
            else:
                business_unit = db.query(BusinessUnit).filter(
                    BusinessUnit.code == business_unit_code
                ).one()

            location_name = text(first.get("location"))
            location_code = text(first.get("location_code")).upper()
            if location_name:
                location = db.query(Location).filter(
                    func.lower(Location.name) == location_name.lower()
                ).one()
            else:
                location = db.query(Location).filter(
                    Location.code == location_code
                ).one()

            department_name = text(first.get("department"))
            department_code = text(first.get("department_code")).upper()
            if department_name:
                department = db.query(Department).filter(
                    func.lower(Department.name) == department_name.lower()
                ).one()
            elif department_code:
                department = db.query(Department).filter(
                    Department.code == department_code
                ).one()
            else:
                department = None
            status = text(first.get("status") or "DRAFT").upper()
            imported_at = datetime.now(timezone.utc)

            journal = JournalEntry(
                journal_number=next_document_number(db, "MAN", digits=6),
                posting_date=parse_date(first["posting_date"], "posting_date"),
                status="DRAFT",
                document_type="BULK_JOURNAL_IMPORT",
                document_number=document_number,
                reference_type=text(first.get("reference_type") or "MANUAL").upper(),
                reference_id=parse_int(first.get("reference_id"), "reference_id"),
                description=text(first.get("description")) or None,
                created_by_id=user.id,
                source_type="JOURNAL_IMPORT",
                external_reference=(
                    text(first.get("external_reference"))
                    or f"JOURNAL_IMPORT:{batch.id}:{document_number}"
                )[:100],
                import_batch_id=batch.id,
                imported_by_id=user.id,
                imported_at=imported_at,
                business_unit_id=business_unit.id,
                department_id=department.id if department else None,
                location_id=location.id,
            )

            for line_number, row in enumerate(rows, 1):
                data = row.normalized_data_json or {}
                account = db.query(ChartOfAccount).filter(
                    ChartOfAccount.account_number == text(data["account_code"]).upper()
                ).one()
                supplier_name = text(data.get("supplier"))
                supplier_code = text(data.get("supplier_code")).upper()
                if supplier_name:
                    supplier = db.query(Supplier).filter(
                        func.lower(Supplier.name) == supplier_name.lower()
                    ).one()
                elif supplier_code:
                    supplier = db.query(Supplier).filter(Supplier.code == supplier_code).one()
                else:
                    supplier = None
                journal.lines.append(
                    JournalLine(
                        line_number=line_number,
                        account_id=account.id,
                        debit=decimal(data["debit"], "debit"),
                        credit=decimal(data["credit"], "credit"),
                        description=text(data.get("line_description")) or None,
                        business_unit_id=business_unit.id,
                        department_id=department.id if department else None,
                        location_id=location.id,
                        supplier_id=supplier.id if supplier else None,
                    )
                )

            db.add(journal)
            db.flush()

            ActivityService.log(
                db=db,
                user=user,
                action="JOURNAL_IMPORT_CREATED",
                entity_type="JOURNAL_ENTRY",
                entity_id=journal.id,
                summary=f"Imported {journal.journal_number} from {batch.batch_number}",
                details={"batch_number": batch.batch_number, "document_number": document_number},
                import_batch_id=batch.id,
            )

            if status == "POSTED":
                post_locked_journal(db, journal=journal, user=user)

            for row in rows:
                row.status = "IMPORTED"
                row.entity_type = "JOURNAL_ENTRY"
                row.entity_id = journal.id
                row.imported_at = imported_at

            imported_documents += 1
            imported_rows += len(rows)

        batch.imported_rows = imported_rows
        batch.failed_rows = 0
        batch.success_count = imported_documents
        batch.failed_count = 0
        batch.status = "IMPORTED"
        batch.imported_at = datetime.now(timezone.utc)
        batch.worker_completed_at = datetime.now(timezone.utc)
        batch.worker_error_message = None
        ActivityService.log(
            db=db,
            user=user,
            action="JOURNAL_IMPORT_COMPLETED",
            entity_type="IMPORT_BATCH",
            entity_id=batch.id,
            summary=f"Imported {imported_documents} journals from {batch.batch_number}",
            details={
                "documents": imported_documents,
                "rows": imported_rows,
            },
            import_batch_id=batch.id,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        failed_batch = db.get(ImportBatch, job_id)
        if failed_batch:
            failed_batch.status = "FAILED"
            failed_batch.worker_error_message = str(exc)[:4000]
            failed_batch.worker_completed_at = datetime.now(timezone.utc)
            db.commit()
        raise
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="HMM Connect journal import worker")
    parser.add_argument("--job-id", type=int, required=True)
    args = parser.parse_args()
    run_job(args.job_id)


if __name__ == "__main__":
    main()

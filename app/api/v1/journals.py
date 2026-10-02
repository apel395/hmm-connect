from datetime import date, datetime, timezone
from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission, is_superuser, require_permission
from app.models.chart_of_account import ChartOfAccount
from app.models.accounting_setting import AccountingSetting
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.fiscal_period import FiscalPeriod
from app.schemas.journal import JournalBulkAction, JournalCreate, JournalUpdate
from app.services.accounting_posting_rule_service import AccountingPostingRuleService
from app.services.accounting_unpost import (
    SUPPORTED_SOURCE_TYPES,
    apply_source_post_state,
    recreate_journal_ledger,
    unpost_journal,
)
from app.services.audit import record_audit
from app.services.document_context import print_metadata
from app.services.document_number import next_document_number
from app.services.general_ledger import GeneralLedgerService
from app.services.fiscal_period_service import FiscalPeriodService
from app.services.location_access import apply_location_scope, enforce_location_access, resolve_location_id
from app.services.organization_dimensions import validate_dimensions

router = APIRouter(prefix="/journal-entries", tags=["Journal Entries"])
ZERO = Decimal("0")
STANDARD_UNPOSTABLE_SOURCES = {"MANUAL", "SUPPLIER_INVOICE"}


journal_view_user = require_permission("journal.view")
journal_manage_user = require_permission("journal.manage")


def get(db, id, user):
    x = db.get(JournalEntry, id)
    if not x:
        raise HTTPException(404, "Journal entry not found")
    enforce_location_access(user, x.location_id)
    return x


def validate(db, lines):
    if not lines:
        raise HTTPException(400, "Journal must contain at least one line")
    debit = credit = ZERO
    for line in lines:
        d = Decimal(line.debit)
        c = Decimal(line.credit)
        if d < 0 or c < 0:
            raise HTTPException(400, "Debit and credit cannot be negative")
        if (d > 0) == (c > 0):
            raise HTTPException(400, "Each line must contain either debit or credit")
        account = db.get(ChartOfAccount, line.account_id)
        if not account or not account.is_active or not account.is_posting:
            raise HTTPException(400, "Journal lines require active posting accounts")
        debit += d
        credit += c
    return debit, credit


def validate_journal_location_integrity(journal: JournalEntry) -> None:
    if journal.location_id is None:
        raise HTTPException(409, "Journal requires a work location before posting")
    for line in journal.lines:
        if line.location_id != journal.location_id:
            raise HTTPException(
                409,
                "Every journal line location must match the journal header location",
            )
        if (
            journal.business_unit_id is not None
            and line.business_unit_id != journal.business_unit_id
        ):
            raise HTTPException(
                409,
                "Every journal line Business Unit must match the journal header",
            )


def serialize(x, user=None):
    debit = sum((Decimal(l.debit) for l in x.lines), ZERO)
    credit = sum((Decimal(l.credit) for l in x.lines), ZERO)
    source = (x.reference_type or "MANUAL").upper()
    admin_unpost = bool(user and is_superuser(user) and source in SUPPORTED_SOURCE_TYPES)
    return {
        "id": x.id,
        "journal_number": x.journal_number,
        "journal_date": x.posting_date,
        "posting_date": x.posting_date,
        "description": x.description,
        "reference_type": x.reference_type,
        "reference_id": x.reference_id,
        "reference_number": x.document_number,
        "status": x.status,
        "business_unit_id": x.business_unit_id,
        "department_id": x.department_id,
        "location_id": x.location_id,
        "location_name": next((line.location.name for line in x.lines if line.location_id == x.location_id and line.location), None),
        "created_by_name": x.created_by.full_name if x.created_by else None,
        "posted_by_name": x.posted_by.full_name if x.posted_by else None,
        "created_at": x.created_at,
        "posted_at": x.posted_at,
        "voided_at": x.voided_at,
        "total_debit": debit,
        "total_credit": credit,
        "difference": debit - credit,
        "allowed_actions": {
            "can_edit": x.status == "DRAFT" and source not in {"SUPPLIER_PAYMENT", "SUPPLIER_INVOICE"},
            "can_post": x.status == "DRAFT" and bool(x.lines) and debit == credit,
            "can_recreate": x.status == "POSTED" and bool(user and is_superuser(user)),
            "can_unpost": x.status == "POSTED" and (
                source in STANDARD_UNPOSTABLE_SOURCES or admin_unpost
            ),
            "can_void": x.status == "DRAFT" and source not in {"SUPPLIER_PAYMENT", "SUPPLIER_INVOICE"},
            "can_void_source_payment": x.status == "DRAFT" and source == "SUPPLIER_PAYMENT" and bool(user and has_permission(user, "payment.manage")),
            "can_print": True,
        },
        "lines": [
            {
                "id": l.id,
                "line_number": l.line_number,
                "account_id": l.account_id,
                "account_code": l.account.account_number,
                "account_name": l.account.account_name,
                "description": l.description,
                "debit": l.debit,
                "credit": l.credit,
                "business_unit_id": l.business_unit_id,
                "department_id": l.department_id,
                "department_name": l.department.name if l.department else None,
                "location_id": l.location_id,
                "location_name": l.location.name if l.location else None,
                "supplier_id": l.supplier_id,
            }
            for l in x.lines
        ],
    }


def require_admin(user) -> None:
    if not is_superuser(user):
        raise HTTPException(403, "Administrator access required for bulk or recreate journal operations")


def post_locked_journal(db: Session, *, journal: JournalEntry, user) -> None:
    if journal.status != "DRAFT":
        raise HTTPException(409, f"Journal {journal.journal_number} is not draft")
    debit, credit = validate(db, journal.lines)
    validate_journal_location_integrity(journal)
    if debit != credit:
        raise HTTPException(409, f"Journal {journal.journal_number} is not balanced")

    source_type = str(journal.reference_type or journal.document_type or "").upper()
    if source_type in {"SUPPLIER_INVOICE", "SUPPLIER_PAYMENT"}:
        debit_accounts = [line.account for line in journal.lines if Decimal(line.debit) > ZERO]
        credit_accounts = [line.account for line in journal.lines if Decimal(line.credit) > ZERO]
        allowed_liability_debit_ids = set()
        if source_type == "SUPPLIER_INVOICE":
            grni_setting = db.query(AccountingSetting).filter(
                AccountingSetting.setting_key == "GRNI_ACCOUNT",
            ).first()
            if grni_setting:
                allowed_liability_debit_ids.add(grni_setting.account_id)
        AccountingPostingRuleService.validate_source_journal_accounts(
            source_type,
            debit_accounts,
            credit_accounts,
            allowed_liability_debit_ids=allowed_liability_debit_ids,
        )

    if source_type == "SUPPLIER_PAYMENT":
        from app.api.v1.payments import validate_payment_journal_integrity
        from app.models.payment import Payment
        payment = db.get(Payment, journal.reference_id)
        if not payment or payment.journal_entry_id != journal.id:
            raise HTTPException(409, "Payment journal is not linked to its source payment")
        if not payment.allocations or sum((Decimal(row.allocated_amount) for row in payment.allocations), ZERO) != Decimal(payment.amount):
            raise HTTPException(409, "Payment allocations must match its total before journal posting")
        if sum((Decimal(row.amount) for row in payment.funding_lines), ZERO) != Decimal(payment.amount):
            raise HTTPException(409, "Payment funding must match its total before journal posting")
        validate_payment_journal_integrity(db, payment, journal)

    apply_source_post_state(db, journal=journal, user=user)
    for line in journal.lines:
        GeneralLedgerService.post(
            db=db,
            account_id=line.account_id,
            debit=line.debit,
            credit=line.credit,
            posting_date=journal.posting_date,
            journal_source=journal.reference_type,
            document_type=journal.document_type,
            document_number=journal.document_number,
            reference_type=journal.reference_type,
            reference_id=journal.reference_id,
            reference_number=journal.journal_number,
            description=line.description,
            user_id=user.id,
        )
    journal.status = "POSTED"
    journal.posted_by_id = user.id
    journal.posted_at = datetime.now(timezone.utc)
    if journal.document_type == "SUPPLIER_INVOICE_ASSET_RECLASS":
        from app.models.supplier_invoice import SupplierInvoiceLine
        from app.models.chart_of_account import ChartOfAccount
        from app.services.invoice_asset_registration import register_invoice_asset

        invoice_line = db.get(SupplierInvoiceLine, journal.reference_id)
        debit_line = next((item for item in journal.lines if Decimal(item.debit or 0) > ZERO), None)
        account = db.get(ChartOfAccount, debit_line.account_id) if debit_line else None
        if not invoice_line or not account or not account.account_number.startswith("100-600-"):
            raise HTTPException(409, "Asset correction journal is missing its invoice line or asset account")
        register_invoice_asset(
            db, invoice=invoice_line.invoice, line=invoice_line,
            account_id=account.id, journal=journal, user=user,
        )
    if source_type == "SUPPLIER_INVOICE":
        from app.models.supplier_invoice import SupplierInvoice
        from app.models.chart_of_account import ChartOfAccount
        from app.services.invoice_asset_registration import register_invoice_asset

        invoice = db.get(SupplierInvoice, journal.reference_id)
        if invoice and not invoice.goods_receipt_id:
            for invoice_line in invoice.lines:
                if invoice_line.goods_receipt_item_id or not invoice_line.account_id:
                    continue
                account = db.get(ChartOfAccount, invoice_line.account_id)
                if account and account.account_number.startswith("100-600-"):
                    register_invoice_asset(
                        db, invoice=invoice, line=invoice_line, account_id=account.id,
                        journal=journal, user=user,
                    )
    record_audit(
        db,
        user,
        "JOURNAL_POSTED",
        "JOURNAL_ENTRY",
        f"Posted {journal.journal_number}",
        entity_id=journal.id,
        reference_document=journal.document_number,
    )


@router.get("")
def listing(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    reference_type: str | None = None,
    account_id: int | None = None,
    supplier_id: int | None = None,
    location_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(journal_view_user),
):
    q = apply_location_scope(db.query(JournalEntry), JournalEntry, user)
    if location_id:
        q = q.filter(JournalEntry.location_id == location_id)
    if search:
        q = q.filter(or_(
            JournalEntry.journal_number.ilike(f"%{search}%"),
            JournalEntry.document_number.ilike(f"%{search}%"),
            JournalEntry.description.ilike(f"%{search}%"),
        ))
    if status:
        q = q.filter(JournalEntry.status == status)
    if date_from:
        q = q.filter(JournalEntry.posting_date >= date_from)
    if date_to:
        q = q.filter(JournalEntry.posting_date <= date_to)
    if reference_type:
        q = q.filter(JournalEntry.reference_type == reference_type)
    if account_id:
        q = q.filter(JournalEntry.lines.any(JournalLine.account_id == account_id))
    if supplier_id:
        q = q.filter(JournalEntry.lines.any(JournalLine.supplier_id == supplier_id))
    total = q.count()
    if total:
        journal_ids = q.with_entities(JournalEntry.id)
        total_debit, total_credit = db.query(
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        ).filter(JournalLine.journal_entry_id.in_(journal_ids)).one()
    else:
        total_debit = total_credit = ZERO
    rows = q.order_by(JournalEntry.posting_date.desc(), JournalEntry.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [serialize(x, user) for x in rows],
        "summary": {"total_debit": total_debit, "total_credit": total_credit},
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": ceil(total / page_size) if total else 0,
        "has_next": page * page_size < total,
        "has_previous": page > 1,
    }


@router.post("", status_code=201)
def create(data: JournalCreate, db: Session = Depends(get_db), user=Depends(journal_manage_user)):
    debit, credit = validate(db, data.lines)
    if debit != credit:
        raise HTTPException(422, "Journal debit and credit must be balanced")
    location_id = resolve_location_id(user, data.location_id)
    if location_id is None:
        raise HTTPException(422, "Select a work location before creating a journal")
    validate_dimensions(db, data.business_unit_id, location_id, data.department_id)
    x = JournalEntry(
        journal_number=next_document_number(db, "MAN", digits=6),
        posting_date=data.posting_date,
        document_type=data.document_type,
        document_number=data.document_number,
        reference_type=data.reference_type,
        reference_id=data.reference_id,
        description=data.description,
        status="DRAFT",
        created_by_id=user.id,
        business_unit_id=data.business_unit_id,
        location_id=location_id,
        department_id=data.department_id,
    )
    for i, line in enumerate(data.lines, 1):
        line_data = line.model_dump()
        line_data["location_id"] = location_id
        line_data["business_unit_id"] = x.business_unit_id
        x.lines.append(JournalLine(line_number=i, **line_data))
    db.add(x)
    db.flush()
    record_audit(db, user, "JOURNAL_CREATED", "JOURNAL_ENTRY", f"Created {x.journal_number}", entity_id=x.id, reference_document=x.document_number)
    db.commit()
    db.refresh(x)
    return serialize(x, user)


@router.get("/bulk/current-period-preview")
def current_period_preview(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_admin(user)
    period = FiscalPeriodService.validate_posting_date(db=db, posting_date=date.today())
    if period is None:
        raise HTTPException(409, "Fiscal periods must be configured before using current-period actions")
    q = db.query(JournalEntry).filter(
        JournalEntry.posting_date >= period.start_date,
        JournalEntry.posting_date <= period.end_date,
    )
    return {
        "period_id": period.id,
        "period_name": period.period_name,
        "start_date": period.start_date,
        "end_date": period.end_date,
        "draft_count": q.filter(JournalEntry.status == "DRAFT").count(),
        "posted_count": q.filter(JournalEntry.status == "POSTED").count(),
    }


@router.post("/bulk/post")
def post_all(
    data: JournalBulkAction,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_admin(user)
    ids = list(dict.fromkeys(data.journal_ids))
    journals = db.query(JournalEntry).filter(
        JournalEntry.id.in_(ids),
    ).with_for_update().all()
    found = {journal.id for journal in journals}
    missing = [journal_id for journal_id in ids if journal_id not in found]
    if missing:
        raise HTTPException(404, f"Journal entries not found: {missing}")
    for journal in journals:
        post_locked_journal(db, journal=journal, user=user)
    db.commit()
    return {"processed": len(journals), "status": "POSTED", "journal_ids": ids}


@router.post("/bulk/unpost")
def unpost_all(
    data: JournalBulkAction,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_admin(user)
    ids = list(dict.fromkeys(data.journal_ids))
    journals = db.query(JournalEntry).filter(
        JournalEntry.id.in_(ids),
    ).with_for_update().all()
    found = {journal.id for journal in journals}
    missing = [journal_id for journal_id in ids if journal_id not in found]
    if missing:
        raise HTTPException(404, f"Journal entries not found: {missing}")
    for journal in journals:
        unpost_journal(db, journal=journal, user=user, commit=False)
    db.commit()
    return {"processed": len(journals), "status": "DRAFT", "journal_ids": ids}


@router.post("/bulk/recreate-current-period")
def recreate_current_period(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_admin(user)
    period = FiscalPeriodService.validate_posting_date(db=db, posting_date=date.today())
    if period is None:
        raise HTTPException(409, "Fiscal periods must be configured before recreating a period")
    journals = db.query(JournalEntry).filter(
        JournalEntry.status == "POSTED",
        JournalEntry.posting_date >= period.start_date,
        JournalEntry.posting_date <= period.end_date,
    ).with_for_update().all()
    if len(journals) > 500:
        raise HTTPException(409, "Current period contains more than 500 posted journals; recreate in smaller batches")
    row_count = 0
    for journal in journals:
        debit, credit = validate(db, journal.lines)
        if debit != credit:
            raise HTTPException(409, f"Journal {journal.journal_number} is not balanced")
        row_count += recreate_journal_ledger(db, journal=journal, user=user)
    db.commit()
    return {
        "period_id": period.id,
        "period_name": period.period_name,
        "journals_recreated": len(journals),
        "ledger_rows_recreated": row_count,
    }


@router.get("/{journal_id}")
def detail(journal_id: int, db: Session = Depends(get_db), user=Depends(journal_view_user)):
    return serialize(get(db, journal_id, user), user)


@router.patch("/{journal_id}")
def update(journal_id: int, data: JournalUpdate, db: Session = Depends(get_db), user=Depends(journal_manage_user)):
    x = get(db, journal_id, user)
    if x.status != "DRAFT":
        raise HTTPException(409, "Unpost the journal before editing it")
    if x.reference_type in {"SUPPLIER_PAYMENT", "SUPPLIER_INVOICE"}:
        raise HTTPException(409, "Edit this journal through its source payment or supplier invoice")
    location_changed = "location_id" in data.model_fields_set
    if location_changed:
        if (x.reference_type or "").upper() != "MANUAL":
            raise HTTPException(409, "Work location must be corrected in the source document")
        if data.location_id is None:
            raise HTTPException(422, "Work location is required")
        location_id = resolve_location_id(user, data.location_id)
        validate_dimensions(db, x.business_unit_id, location_id, x.department_id)
        x.location_id = location_id
    if data.posting_date:
        x.posting_date = data.posting_date
    if data.description is not None:
        x.description = data.description
    if data.lines is not None:
        debit, credit = validate(db, data.lines)
        if debit != credit:
            raise HTTPException(422, "Journal debit and credit must be balanced")
        x.lines.clear()
        for i, l in enumerate(data.lines, 1):
            line_data = l.model_dump()
            line_data["location_id"] = x.location_id
            line_data["business_unit_id"] = x.business_unit_id
            x.lines.append(JournalLine(line_number=i, **line_data))
    elif location_changed:
        for line in x.lines:
            line.location_id = x.location_id
            line.business_unit_id = x.business_unit_id
    record_audit(db, user, "JOURNAL_UPDATED", "JOURNAL_ENTRY", f"Updated {x.journal_number}", entity_id=x.id)
    db.commit()
    db.refresh(x)
    return serialize(x, user)


@router.post("/{journal_id}/post")
def post(journal_id: int, db: Session = Depends(get_db), user=Depends(journal_manage_user)):
    x = db.query(JournalEntry).filter(JournalEntry.id == journal_id).with_for_update().first()
    if not x:
        raise HTTPException(404, "Journal entry not found")
    enforce_location_access(user, x.location_id)
    post_locked_journal(db, journal=x, user=user)
    db.commit()
    db.refresh(x)
    return serialize(x, user)


@router.post("/{journal_id}/recreate")
def recreate(
    journal_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_admin(user)
    journal = db.query(JournalEntry).filter(
        JournalEntry.id == journal_id,
    ).with_for_update().first()
    if not journal:
        raise HTTPException(404, "Journal entry not found")
    debit, credit = validate(db, journal.lines)
    if debit != credit:
        raise HTTPException(409, "Journal is not balanced")
    rows = recreate_journal_ledger(db, journal=journal, user=user)
    db.commit()
    db.refresh(journal)
    return {**serialize(journal, user), "ledger_rows_recreated": rows}


@router.post("/{journal_id}/unpost")
def unpost(journal_id: int, db: Session = Depends(get_db), user=Depends(journal_manage_user)):
    x = db.query(JournalEntry).filter(JournalEntry.id == journal_id).with_for_update().first()
    if not x:
        raise HTTPException(404, "Journal entry not found")
    enforce_location_access(user, x.location_id)
    source = (x.reference_type or "MANUAL").upper()
    if source not in STANDARD_UNPOSTABLE_SOURCES and not is_superuser(user):
        raise HTTPException(403, "Only an administrator can unpost a source-controlled journal")
    return serialize(unpost_journal(db, journal=x, user=user), user)


@router.post("/{journal_id}/void")
def void(journal_id: int, db: Session = Depends(get_db), user=Depends(journal_manage_user)):
    x = get(db, journal_id, user)
    if x.status != "DRAFT":
        raise HTTPException(409, "Only draft journals can be voided without reversal")
    if x.reference_type in {"SUPPLIER_PAYMENT", "SUPPLIER_INVOICE"}:
        raise HTTPException(409, "Void or reopen the source payment or supplier invoice instead")
    x.status = "VOID"
    x.voided_at = datetime.now(timezone.utc)
    record_audit(db, user, "JOURNAL_VOIDED", "JOURNAL_ENTRY", f"Voided {x.journal_number}", entity_id=x.id)
    db.commit()
    db.refresh(x)
    return serialize(x, user)


@router.get("/{journal_id}/print")
def printable(journal_id: int, db: Session = Depends(get_db), user=Depends(journal_view_user)):
    return {**serialize(get(db, journal_id, user), user), "document_type": "Journal Entry", **print_metadata(user)}

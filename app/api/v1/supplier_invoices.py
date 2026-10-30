from datetime import date, datetime, timedelta, timezone
from math import ceil
from decimal import Decimal

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import is_superuser, require_permission
from app.models.journal_entry import JournalEntry
from app.models.chart_of_account import ChartOfAccount
from app.models.fixed_asset import FixedAsset
from app.models.payment import Payment, PaymentAllocation
from app.models.payment_voucher import PaymentVoucher, PaymentVoucherAllocation
from app.models.goods_receipt import GoodsReceipt
from app.models.purchase_order import PurchaseOrder
from app.models.warehouse import Warehouse
from app.models.location import Location
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.schemas.supplier_invoice import SupplierInvoiceInput
from app.schemas.journal import JournalCreate, JournalLineCreate
from app.services.accounting_unpost import unpost_journal
from app.services.journal_service import JournalService
from app.services.invoice_asset_registration import register_invoice_asset
from app.services.audit import record_audit
from app.services.document_context import document_context, print_metadata
from app.services.direct_coa_service import DirectCoaService
from app.services.supplier_invoice_runtime_service import SupplierInvoiceService
from app.services.location_access import apply_location_scope, enforce_location_access, resolve_location_id

router = APIRouter(prefix="/supplier-invoices", tags=["Supplier Invoices"])

ASSET_RECLASS_DOCUMENT_TYPE = "SUPPLIER_INVOICE_ASSET_RECLASS"


class AssetReclassInput(BaseModel):
    line_id: int
    asset_account_id: int
    posting_date: date


invoice_view_user = require_permission("supplier_invoice.view")
invoice_create_user = require_permission("supplier_invoice.create")
invoice_edit_user = require_permission("supplier_invoice.edit")
invoice_verify_user = require_permission("supplier_invoice.verify")
invoice_reject_user = require_permission("supplier_invoice.reject")
invoice_post_user = require_permission("supplier_invoice.post")
invoice_void_user = require_permission("supplier_invoice.void")


def get(db, invoice_id, user):
    invoice = db.get(SupplierInvoice, invoice_id)
    if not invoice:
        raise HTTPException(404, "Supplier invoice not found")
    enforce_location_access(user, _resolved_invoice_location_id(db, invoice))
    return invoice


def _resolved_invoice_location_id(db: Session, invoice: SupplierInvoice) -> int | None:
    """Resolve invoice location from persisted source IDs, without relying on ORM cache."""
    if invoice.location_id:
        return invoice.location_id

    if invoice.goods_receipt_id:
        row = (
            db.query(GoodsReceipt.location_id, Warehouse.location_id, PurchaseOrder.location_id)
            .outerjoin(Warehouse, Warehouse.id == GoodsReceipt.warehouse_id)
            .outerjoin(PurchaseOrder, PurchaseOrder.id == GoodsReceipt.purchase_order_id)
            .filter(GoodsReceipt.id == invoice.goods_receipt_id)
            .first()
        )
        if row:
            receipt_location_id, warehouse_location_id, po_location_id = row
            return receipt_location_id or warehouse_location_id or po_location_id

    if invoice.purchase_order_id:
        return (
            db.query(PurchaseOrder.location_id)
            .filter(PurchaseOrder.id == invoice.purchase_order_id)
            .scalar()
        )

    return None


def _hydrate_location_name(db: Session, invoice: SupplierInvoice, data: dict) -> dict:
    location_id = _resolved_invoice_location_id(db, invoice)
    if location_id:
        location = db.get(Location, location_id)
        data["location_id"] = location_id
        data["location_name"] = location.name if location else None
    return data


def result(db, invoice, user):
    service = SupplierInvoiceService(db)
    data = _hydrate_location_name(db, invoice, service.serialize(service.attach_journal(invoice)))
    match = service.match_summary(invoice)
    data["three_way_match"] = match
    readiness = DirectCoaService(db).supplier_invoice_readiness(invoice)
    data["accounting_readiness"] = readiness
    asset_by_line = {
        asset.source_invoice_line_id: asset
        for asset in db.query(FixedAsset).filter(
            FixedAsset.source_invoice_line_id.in_([line.id for line in invoice.lines]),
        ).all()
    } if invoice.lines else {}
    for item in data["lines"]:
        asset = asset_by_line.get(item["id"])
        if asset:
            item["fixed_asset"] = {
                "id": asset.id, "asset_number": asset.asset_number, "status": asset.status,
            }
    line_ids = [line.id for line in invoice.lines]
    if line_ids:
        reclasses = db.query(JournalEntry).filter(
            JournalEntry.document_type == ASSET_RECLASS_DOCUMENT_TYPE,
            JournalEntry.reference_type == "MANUAL",
            JournalEntry.reference_id.in_(line_ids),
            JournalEntry.status != "VOID",
        ).all()
        by_line = {journal.reference_id: journal for journal in reclasses}
        for line in data["lines"]:
            journal = by_line.get(line["id"])
            if journal:
                debit = next((item for item in journal.lines if item.debit > 0), None)
                account = db.get(ChartOfAccount, debit.account_id) if debit else None
                line["asset_reclassification"] = {
                    "journal_id": journal.id,
                    "journal_number": journal.journal_number,
                    "status": journal.status,
                    "account_code": account.account_number if account else None,
                    "account_name": account.account_name if account else None,
                }
    data.update(document_context(db, "SUPPLIER_INVOICE", invoice.id, invoice.status, user))
    data["allowed_actions"] = {
        "can_edit": invoice.status == "DRAFT",
        "can_verify": invoice.status == "DRAFT" and not data["supplier_reference_pending"] and match["can_verify"] and readiness["is_ready"],
        "can_reject": invoice.status in {"DRAFT", "VERIFIED"} and not data["related_journal"],
        "can_generate_journal": invoice.status == "VERIFIED" and not data["related_journal"],
        "can_void": invoice.status in {"DRAFT", "VERIFIED"},
        "can_print": True,
        "can_manage_attachments": True,
        "can_view_history": True,
    }
    return data


@router.get("")
def listing(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    supplier_id: int | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    po_number: str | None = None,
    receipt_number: str | None = None,
    source_type: str | None = None,
    location_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(invoice_view_user),
):
    query = apply_location_scope(db.query(SupplierInvoice), SupplierInvoice, user)
    if location_id:
        query = query.filter(SupplierInvoice.location_id == location_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(
            SupplierInvoice.internal_invoice_number.ilike(term),
            SupplierInvoice.supplier_invoice_number.ilike(term),
            SupplierInvoice.supplier.has(Supplier.name.ilike(term)),
        ))
    if supplier_id:
        query = query.filter(SupplierInvoice.supplier_id == supplier_id)
    if status:
        query = query.filter(SupplierInvoice.status == status)
    if date_from:
        query = query.filter(SupplierInvoice.invoice_date >= date_from)
    if date_to:
        query = query.filter(SupplierInvoice.invoice_date <= date_to)
    if due_from:
        query = query.filter(SupplierInvoice.due_date >= due_from)
    if due_to:
        query = query.filter(SupplierInvoice.due_date <= due_to)
    if po_number:
        query = query.join(SupplierInvoice.purchase_order).filter_by(po_number=po_number)
    if receipt_number:
        query = query.join(SupplierInvoice.goods_receipt).filter_by(receipt_number=receipt_number)
    if source_type:
        query = query.filter(SupplierInvoice.source_type == source_type)
    total = query.count()
    rows = query.order_by(SupplierInvoice.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    service = SupplierInvoiceService(db)
    return {
        "items": [
            _hydrate_location_name(db, item, service.serialize(service.attach_journal(item)))
            for item in rows
        ],
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": ceil(total / page_size) if total else 0,
        "has_next": page * page_size < total,
        "has_previous": page > 1,
    }


@router.get("/{invoice_id}")
def detail(invoice_id: int, db: Session = Depends(get_db), user=Depends(invoice_view_user)):
    return result(db, get(db, invoice_id, user), user)


@router.post("/prepare-from-receipt/{receipt_id}", status_code=201)
def prepare_from_receipt(
    receipt_id: int,
    db: Session = Depends(get_db),
    user=Depends(invoice_create_user),
):
    """One-click idempotent preparation for receipts posted before rollout."""
    receipt = (
        db.query(GoodsReceipt)
        .filter(GoodsReceipt.id == receipt_id)
        .with_for_update()
        .first()
    )
    if not receipt:
        raise HTTPException(404, "Receiving Report not found")
    enforce_location_access(user, receipt.location_id)
    if receipt.status != "POSTED":
        raise HTTPException(409, "Only posted Receiving Reports can prepare supplier invoice drafts")
    invoice = SupplierInvoiceService(db).prepare_receipt_draft(receipt, user)
    db.commit()
    db.refresh(invoice)
    return result(db, invoice, user)


@router.post("", status_code=201)
def create(data: SupplierInvoiceInput, db: Session = Depends(get_db), user=Depends(invoice_create_user)):
    data.location_id = resolve_location_id(user, data.location_id)
    if data.due_date is None:
        data.due_date = data.invoice_date + timedelta(days=30)
    return result(db, SupplierInvoiceService(db).create(data, user), user)


@router.patch("/{invoice_id}")
def update(invoice_id: int, data: SupplierInvoiceInput, db: Session = Depends(get_db), user=Depends(invoice_edit_user)):
    data.location_id = resolve_location_id(user, data.location_id)
    if data.due_date is None:
        data.due_date = data.invoice_date + timedelta(days=30)
    return result(db, SupplierInvoiceService(db).update(get(db, invoice_id, user), data, user), user)


@router.post("/{invoice_id}/verify")
def verify(invoice_id: int, db: Session = Depends(get_db), user=Depends(invoice_verify_user)):
    """Verify and prepare the invoice journal atomically."""
    service = SupplierInvoiceService(db)
    invoice = get(db, invoice_id, user)
    invoice = service.persist_source_location(invoice)
    try:
        invoice = service.verify(invoice, user, commit=False)
        service.generate_journal(invoice, user, commit=False)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    db.refresh(invoice)
    return result(db, invoice, user)


@router.post("/{invoice_id}/reject")
def reject(invoice_id: int, db: Session = Depends(get_db), user=Depends(invoice_reject_user)):
    invoice = get(db, invoice_id, user)
    if invoice.status not in {"DRAFT", "VERIFIED"}:
        raise HTTPException(409, "Only draft or verified invoices without a journal can be rejected")
    journal = db.query(JournalEntry).filter(
        JournalEntry.reference_type == "SUPPLIER_INVOICE",
        JournalEntry.reference_id == invoice.id,
        JournalEntry.status != "VOID",
    ).first()
    if journal:
        raise HTTPException(409, "Invoice with a journal cannot be rejected")
    previous = invoice.status
    invoice.status = "REJECTED"
    record_audit(
        db, user, "SUPPLIER_INVOICE_REJECTED", "SUPPLIER_INVOICE",
        f"Rejected {invoice.internal_invoice_number}", entity_id=invoice.id,
        before_data={"status": previous}, after_data={"status": "REJECTED"},
    )
    db.commit()
    db.refresh(invoice)
    return result(db, invoice, user)


@router.post("/{invoice_id}/generate-journal")
def generate(invoice_id: int, db: Session = Depends(get_db), user=Depends(invoice_post_user)):
    invoice = get(db, invoice_id, user)
    existing = db.query(JournalEntry).filter(
        JournalEntry.reference_type == "SUPPLIER_INVOICE",
        JournalEntry.reference_id == invoice.id,
        JournalEntry.status != "VOID",
    ).first()
    if existing:
        return {"id": existing.id, "journal_number": existing.journal_number, "status": existing.status}
    service = SupplierInvoiceService(db)
    invoice = service.persist_source_location(invoice)
    journal = service.generate_journal(invoice, user)
    return {"id": journal.id, "journal_number": journal.journal_number, "status": journal.status}


@router.post("/{invoice_id}/reclassify-asset")
def reclassify_asset(
    invoice_id: int,
    payload: AssetReclassInput,
    db: Session = Depends(get_db),
    user=Depends(invoice_post_user),
):
    if not is_superuser(user):
        raise HTTPException(403, "Administrator access required for posted invoice reclassification")
    invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == invoice_id).with_for_update().one_or_none()
    if not invoice:
        raise HTTPException(404, "Supplier invoice not found")
    enforce_location_access(user, _resolved_invoice_location_id(db, invoice))
    if invoice.status != "POSTED":
        raise HTTPException(409, "Only posted supplier invoices can be reclassified")
    line = next((item for item in invoice.lines if item.id == payload.line_id), None)
    if not line or line.goods_receipt_item_id or invoice.goods_receipt_id:
        raise HTTPException(409, "Choose a direct supplier invoice line without a receiving link")
    origin = DirectCoaService(db).account(line.account_id, "Original invoice line")
    if origin.account_type != "EXPENSE" or origin.normal_balance != "DEBIT":
        raise HTTPException(409, "Original invoice line must be an expense debit")
    amount = Decimal(line.line_amount or 0)
    if amount <= 0:
        raise HTTPException(409, "Invoice line must have a positive amount")
    asset = DirectCoaService(db).account(payload.asset_account_id, "Fixed asset")
    if not (
        asset.account_number.startswith("100-600-")
        and asset.account_type == "ASSET"
        and asset.normal_balance == "DEBIT"
    ):
        raise HTTPException(409, "Select a posting debit-balance fixed asset COA under 100-600")

    source = db.query(JournalEntry).filter(
        JournalEntry.reference_type == "SUPPLIER_INVOICE",
        JournalEntry.reference_id == invoice.id,
        JournalEntry.status == "POSTED",
    ).one_or_none()
    if not source:
        raise HTTPException(409, "The original invoice journal must be posted")
    source_debit = sum(
        (Decimal(item.debit or 0) for item in source.lines if item.account_id == origin.id),
        Decimal("0"),
    )
    invoice_expense = sum(
        (Decimal(item.line_amount or 0) for item in invoice.lines if item.account_id == origin.id),
        Decimal("0"),
    )
    if source_debit < invoice_expense:
        raise HTTPException(409, "The original journal does not contain the invoice expense debit")

    existing = db.query(JournalEntry).filter(
        JournalEntry.document_type == ASSET_RECLASS_DOCUMENT_TYPE,
        JournalEntry.reference_type == "MANUAL",
        JournalEntry.reference_id == line.id,
        JournalEntry.status != "VOID",
    ).first()
    if existing:
        raise HTTPException(409, f"Line already has reclassification journal {existing.journal_number}")

    location_id = _resolved_invoice_location_id(db, invoice)
    description = f"Asset reclassification of {invoice.internal_invoice_number} line {line.id}"
    journal = JournalService.post(
        db=db,
        user=user,
        journal=JournalCreate(
            business_unit_id=invoice.business_unit_id,
            location_id=location_id,
            department_id=line.department_id or invoice.department_id,
            posting_date=payload.posting_date,
            document_type=ASSET_RECLASS_DOCUMENT_TYPE,
            document_number=invoice.internal_invoice_number,
            reference_type="MANUAL",
            reference_id=line.id,
            description=description,
            lines=[
                JournalLineCreate(account_id=asset.id, debit=amount, credit=0,
                                  description=description, supplier_id=invoice.supplier_id),
                JournalLineCreate(account_id=origin.id, debit=0, credit=amount,
                                  description=description, supplier_id=invoice.supplier_id),
            ],
        ),
    )
    register_invoice_asset(db, invoice=invoice, line=line, account_id=asset.id, journal=journal, user=user)
    record_audit(
        db, user, "SUPPLIER_INVOICE_ASSET_RECLASSIFIED", "SUPPLIER_INVOICE",
        description, entity_id=invoice.id,
        before_data={"line_id": line.id, "account_id": origin.id},
        after_data={"journal_id": journal.id, "asset_account_id": asset.id, "amount": str(amount)},
        reference_document=invoice.internal_invoice_number,
    )
    db.commit()
    return result(db, invoice, user)


@router.post("/{invoice_id}/unpost")
def admin_unpost(invoice_id: int, db: Session = Depends(get_db), user=Depends(invoice_post_user)):
    if not is_superuser(user):
        raise HTTPException(403, "Administrator access required to unpost a supplier invoice")
    invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == invoice_id).with_for_update().first()
    if not invoice:
        raise HTTPException(404, "Supplier invoice not found")
    enforce_location_access(user, _resolved_invoice_location_id(db, invoice))
    if invoice.status != "POSTED":
        raise HTTPException(409, "Only posted supplier invoices can be unposted")
    journal = db.query(JournalEntry).filter(
        JournalEntry.reference_type == "SUPPLIER_INVOICE",
        JournalEntry.reference_id == invoice.id,
        JournalEntry.status == "POSTED",
    ).with_for_update().one_or_none()
    if not journal:
        raise HTTPException(409, "Posted supplier invoice journal not found")
    reclass = db.query(JournalEntry.id).filter(
        JournalEntry.document_type == ASSET_RECLASS_DOCUMENT_TYPE,
        JournalEntry.reference_type == "MANUAL",
        JournalEntry.reference_id.in_([line.id for line in invoice.lines]),
        JournalEntry.status != "VOID",
    ).first()
    if reclass:
        raise HTTPException(409, "Void the linked asset reclassification journal before unposting this invoice")
    unpost_journal(db, journal=journal, user=user, commit=False)
    db.commit()
    db.refresh(invoice)
    return result(db, invoice, user)


@router.post("/{invoice_id}/reopen")
def admin_reopen(invoice_id: int, db: Session = Depends(get_db), user=Depends(invoice_edit_user), body: dict | None = None):
    # The invoice.edit permission is explicitly granted by the Roles module.
    # No journal posting or period-closing privilege is implied.
    reason = str((body or {}).get("reason") or "").strip()
    if not is_superuser(user) and len(reason) < 3:
        raise HTTPException(422, "Enter a correction reason before reopening a verified invoice")
    invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == invoice_id).with_for_update().first()
    if not invoice:
        raise HTTPException(404, "Supplier invoice not found")
    enforce_location_access(user, _resolved_invoice_location_id(db, invoice))
    if invoice.status != "VERIFIED":
        raise HTTPException(409, "Only verified, unposted invoices can be reopened")
    linked_payment = db.query(PaymentAllocation.id).join(Payment).filter(
        PaymentAllocation.supplier_invoice_id == invoice.id,
        Payment.status != "VOID",
    ).first()
    linked_voucher = db.query(PaymentVoucherAllocation.id).join(PaymentVoucher).filter(
        PaymentVoucherAllocation.supplier_invoice_id == invoice.id,
        PaymentVoucher.status.notin_(("VOID", "REJECTED", "CANCELLED")),
    ).first()
    if linked_payment or linked_voucher:
        raise HTTPException(409, "Void linked payments and vouchers before reopening this invoice")
    journals = db.query(JournalEntry).filter(
        JournalEntry.reference_type == "SUPPLIER_INVOICE",
        JournalEntry.reference_id == invoice.id,
        JournalEntry.status != "VOID",
    ).with_for_update().all()
    if any(j.status != "DRAFT" for j in journals):
        raise HTTPException(409, "Unpost the supplier invoice journal before reopening")
    # Preserve the draft journal identity. Re-verification rebuilds its lines
    # from the corrected invoice; only a posted journal needs a reversal flow.
    from app.services.fiscal_period_service import FiscalPeriodService
    FiscalPeriodService.validate_posting_date(db, invoice.invoice_date, system_closing=True)
    snapshots = [{"id": j.id, "lines": [{"account_id": line.account_id, "debit": str(line.debit), "credit": str(line.credit)} for line in j.lines]} for j in journals]
    for journal in journals:
        journal.lines.clear()  # Retain identity, withdraw recognition until re-verification.
    invoice.status = "DRAFT"
    invoice.verified_at = None
    record_audit(
        db, user, "SUPPLIER_INVOICE_REOPENED", "SUPPLIER_INVOICE",
        f"Reopened {invoice.internal_invoice_number} as draft",
        entity_id=invoice.id,
        before_data={"status": "VERIFIED", "journals": snapshots},
        after_data={"status": "DRAFT", "journal_status": "DRAFT", "journal_reused": True, "reason": reason or "Administrator correction"},
    )
    db.commit()
    db.refresh(invoice)
    return result(db, invoice, user)


@router.post("/{invoice_id}/void")
def void(invoice_id: int, db: Session = Depends(get_db), user=Depends(invoice_void_user)):
    invoice = get(db, invoice_id, user)
    if invoice.status == "POSTED":
        raise HTTPException(409, "Posted invoices cannot be voided without a reversal")
    if invoice.status == "VOID":
        raise HTTPException(409, "Invoice is already void")
    from app.services.accounting_unpost import _assert_invoice_has_no_posted_dependents
    from app.services.fiscal_period_service import FiscalPeriodService
    FiscalPeriodService.validate_posting_date(db, invoice.invoice_date, system_closing=True)
    _assert_invoice_has_no_posted_dependents(db, invoice)
    now = datetime.now(timezone.utc)
    invoice.status = "VOID"
    invoice.voided_at = now
    journal = db.query(JournalEntry).filter(
        JournalEntry.reference_type == "SUPPLIER_INVOICE",
        JournalEntry.reference_id == invoice.id,
        JournalEntry.status == "DRAFT",
    ).first()
    if journal:
        journal.status = "VOID"
        journal.voided_at = now
        record_audit(db, user, "JOURNAL_VOIDED", "JOURNAL_ENTRY", f"Voided {journal.journal_number}", entity_id=journal.id, reference_document=invoice.internal_invoice_number)
    record_audit(db, user, "SUPPLIER_INVOICE_VOIDED", "SUPPLIER_INVOICE", f"Voided {invoice.internal_invoice_number}", entity_id=invoice.id)
    db.commit()
    db.refresh(invoice)
    return result(db, invoice, user)


@router.get("/{invoice_id}/allowed-actions")
def actions(invoice_id: int, db: Session = Depends(get_db), user=Depends(invoice_view_user)):
    return result(db, get(db, invoice_id, user), user)["allowed_actions"]


@router.get("/{invoice_id}/print")
def printable(invoice_id: int, db: Session = Depends(get_db), user=Depends(invoice_view_user)):
    return {**result(db, get(db, invoice_id, user), user), "document_type": "Supplier Invoice", **print_metadata(user)}

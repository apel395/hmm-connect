from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import is_superuser
from app.models.account_payable import AccountPayable
from app.models.amortization import Amortization
from app.models.approval_request import ApprovalRequest
from app.models.bank_transfer import BankTransfer
from app.models.fixed_asset import (
    FixedAsset,
    FixedAssetDepreciationRun,
    FixedAssetDepreciationSchedule,
    FixedAssetMovement,
)
from app.models.general_ledger import GeneralLedger
from app.models.goods_receipt import GoodsReceipt
from app.models.journal_entry import JournalEntry
from app.models.payment import Payment
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_requisition import PurchaseRequisition
from app.models.supplier_adjustment import SupplierAdjustment
from app.models.supplier_invoice import SupplierInvoice
from app.services.audit import record_audit
from app.services.fiscal_period_service import FiscalPeriodService

router = APIRouter(prefix="/admin-overrides", tags=["Admin Overrides"])
ZERO = Decimal("0")


def require_admin(user):
    if not is_superuser(user):
        raise HTTPException(status_code=403, detail="Administrator access required")


def _delete_approval(db: Session, entity_type: str, entity_id: int) -> None:
    request = db.query(ApprovalRequest).filter(
        ApprovalRequest.entity_type == entity_type,
        ApprovalRequest.entity_id == entity_id,
    ).first()
    if request:
        db.delete(request)
        db.flush()


def _active_journal(db: Session, reference_type: str, reference_id: int) -> JournalEntry | None:
    return db.query(JournalEntry).filter(
        JournalEntry.reference_type == reference_type,
        JournalEntry.reference_id == reference_id,
        JournalEntry.status != "VOID",
    ).order_by(JournalEntry.id.desc()).first()


def _void_draft_journal(db: Session, journal: JournalEntry | None, user) -> None:
    if not journal or journal.status == "VOID":
        return
    if journal.status == "POSTED":
        raise HTTPException(
            status_code=409,
            detail=f"Journal {journal.journal_number} is posted. Unpost the journal before reopening its source document.",
        )
    journal.status = "VOID"
    journal.voided_at = datetime.now(timezone.utc)
    record_audit(
        db,
        user,
        "ADMIN_JOURNAL_VOIDED_FOR_REOPEN",
        "JOURNAL_ENTRY",
        f"Voided draft journal {journal.journal_number} while reopening source document",
        entity_id=journal.id,
        reference_document=journal.document_number,
    )


def _sync_payable(db: Session, invoice: SupplierInvoice, payment_date=None) -> None:
    balance = max(
        ZERO,
        Decimal(invoice.total_amount or 0)
        - Decimal(invoice.paid_amount or 0)
        - Decimal(invoice.adjustment_amount or 0),
    )
    invoice.balance_amount = balance
    invoice.payment_status = (
        "PAID"
        if balance == ZERO
        else "PARTIALLY_PAID"
        if Decimal(invoice.paid_amount or 0) > ZERO or Decimal(invoice.adjustment_amount or 0) > ZERO
        else "UNPAID"
    )
    payable = db.query(AccountPayable).filter(
        AccountPayable.supplier_id == invoice.supplier_id,
        AccountPayable.invoice_number == invoice.internal_invoice_number,
    ).first()
    if payable:
        payable.amount = invoice.total_amount
        payable.paid_amount = invoice.paid_amount
        payable.outstanding_amount = balance
        payable.payment_status = invoice.payment_status
        payable.status = "PAID" if balance == ZERO else "OPEN"
        if payment_date is not None:
            payable.last_payment_date = payment_date


def _reopen_purchase_requisition(db: Session, item: PurchaseRequisition, user) -> None:
    linked = [po for po in item.purchase_orders if po.status != "CANCELLED"]
    if linked:
        numbers = ", ".join(po.po_number for po in linked[:5])
        raise HTTPException(
            status_code=409,
            detail=f"Reopen or cancel linked purchase order(s) first: {numbers}",
        )
    previous = item.status
    _delete_approval(db, "PURCHASE_REQUISITION", item.id)
    item.status = "DRAFT"
    record_audit(db, user, "ADMIN_REOPEN", "PURCHASE_REQUISITION", f"Reopened {item.pr_number}", entity_id=item.id, before_data={"status": previous}, after_data={"status": "DRAFT"})


def _reopen_purchase_order(db: Session, item: PurchaseOrder, user) -> None:
    active_receipts = [receipt for receipt in item.goods_receipts if receipt.status not in {"RETURNED", "CANCELLED"}]
    if active_receipts:
        numbers = ", ".join(receipt.receipt_number for receipt in active_receipts[:5])
        raise HTTPException(
            status_code=409,
            detail=f"Return active receiving document(s) before reopening this PO: {numbers}",
        )
    previous = item.status
    _delete_approval(db, "PURCHASE_ORDER", item.id)
    item.status = "DRAFT"
    record_audit(db, user, "ADMIN_REOPEN", "PURCHASE_ORDER", f"Reopened {item.po_number}", entity_id=item.id, before_data={"status": previous}, after_data={"status": "DRAFT"})


def _reopen_supplier_invoice(db: Session, item: SupplierInvoice, user) -> None:
    if Decimal(item.paid_amount or 0) > ZERO or Decimal(item.adjustment_amount or 0) > ZERO:
        raise HTTPException(
            status_code=409,
            detail="Unpost dependent supplier payments/adjustments before reopening this invoice.",
        )
    journal = _active_journal(db, "SUPPLIER_INVOICE", item.id)
    _void_draft_journal(db, journal, user)
    previous = item.status
    item.status = "DRAFT"
    item.verified_at = None
    item.posted_at = None
    payable = db.query(AccountPayable).filter(
        AccountPayable.supplier_id == item.supplier_id,
        AccountPayable.invoice_number == item.internal_invoice_number,
    ).first()
    if payable:
        db.delete(payable)
    record_audit(db, user, "ADMIN_REOPEN", "SUPPLIER_INVOICE", f"Reopened {item.internal_invoice_number}", entity_id=item.id, before_data={"status": previous}, after_data={"status": "DRAFT"})


def _reopen_payment(db: Session, item: Payment, user) -> None:
    journal = item.journal_entry or _active_journal(db, "SUPPLIER_PAYMENT", item.id)
    _void_draft_journal(db, journal, user)
    previous = item.status
    item.status = "DRAFT"
    item.journal_entry_id = None
    item.approved_by_id = None
    item.approved_at = None
    item.posted_by_id = None
    item.posted_at = None
    record_audit(db, user, "ADMIN_REOPEN", "PAYMENT", f"Reopened {item.payment_number}", entity_id=item.id, before_data={"status": previous}, after_data={"status": "DRAFT"})


def _reopen_bank_transfer(db: Session, item: BankTransfer, user) -> None:
    journal = item.journal_entry or _active_journal(db, "BANK_TRANSFER", item.id)
    _void_draft_journal(db, journal, user)
    previous = item.status
    item.status = "DRAFT"
    item.journal_entry_id = None
    item.posted_by_id = None
    item.posted_at = None
    record_audit(db, user, "ADMIN_REOPEN", "BANK_TRANSFER", f"Reopened {item.transfer_number}", entity_id=item.id, before_data={"status": previous}, after_data={"status": "DRAFT"})


def _reopen_supplier_adjustment(db: Session, item: SupplierAdjustment, user) -> None:
    journal = item.journal_entry or _active_journal(db, "SUPPLIER_ADJUSTMENT", item.id)
    _void_draft_journal(db, journal, user)
    previous = item.status
    item.status = "DRAFT"
    item.journal_entry_id = None
    item.posted_by_id = None
    item.posted_at = None
    record_audit(db, user, "ADMIN_REOPEN", "SUPPLIER_ADJUSTMENT", f"Reopened {item.adjustment_number}", entity_id=item.id, before_data={"status": previous}, after_data={"status": "DRAFT"})


def _reopen_goods_receipt(db: Session, item: GoodsReceipt, user) -> None:
    if item.status == "POSTED":
        raise HTTPException(status_code=409, detail="Return the posted receipt first so inventory is reversed before reopening it.")
    if item.status != "RETURNED":
        raise HTTPException(status_code=409, detail="Only a returned receipt can be reopened by an administrator.")
    downstream = db.query(SupplierInvoice).filter(
        SupplierInvoice.goods_receipt_id == item.id,
        SupplierInvoice.status != "VOID",
    ).first()
    if downstream:
        raise HTTPException(status_code=409, detail=f"Void/reopen supplier invoice {downstream.internal_invoice_number} before reopening this receipt.")
    item.status = "DRAFT"
    record_audit(db, user, "ADMIN_REOPEN", "GOODS_RECEIPT", f"Reopened {item.receipt_number}", entity_id=item.id, before_data={"status": "RETURNED"}, after_data={"status": "DRAFT"})


def _reopen_fixed_asset(db: Session, item: FixedAsset, user) -> None:
    posted = db.query(JournalEntry).filter(
        JournalEntry.reference_id == item.id,
        JournalEntry.reference_type.in_({"FIXED_ASSET_CAPITALIZATION", "FIXED_ASSET_DISPOSAL", "FIXED_ASSET_WRITE_OFF"}),
        JournalEntry.status == "POSTED",
    ).first()
    if posted:
        raise HTTPException(status_code=409, detail=f"Unpost journal {posted.journal_number} before reopening this fixed asset.")
    previous = item.status
    item.status = "DRAFT"
    record_audit(db, user, "ADMIN_REOPEN", "FIXED_ASSET", f"Reopened {item.asset_number}", entity_id=item.id, before_data={"status": previous}, after_data={"status": "DRAFT"})


@router.post("/{entity_type}/{entity_id}/reopen")
def reopen_document(entity_type: str, entity_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_admin(user)
    kind = entity_type.strip().upper().replace("-", "_")
    handlers = {
        "PURCHASE_REQUISITION": (PurchaseRequisition, _reopen_purchase_requisition),
        "PURCHASE_ORDER": (PurchaseOrder, _reopen_purchase_order),
        "SUPPLIER_INVOICE": (SupplierInvoice, _reopen_supplier_invoice),
        "PAYMENT": (Payment, _reopen_payment),
        "BANK_TRANSFER": (BankTransfer, _reopen_bank_transfer),
        "SUPPLIER_ADJUSTMENT": (SupplierAdjustment, _reopen_supplier_adjustment),
        "GOODS_RECEIPT": (GoodsReceipt, _reopen_goods_receipt),
        "FIXED_ASSET": (FixedAsset, _reopen_fixed_asset),
    }
    if kind not in handlers:
        raise HTTPException(status_code=400, detail=f"Admin reopen is not configured for {kind}")
    model, handler = handlers[kind]
    item = db.get(model, entity_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"{kind.replace('_', ' ').title()} not found")
    if getattr(item, "status", None) == "DRAFT":
        return {"entity_type": kind, "entity_id": entity_id, "status": "DRAFT", "message": "Document is already draft"}
    handler(db, item, user)
    db.commit()
    db.refresh(item)
    return {"entity_type": kind, "entity_id": entity_id, "status": item.status, "message": "Document reopened for administrator correction"}


def _reverse_payment_source(db: Session, journal: JournalEntry) -> None:
    payment = db.get(Payment, journal.reference_id)
    if not payment:
        return
    for allocation in payment.allocations:
        invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == allocation.supplier_invoice_id).with_for_update().one()
        invoice.paid_amount = max(ZERO, Decimal(invoice.paid_amount or 0) - Decimal(allocation.allocated_amount or 0))
        _sync_payable(db, invoice)
    payment.status = "APPROVED"
    payment.posted_by_id = None
    payment.posted_at = None


def _reverse_supplier_adjustment_source(db: Session, journal: JournalEntry) -> None:
    adjustment = db.get(SupplierAdjustment, journal.reference_id)
    if not adjustment:
        return
    invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == adjustment.supplier_invoice_id).with_for_update().one()
    invoice.adjustment_amount = max(ZERO, Decimal(invoice.adjustment_amount or 0) - Decimal(adjustment.amount or 0))
    _sync_payable(db, invoice)
    adjustment.status = "DRAFT"
    adjustment.posted_by_id = None
    adjustment.posted_at = None


def _reverse_bank_transfer_source(db: Session, journal: JournalEntry) -> None:
    transfer = db.get(BankTransfer, journal.reference_id)
    if not transfer:
        return
    transfer.status = "DRAFT"
    transfer.posted_by_id = None
    transfer.posted_at = None


def _reverse_amortization_source(db: Session, journal: JournalEntry) -> None:
    item = db.query(Amortization).filter(Amortization.id == journal.reference_id).with_for_update().first()
    if not item:
        return
    amount = sum((Decimal(line.debit or 0) for line in journal.lines), ZERO)
    item.months_posted = max(0, int(item.months_posted or 0) - 1)
    item.accumulated_amortization = max(ZERO, Decimal(item.accumulated_amortization or 0) - amount)
    item.net_book_value = max(ZERO, Decimal(item.original_cost or 0) - Decimal(item.accumulated_amortization or 0))
    item.status = "ACTIVE"
    previous = db.query(JournalEntry).filter(
        JournalEntry.reference_type == "AMORTIZATION",
        JournalEntry.reference_id == item.id,
        JournalEntry.status == "POSTED",
        JournalEntry.id != journal.id,
    ).order_by(JournalEntry.posting_date.desc(), JournalEntry.id.desc()).first()
    item.last_posted_at = previous.posted_at if previous else None


def _reverse_fixed_asset_source(db: Session, journal: JournalEntry) -> None:
    ref = journal.reference_type
    if ref == "FIXED_ASSET_DEPRECIATION":
        run = db.get(FixedAssetDepreciationRun, journal.reference_id)
        schedules = db.query(FixedAssetDepreciationSchedule).filter(FixedAssetDepreciationSchedule.journal_entry_id == journal.id).all()
        for schedule in schedules:
            asset = schedule.asset
            amount = Decimal(schedule.depreciation_amount or 0)
            asset.accumulated_depreciation = max(ZERO, Decimal(asset.accumulated_depreciation or 0) - amount)
            asset.net_book_value = max(ZERO, Decimal(asset.acquisition_cost or 0) - Decimal(asset.accumulated_depreciation or 0))
            asset.status = "FULLY_DEPRECIATED" if asset.net_book_value <= Decimal(asset.residual_value or 0) else "ACTIVE"
            schedule.status = "GENERATED"
            schedule.journal_entry_id = None
            schedule.posted_at = None
        if run:
            run.status = "CALCULATED"
            run.journal_entry_id = None
            run.posted_by_id = None
            run.posted_at = None
        return

    asset = db.get(FixedAsset, journal.reference_id)
    if not asset:
        return
    if ref == "FIXED_ASSET_CAPITALIZATION":
        posted_depreciation = db.query(FixedAssetDepreciationSchedule).filter(
            FixedAssetDepreciationSchedule.fixed_asset_id == asset.id,
            FixedAssetDepreciationSchedule.status == "POSTED",
        ).first()
        if posted_depreciation:
            raise HTTPException(status_code=409, detail="Unpost posted depreciation before unposting asset capitalization.")
        db.query(FixedAssetDepreciationSchedule).filter(
            FixedAssetDepreciationSchedule.fixed_asset_id == asset.id,
            FixedAssetDepreciationSchedule.status.in_({"PLANNED", "GENERATED", "SKIPPED"}),
        ).delete(synchronize_session=False)
        asset.status = "DRAFT"
        asset.capitalization_date = None
        asset.depreciation_start_date = None
    elif ref in {"FIXED_ASSET_DISPOSAL", "FIXED_ASSET_WRITE_OFF"}:
        asset.status = "FULLY_DEPRECIATED" if Decimal(asset.net_book_value or 0) <= Decimal(asset.residual_value or 0) else "ACTIVE"
        asset.disposed_at = None
        asset.written_off_at = None
        db.query(FixedAssetDepreciationSchedule).filter(
            FixedAssetDepreciationSchedule.fixed_asset_id == asset.id,
            FixedAssetDepreciationSchedule.status == "SKIPPED",
        ).update({"status": "PLANNED"}, synchronize_session=False)
        movement = db.query(FixedAssetMovement).filter(
            FixedAssetMovement.fixed_asset_id == asset.id,
            FixedAssetMovement.reference_number == journal.journal_number,
        ).first()
        if movement:
            db.delete(movement)


def _sync_source_after_unpost(db: Session, journal: JournalEntry) -> None:
    if journal.reference_type == "SUPPLIER_INVOICE":
        invoice = db.get(SupplierInvoice, journal.reference_id)
        if invoice:
            invoice.status = "VERIFIED"
            invoice.posted_at = None
    elif journal.reference_type == "SUPPLIER_PAYMENT":
        _reverse_payment_source(db, journal)
    elif journal.reference_type == "SUPPLIER_ADJUSTMENT":
        _reverse_supplier_adjustment_source(db, journal)
    elif journal.reference_type == "BANK_TRANSFER":
        _reverse_bank_transfer_source(db, journal)
    elif journal.reference_type == "AMORTIZATION":
        _reverse_amortization_source(db, journal)
    elif journal.reference_type.startswith("FIXED_ASSET_"):
        _reverse_fixed_asset_source(db, journal)


@router.post("/journals/{journal_id}/unpost")
def admin_unpost_journal(journal_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_admin(user)
    journal = db.query(JournalEntry).filter(JournalEntry.id == journal_id).with_for_update().first()
    if not journal:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    if journal.status != "POSTED":
        raise HTTPException(status_code=409, detail="Only posted journals can be unposted")

    # The fiscal period/GL is the hard accounting lock. ADMIN can override
    # operational document states, but cannot silently rewrite a closed period.
    FiscalPeriodService.validate_posting_date(db=db, posting_date=journal.posting_date)

    # Reverse the source state before removing ledger rows. Source-specific
    # dependencies (payments, adjustments, depreciation, etc.) are updated in
    # the same transaction so operational and accounting state remain aligned.
    _sync_source_after_unpost(db, journal)

    gl_rows = db.query(GeneralLedger).filter(
        GeneralLedger.reference_number == journal.journal_number,
        GeneralLedger.reference_type == journal.reference_type,
        GeneralLedger.reference_id == journal.reference_id,
    ).all()
    for row in gl_rows:
        db.delete(row)

    previous_posted_at = journal.posted_at
    journal.status = "DRAFT"
    journal.posted_by_id = None
    journal.posted_at = None
    record_audit(
        db,
        user,
        "ADMIN_JOURNAL_UNPOSTED",
        "JOURNAL_ENTRY",
        f"Administrator unposted {journal.journal_number}",
        entity_id=journal.id,
        reference_document=journal.document_number,
        before_data={"status": "POSTED", "posted_at": str(previous_posted_at) if previous_posted_at else None},
        after_data={"status": "DRAFT", "ledger_rows_removed": len(gl_rows)},
    )
    db.commit()
    db.refresh(journal)
    return {
        "id": journal.id,
        "journal_number": journal.journal_number,
        "status": journal.status,
        "reference_type": journal.reference_type,
        "reference_id": journal.reference_id,
        "ledger_rows_removed": len(gl_rows),
    }

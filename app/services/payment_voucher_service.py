from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.payment_voucher import PaymentVoucher, PaymentVoucherAllocation
from app.models.supplier_invoice import SupplierInvoice
from app.services.document_number import next_document_number
from app.services.location_access import enforce_location_access

ZERO = Decimal("0")
OPEN_STATUSES = {"POSTED"}


def _voucher_number(db: Session) -> str:
    return next_document_number(db, "PV", digits=5, day=True)


def _invoice_balance(inv: SupplierInvoice) -> Decimal:
    return max(ZERO, Decimal(inv.total_amount or 0) - Decimal(inv.paid_amount or 0) - Decimal(inv.adjustment_amount or 0))


def _validate_invoices(db: Session, location_id: int, allocations, exclude_voucher_id: int | None = None):
    if not allocations:
        raise HTTPException(422, "Voucher requires at least one invoice")
    seen = set()
    invoices = []
    for alloc in allocations:
        if alloc.supplier_invoice_id in seen:
            raise HTTPException(422, "Duplicate invoice in voucher")
        seen.add(alloc.supplier_invoice_id)
        inv = db.get(SupplierInvoice, alloc.supplier_invoice_id)
        if not inv:
            raise HTTPException(404, f"Invoice {alloc.supplier_invoice_id} not found")
        if inv.location_id != location_id:
            raise HTTPException(422, f"Invoice {inv.internal_invoice_number} location does not match voucher location")
        if inv.status not in OPEN_STATUSES or inv.payment_status == "PAID":
            raise HTTPException(409, f"Invoice {inv.internal_invoice_number} is not payable")
        # check already allocated to another voucher (not rejected/void)
        q = db.query(PaymentVoucherAllocation).join(PaymentVoucher).filter(
            PaymentVoucherAllocation.supplier_invoice_id == inv.id,
            PaymentVoucher.status.notin_(["REJECTED", "VOID", "CANCELLED"]),
        )
        if exclude_voucher_id:
            q = q.filter(PaymentVoucher.id != exclude_voucher_id)
        existing = q.first()
        if existing:
            raise HTTPException(409, f"Invoice {inv.internal_invoice_number} already in voucher {existing.voucher.voucher_number}")
        # check already allocated to approved payment
        from app.api.v1.payments import reserved_amount, invoice_balance
        available = _invoice_balance(inv) - reserved_amount(db, inv.id)
        if Decimal(alloc.allocated_amount) <= ZERO or Decimal(alloc.allocated_amount) > available:
            raise HTTPException(409, f"Allocation for {inv.internal_invoice_number} exceeds available {available}")
        invoices.append(inv)
    return invoices


def create(db: Session, data, user):
    enforce_location_access(user, data.location_id)
    invoices = _validate_invoices(db, data.location_id, data.allocations)
    total = sum((Decimal(a.allocated_amount) for a in data.allocations), ZERO)
    # derive period from invoices if not provided
    period_from = data.period_from or min((inv.invoice_date for inv in invoices), default=data.voucher_date)
    period_to = data.period_to or max((inv.invoice_date for inv in invoices), default=data.voucher_date)
    # inherit BU/dept from first invoice if not provided (must be same location, BU/dept should match)
    first = invoices[0]
    voucher = PaymentVoucher(
        voucher_number=_voucher_number(db),
        voucher_date=data.voucher_date,
        location_id=data.location_id,
        business_unit_id=first.business_unit_id,
        department_id=first.department_id,
        period_from=period_from,
        period_to=period_to,
        total_amount=total,
        status="DRAFT",
        notes=data.notes,
        source_type=data.source_type,
        created_by_id=user.id,
    )
    db.add(voucher)
    db.flush()
    for alloc in data.allocations:
        db.add(PaymentVoucherAllocation(
            voucher_id=voucher.id,
            supplier_invoice_id=alloc.supplier_invoice_id,
            allocated_amount=Decimal(alloc.allocated_amount),
        ))
    db.flush()
    return voucher


def submit(db: Session, voucher_id: int, user):
    v = db.get(PaymentVoucher, voucher_id)
    if not v or v.status != "DRAFT":
        raise HTTPException(409, "Only draft vouchers can be submitted")
    enforce_location_access(user, v.location_id)
    v.status = "PENDING_APPROVAL"
    db.commit()
    db.refresh(v)
    return v


def approve(db: Session, voucher_id: int, user):
    v = db.query(PaymentVoucher).filter(PaymentVoucher.id == voucher_id).with_for_update().first()
    if not v or v.status != "PENDING_APPROVAL":
        raise HTTPException(409, "Only pending vouchers can be approved")
    enforce_location_access(user, v.location_id)
    # Approval only advances the voucher. The actual supplier Payment is created
    # explicitly from this approved voucher via Create Payment.
    v.status = "APPROVED"
    v.approved_by_id = user.id
    v.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(v)
    return v


def reject(db: Session, voucher_id: int, user, reason: str | None = None):
    v = db.query(PaymentVoucher).filter(PaymentVoucher.id == voucher_id).with_for_update().first()
    if not v or v.status != "PENDING_APPROVAL":
        raise HTTPException(409, "Only pending vouchers can be rejected")
    enforce_location_access(user, v.location_id)
    v.status = "REJECTED"
    if reason:
        v.notes = (v.notes or "") + f"\nRejected: {reason}"
    db.commit()
    db.refresh(v)
    return v


def void(db: Session, voucher_id: int, user):
    v = db.get(PaymentVoucher, voucher_id)
    if not v or v.status in ("PAID", "VOID"):
        raise HTTPException(409, "Cannot void this voucher")
    enforce_location_access(user, v.location_id)
    if v.payment_id:
        pay = db.get(Payment, v.payment_id)
        if pay and pay.status == "POSTED":
            raise HTTPException(409, "Voucher payment already posted, void the payment first")
    v.status = "VOID"
    db.commit()
    db.refresh(v)
    return v

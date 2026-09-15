from collections import defaultdict
from datetime import date
from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import require_permission
from app.models.payment_voucher import PaymentVoucher
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.schemas.payment_voucher import PaymentVoucherCreate
from app.services import payment_voucher_service as svc
from app.services.document_context import document_context, print_metadata
from app.services.location_access import apply_location_scope

router = APIRouter(prefix="/payment-vouchers", tags=["Payment Vouchers"])
view_user = require_permission("payment.view")
manage_user = require_permission("payment.manage")


def serialize(v: PaymentVoucher):
    # group allocations by supplier for print
    by_supplier = defaultdict(list)
    for a in v.allocations:
        inv = a.supplier_invoice
        by_supplier[inv.supplier_id].append(a)
    groups = []
    for supplier_id, allocs in by_supplier.items():
        invs = [a.supplier_invoice for a in allocs]
        supplier = invs[0].supplier if invs else None
        total = sum((Decimal(a.allocated_amount) for a in allocs), Decimal("0"))
        # bank info from supplier if available
        bank = None
        if supplier and supplier.bank_name:
            bank = {"bank_name": supplier.bank_name, "account_number": supplier.bank_account_number, "account_name": supplier.bank_account_name}
        groups.append({
            "supplier_id": supplier_id,
            "supplier_name": supplier.name if supplier else None,
            "supplier_code": supplier.code if supplier else None,
            "bank": bank,
            "total": total,
            "invoices": [{
                "id": a.supplier_invoice.id,
                "invoice_number": a.supplier_invoice.internal_invoice_number,
                "supplier_invoice_number": a.supplier_invoice.supplier_invoice_number,
                "invoice_date": a.supplier_invoice.invoice_date,
                "due_date": a.supplier_invoice.due_date,
                "total_amount": a.supplier_invoice.total_amount,
                "allocated_amount": a.allocated_amount,
            } for a in allocs],
        })
    return {
        "id": v.id,
        "voucher_number": v.voucher_number,
        "voucher_date": v.voucher_date,
        "location_id": v.location_id,
        "location_name": v.location.name if v.location else None,
        "business_unit_id": v.business_unit_id,
        "business_unit_name": v.business_unit.name if v.business_unit else None,
        "department_id": v.department_id,
        "department_name": v.department.name if v.department else None,
        "period_from": v.period_from,
        "period_to": v.period_to,
        "total_amount": v.total_amount,
        "status": v.status,
        "notes": v.notes,
        "payment_id": v.payment_id,
        "created_by_name": v.created_by.full_name if v.created_by else None,
        "approved_by_name": v.approved_by.full_name if v.approved_by else None,
        "created_at": v.created_at,
        "approved_at": v.approved_at,
        "groups": groups,
        "allocations": [{
            "id": a.id,
            "supplier_invoice_id": a.supplier_invoice_id,
            "invoice_number": a.supplier_invoice.internal_invoice_number,
            "supplier_invoice_number": a.supplier_invoice.supplier_invoice_number,
            "supplier_name": a.supplier_invoice.supplier.name if a.supplier_invoice.supplier else None,
            "invoice_date": a.supplier_invoice.invoice_date,
            "total_amount": a.supplier_invoice.total_amount,
            "allocated_amount": a.allocated_amount,
        } for a in v.allocations],
    }


@router.get("/eligible-invoices")
def eligible_invoices(
    location_id: int = Query(..., description="Location to filter"),
    supplier_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(manage_user),
):
    q = apply_location_scope(db.query(SupplierInvoice), SupplierInvoice, user).filter(
        SupplierInvoice.location_id == location_id,
        SupplierInvoice.status == "POSTED",
    )
    # only unpaid
    q = q.filter(SupplierInvoice.payment_status != "PAID")
    if supplier_id:
        q = q.filter(SupplierInvoice.supplier_id == supplier_id)
    rows = q.order_by(SupplierInvoice.due_date.asc().nullslast(), SupplierInvoice.id).all()
    # filter out already allocated to voucher
    result = []
    for inv in rows:
        # check if already in a non-rejected voucher
        from app.models.payment_voucher import PaymentVoucherAllocation
        existing = db.query(PaymentVoucherAllocation).join(PaymentVoucher).filter(
            PaymentVoucherAllocation.supplier_invoice_id == inv.id,
            PaymentVoucher.status.notin_(["REJECTED", "VOID", "CANCELLED"]),
        ).first()
        if existing:
            continue
        # also check reserved by approved payment
        from app.api.v1.payments import invoice_balance, reserved_amount
        outstanding = invoice_balance(inv)
        reserved = reserved_amount(db, inv.id)
        available = max(Decimal("0"), outstanding - reserved)
        if available <= 0:
            continue
        result.append({
            "id": inv.id,
            "invoice_number": inv.internal_invoice_number,
            "supplier_invoice_number": inv.supplier_invoice_number,
            "supplier_id": inv.supplier_id,
            "supplier_name": inv.supplier.name if inv.supplier else None,
            "invoice_date": inv.invoice_date,
            "due_date": inv.due_date,
            "total_amount": inv.total_amount,
            "paid_amount": inv.paid_amount,
            "outstanding_balance": outstanding,
            "available_balance": available,
            "currency": inv.currency,
        })
    return result


@router.get("")
def listing(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    location_id: int | None = None,
    search: str | None = None,
    date_from: date | None = Query(None, description="Voucher date from (inclusive)"),
    date_to: date | None = Query(None, description="Voucher date to (inclusive)"),
    db: Session = Depends(get_db),
    user=Depends(view_user),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "date_from must be on or before date_to")
    q = apply_location_scope(db.query(PaymentVoucher), PaymentVoucher, user)
    if status:
        q = q.filter(PaymentVoucher.status == status)
    if location_id:
        q = q.filter(PaymentVoucher.location_id == location_id)
    if search:
        q = q.filter(PaymentVoucher.voucher_number.ilike(f"%{search}%"))
    if date_from:
        q = q.filter(PaymentVoucher.voucher_date >= date_from)
    if date_to:
        q = q.filter(PaymentVoucher.voucher_date <= date_to)
    total = q.count()
    rows = q.order_by(PaymentVoucher.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {
        "items": [serialize(r) for r in rows],
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": ceil(total/page_size) if total else 0,
        "has_next": page*page_size < total,
        "has_previous": page > 1,
    }


@router.get("/{voucher_id}")
def detail(voucher_id: int, db: Session = Depends(get_db), user=Depends(view_user)):
    v = db.get(PaymentVoucher, voucher_id)
    if not v:
        raise HTTPException(404, "Voucher not found")
    from app.services.location_access import enforce_location_access
    enforce_location_access(user, v.location_id)
    data = serialize(v)
    data.update(document_context(db, "PAYMENT_VOUCHER", v.id, v.status, user))
    data["allowed_actions"] = {
        "can_submit": v.status == "DRAFT",
        "can_approve": v.status == "PENDING_APPROVAL",
        "can_reject": v.status == "PENDING_APPROVAL",
        "can_void": v.status in ("DRAFT", "PENDING_APPROVAL"),
        "can_print": True,
    }
    return data


@router.post("", status_code=201)
def create(data: PaymentVoucherCreate, db: Session = Depends(get_db), user=Depends(manage_user)):
    v = svc.create(db, data, user)
    db.commit()
    db.refresh(v)
    return serialize(v)


@router.post("/{voucher_id}/submit")
def submit(voucher_id: int, db: Session = Depends(get_db), user=Depends(manage_user)):
    v = svc.submit(db, voucher_id, user)
    return serialize(v)


@router.post("/{voucher_id}/approve")
def approve(voucher_id: int, db: Session = Depends(get_db), user=Depends(manage_user)):
    v = svc.approve(db, voucher_id, user)
    return serialize(v)


@router.post("/{voucher_id}/reject")
def reject(voucher_id: int, body: dict | None = None, db: Session = Depends(get_db), user=Depends(manage_user)):
    reason = (body or {}).get("reason") if body else None
    v = svc.reject(db, voucher_id, user, reason)
    return serialize(v)


@router.post("/{voucher_id}/void")
def void(voucher_id: int, db: Session = Depends(get_db), user=Depends(manage_user)):
    v = svc.void(db, voucher_id, user)
    return serialize(v)

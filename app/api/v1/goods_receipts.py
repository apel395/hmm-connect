from datetime import date, timedelta
from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission, require_permission
from app.models.approval_request import ApprovalRequest
from app.models.department import Department
from app.models.goods_receipt import GoodsReceipt
from app.models.location import Location
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.goods_receipt import GoodsReceiptCostCorrection, GoodsReceiptCreate, GoodsReceiptUpdate
from app.services.approval import (
    approve_current_step,
    can_user_decide_step,
    can_user_edit_pending_approval,
    current_steps,
    get_request,
    reject_current_step,
    start_approval,
)
from app.services.document_context import document_context, print_metadata
from app.services.goods_receipt_service import GoodsReceiptService
from app.services.location_access import (
    apply_location_scope,
    enforce_warehouse_access,
    require_location_access,
    resolve_location_id,
)

router = APIRouter(prefix="/goods-receipts", tags=["Goods Receipts"])
receiving_view_user = require_permission("receiving.view")
receiving_create_user = require_permission("receiving.create")
receiving_edit_user = require_permission("receiving.edit")
receiving_submit_user = require_permission("receiving.submit")
receiving_approve_user = require_permission("receiving.approve")
receiving_post_user = require_permission("receiving.post")
receiving_return_user = require_permission("receiving.return")
receiving_manage_user = require_permission("receiving.manage")


def _scoped_receipt(db: Session, receipt_id: int, user) -> GoodsReceipt:
    receipt = db.get(GoodsReceipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "Goods receipt not found")
    require_location_access(receipt.location_id, user)
    return receipt


def _scoped_receipt_for_update(db: Session, receipt_id: int, user) -> GoodsReceipt:
    receipt = (
        db.query(GoodsReceipt)
        .filter(GoodsReceipt.id == receipt_id)
        .with_for_update()
        .first()
    )
    if not receipt:
        raise HTTPException(404, "Goods receipt not found")
    require_location_access(receipt.location_id, user)
    return receipt


def receipt_actions(receipt: GoodsReceipt, user, db: Session):
    approval = get_request(db, "GOODS_RECEIPT", receipt.id)
    approval_status = approval.status if approval else None
    can_decide = bool(
        approval
        and approval.status == "PENDING"
        and any(can_user_decide_step(step, user) for step in current_steps(approval))
    )
    can_edit = bool(
        receipt.status == "DRAFT"
        and has_permission(user, "receiving.edit")
        and (
            approval is None
            or (approval.status == "PENDING" and can_user_edit_pending_approval(approval, user))
        )
    )
    return {
        "can_edit": can_edit,
        "can_submit": receipt.status == "DRAFT" and receipt.source_type != "HISTORICAL_ENTRY" and approval is None and has_permission(user, "receiving.submit"),
        "can_approve": can_decide and has_permission(user, "receiving.approve"),
        "can_reject": can_decide and has_permission(user, "receiving.approve"),
        "can_post": receipt.status == "DRAFT" and (approval_status == "APPROVED" or (receipt.source_type == "HISTORICAL_ENTRY" and approval is None)) and has_permission(user, "receiving.post"),
        "can_return": receipt.status == "POSTED" and has_permission(user, "receiving.return"),
        "can_correct_cost": receipt.status == "POSTED" and GoodsReceiptService.can_correct_cost(user),
        "can_print": True,
        "can_view_history": True,
        "can_manage_attachments": True,
    }


def serialize_receipt(receipt: GoodsReceipt, db: Session | None = None):
    purchase_order = receipt.purchase_order
    supplier = purchase_order.supplier if purchase_order else receipt.supplier
    approval = get_request(db, "GOODS_RECEIPT", receipt.id) if db else None
    return {
        "id": receipt.id,
        "receipt_number": receipt.receipt_number,
        "status": receipt.status,
        "approval_status": approval.status if approval else None,
        "approval_current_step": approval.current_step_order if approval else None,
        "purchase_order_id": receipt.purchase_order_id,
        "purchase_order_number": purchase_order.po_number if purchase_order else None,
        "source_mode": "PO" if purchase_order else "DIRECT",
        "supplier_id": purchase_order.supplier_id if purchase_order else receipt.supplier_id,
        "supplier_name": supplier.name if supplier else None,
        "received_by_id": receipt.received_by_id,
        "received_by_name": receipt.received_by.full_name if receipt.received_by else None,
        "received_at": receipt.received_at,
        "source_type": receipt.source_type,
        "external_reference": receipt.external_reference,
        "delivery_note_number": receipt.external_reference,
        "receipt_type": receipt.receipt_type,
        "destination_type": receipt.destination_type,
        "warehouse_id": receipt.warehouse_id,
        "warehouse_name": receipt.warehouse.name if receipt.warehouse else None,
        "business_unit_id": receipt.business_unit_id,
        "business_unit_name": receipt.business_unit.name if receipt.business_unit else None,
        "location_id": receipt.location_id,
        "location_name": receipt.location.name if receipt.location else None,
        "department_id": receipt.department_id,
        "department_name": receipt.department.name if receipt.department else None,
        "notes": receipt.notes,
        "subtotal": receipt.subtotal,
        "tax_amount": receipt.tax_amount,
        "total_amount": receipt.total_amount,
        "total_value": receipt.total_amount or sum(Decimal(item.quantity) * Decimal(item.unit_cost) for item in receipt.items),
        "items": [
            {
                "id": item.id,
                "purchase_order_item_id": item.purchase_order_item_id,
                "product_id": item.product_id,
                "product_code": item.product.code if item.product else None,
                "product_name": item.product.name if item.product else None,
                "uom": (item.purchase_order_item.uom if item.purchase_order_item else None) or (item.product.uom if item.product else None),
                "quantity": item.quantity,
                "unit_cost": item.unit_cost,
                "line_subtotal": Decimal(item.quantity) * Decimal(item.unit_cost),
                "is_taxable": item.is_taxable,
                "tax_rate": item.tax_rate,
                "tax_amount": item.tax_amount,
                "line_total": Decimal(item.quantity) * Decimal(item.unit_cost) + Decimal(item.tax_amount or 0),
            }
            for item in receipt.items
        ],
    }


def serialize_receipt_summary(receipt: GoodsReceipt, approval: ApprovalRequest | None = None):
    purchase_order = receipt.purchase_order
    supplier = purchase_order.supplier if purchase_order else receipt.supplier
    return {
        "id": receipt.id,
        "receipt_number": receipt.receipt_number,
        "status": receipt.status,
        "approval_status": approval.status if approval else None,
        "approval_current_step": approval.current_step_order if approval else None,
        "purchase_order_id": receipt.purchase_order_id,
        "purchase_order_number": purchase_order.po_number if purchase_order else None,
        "source_mode": "PO" if purchase_order else "DIRECT",
        "supplier_id": purchase_order.supplier_id if purchase_order else receipt.supplier_id,
        "supplier_name": supplier.name if supplier else None,
        "received_by_id": receipt.received_by_id,
        "received_by_name": receipt.received_by.full_name if receipt.received_by else None,
        "received_at": receipt.received_at,
        "external_reference": receipt.external_reference,
        "destination_type": receipt.destination_type,
        "warehouse_id": receipt.warehouse_id,
        "warehouse_name": receipt.warehouse.name if receipt.warehouse else None,
        "business_unit_id": receipt.business_unit_id,
        "business_unit_name": receipt.business_unit.name if receipt.business_unit else None,
        "location_id": receipt.location_id,
        "location_name": receipt.location_name if hasattr(receipt, "location_name") else None,
        "department_id": receipt.department_id,
        "department_name": receipt.department.name if receipt.department else None,
        "subtotal": receipt.subtotal,
        "tax_amount": receipt.tax_amount,
        "total_amount": receipt.total_amount,
    }


def remaining_items(purchase_order: PurchaseOrder):
    return [
        {
            "purchase_order_item_id": item.id,
            "product_id": item.product_id,
            "product_code": item.product.code if item.product else None,
            "product_name": item.product.name if item.product else None,
            "uom": item.uom or (item.product.uom if item.product else None),
            "ordered_quantity": item.quantity,
            "received_quantity": item.received_quantity,
            "remaining_quantity": Decimal(item.quantity) - Decimal(item.received_quantity or 0),
            "unit_cost": item.unit_price,
            "is_taxable": item.is_taxable,
            "tax_rate": item.tax_rate,
        }
        for item in purchase_order.items
        if Decimal(item.quantity) > Decimal(item.received_quantity or 0)
    ]


def inherit_purchase_order_dimensions(order: PurchaseOrder, data: GoodsReceiptCreate, db: Session):
    business_unit_id, location_id, department_id = GoodsReceiptService._po_dimensions(order)
    data.business_unit_id = business_unit_id
    data.location_id = location_id
    data.department_id = department_id
    db.flush()


@router.get("")
def list_receipts(
    purchase_order_id: int | None = None,
    destination_type: str | None = None,
    status: str | None = None,
    approval_status: str | None = None,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(receiving_view_user),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "date_from must be on or before date_to")
    query = apply_location_scope(
        db.query(GoodsReceipt),
        GoodsReceipt.location_id,
        user,
    ).options(
        selectinload(GoodsReceipt.purchase_order).selectinload(PurchaseOrder.supplier),
        selectinload(GoodsReceipt.supplier),
        selectinload(GoodsReceipt.received_by),
        selectinload(GoodsReceipt.warehouse),
        selectinload(GoodsReceipt.business_unit),
        selectinload(GoodsReceipt.department),
        selectinload(GoodsReceipt.location),
    )
    if purchase_order_id:
        query = query.filter(GoodsReceipt.purchase_order_id == purchase_order_id)
    if destination_type:
        query = query.filter(GoodsReceipt.destination_type == destination_type.upper())
    if status:
        query = query.filter(GoodsReceipt.status == status.upper())
    if date_from:
        query = query.filter(GoodsReceipt.received_at >= date_from)
    if date_to:
        query = query.filter(GoodsReceipt.received_at < date_to + timedelta(days=1))
    if approval_status:
        query = query.join(
            ApprovalRequest,
            (ApprovalRequest.entity_type == "GOODS_RECEIPT") & (ApprovalRequest.entity_id == GoodsReceipt.id),
        ).filter(ApprovalRequest.status == approval_status.upper())
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(
            GoodsReceipt.receipt_number.ilike(term),
            GoodsReceipt.external_reference.ilike(term),
            GoodsReceipt.purchase_order.has(PurchaseOrder.po_number.ilike(term)),
            GoodsReceipt.supplier.has(Supplier.name.ilike(term)),
            GoodsReceipt.purchase_order.has(PurchaseOrder.supplier.has(Supplier.name.ilike(term))),
            GoodsReceipt.received_by.has(User.full_name.ilike(term)),
            GoodsReceipt.warehouse.has(Warehouse.name.ilike(term)),
            GoodsReceipt.location.has(Location.name.ilike(term)),
            GoodsReceipt.department.has(Department.name.ilike(term)),
        ))

    total = query.count()
    rows = query.order_by(GoodsReceipt.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    row_ids = [receipt.id for receipt in rows]
    approvals = (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.entity_type == "GOODS_RECEIPT",
            ApprovalRequest.entity_id.in_(row_ids),
        )
        .all()
        if row_ids else []
    )
    approval_map = {approval.entity_id: approval for approval in approvals}
    total_pages = ceil(total / page_size) if total else 0
    scoped_summary = apply_location_scope(
        db.query(GoodsReceipt),
        GoodsReceipt.location_id,
        user,
    )
    waiting = scoped_summary.join(
        ApprovalRequest,
        (ApprovalRequest.entity_type == "GOODS_RECEIPT") & (ApprovalRequest.entity_id == GoodsReceipt.id),
    ).filter(ApprovalRequest.status == "PENDING").count()
    ready = scoped_summary.join(
        ApprovalRequest,
        (ApprovalRequest.entity_type == "GOODS_RECEIPT") & (ApprovalRequest.entity_id == GoodsReceipt.id),
    ).filter(GoodsReceipt.status == "DRAFT", ApprovalRequest.status == "APPROVED").count()
    posted = scoped_summary.filter(GoodsReceipt.status == "POSTED").count()
    return {
        "items": [{**serialize_receipt_summary(item, approval_map.get(item.id)),
                   "source_type": item.source_type,
                   "allowed_actions": {
                       "can_submit": item.status == "DRAFT" and item.source_type != "HISTORICAL_ENTRY" and item.id not in approval_map and has_permission(user, "receiving.submit"),
                       "can_post": item.status == "DRAFT" and has_permission(user, "receiving.post") and ((item.source_type == "HISTORICAL_ENTRY" and item.id not in approval_map) or (item.id in approval_map and approval_map[item.id].status == "APPROVED")),
                   }} for item in rows],
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
        "summary": {"waiting_approval": waiting, "approved_to_post": ready, "posted": posted},
    }


@router.get("/receivable-purchase-orders")
def list_receivable_purchase_orders(db: Session = Depends(get_db), user=Depends(receiving_create_user)):
    orders = (
        apply_location_scope(db.query(PurchaseOrder), PurchaseOrder.location_id, user)
        .filter(PurchaseOrder.status.in_({"APPROVED", "PARTIALLY_RECEIVED"}))
        .order_by(PurchaseOrder.id.desc())
        .all()
    )
    return [
        {
            "id": order.id,
            "po_number": order.po_number,
            "supplier_id": order.supplier_id,
            "supplier_name": order.supplier.name if order.supplier else None,
            "status": order.status,
            "business_unit_id": order.business_unit_id,
            "business_unit_name": order.business_unit.name if order.business_unit else None,
            "department_id": order.department_id,
            "department_name": order.department.name if order.department else None,
            "location_id": order.location_id,
            "location_name": order.location.name if order.location else None,
            "tax_amount": order.tax_amount,
            "total_amount": order.total_amount,
            "items": remaining_items(order),
        }
        for order in orders
        if remaining_items(order)
    ]


@router.get("/receivable-purchase-orders/{purchase_order_id}/items")
def get_remaining_purchase_order_items(purchase_order_id: int, db: Session = Depends(get_db), user=Depends(receiving_create_user)):
    order = db.get(PurchaseOrder, purchase_order_id)
    if not order:
        raise HTTPException(404, "Purchase order not found")
    require_location_access(order.location_id, user)
    if order.status not in {"APPROVED", "PARTIALLY_RECEIVED"}:
        raise HTTPException(409, "Purchase order is not receivable")
    return remaining_items(order)


@router.post("", status_code=201)
def create_receipt(data: GoodsReceiptCreate, db: Session = Depends(get_db), user=Depends(receiving_create_user)):
    if data.purchase_order_id:
        order = db.get(PurchaseOrder, data.purchase_order_id)
        if not order:
            raise HTTPException(404, "Purchase order not found")
        require_location_access(order.location_id, user)
        inherit_purchase_order_dimensions(order, data, db)
    else:
        data.location_id = resolve_location_id(user, data.location_id)
    if data.warehouse_id:
        warehouse = db.get(Warehouse, data.warehouse_id)
        if not warehouse:
            raise HTTPException(404, "Warehouse not found")
        enforce_warehouse_access(user, warehouse)
    return serialize_receipt(GoodsReceiptService.create(db=db, data=data, user=user), db)


@router.put("/{receipt_id}")
@router.patch("/{receipt_id}")
def update_receipt(
    receipt_id: int,
    data: GoodsReceiptUpdate,
    db: Session = Depends(get_db),
    user=Depends(receiving_edit_user),
):
    receipt = _scoped_receipt_for_update(db, receipt_id, user)
    approval = get_request(db, "GOODS_RECEIPT", receipt.id)
    if approval is not None:
        if approval.status != "PENDING" or not can_user_edit_pending_approval(approval, user):
            raise HTTPException(403, "User cannot edit this Receiving Report at the current approval stage")
    updated = GoodsReceiptService.update(db=db, receipt=receipt, data=data, user=user)
    result = serialize_receipt(updated, db)
    result.update(document_context(db, "GOODS_RECEIPT", updated.id, updated.status, user))
    result["allowed_actions"] = receipt_actions(updated, user, db)
    return result


@router.get("/{receipt_id}")
def get_receipt(receipt_id: int, db: Session = Depends(get_db), user=Depends(receiving_view_user)):
    receipt = _scoped_receipt(db, receipt_id, user)
    result = serialize_receipt(receipt, db)
    result.update(document_context(db, "GOODS_RECEIPT", receipt.id, receipt.status, user))
    result["allowed_actions"] = receipt_actions(receipt, user, db)
    return result


@router.post("/{receipt_id}/submit")
def submit_receipt(receipt_id: int, db: Session = Depends(get_db), user=Depends(receiving_submit_user)):
    receipt = _scoped_receipt_for_update(db, receipt_id, user)
    if receipt.status != "DRAFT":
        raise HTTPException(409, "Only draft receiving reports can be submitted")
    if receipt.source_type == "HISTORICAL_ENTRY":
        raise HTTPException(409, "Historical receiving uses Draft then Post")
    start_approval(
        db,
        entity_type="GOODS_RECEIPT",
        entity_id=receipt.id,
        workflow_code="RR_APPROVAL",
        user=user,
    )
    db.commit()
    db.refresh(receipt)
    return serialize_receipt(receipt, db)


@router.post("/{receipt_id}/approve")
def approve_receipt(receipt_id: int, data: ApprovalDecisionRequest | None = None, db: Session = Depends(get_db), user=Depends(receiving_approve_user)):
    receipt = _scoped_receipt_for_update(db, receipt_id, user)
    approval = get_request(db, "GOODS_RECEIPT", receipt.id)
    if not approval or approval.status != "PENDING":
        raise HTTPException(409, "Receiving report does not have pending approval")
    approve_current_step(db, request=approval, user=user, comment=data.comment if data else None)
    db.commit()
    db.refresh(receipt)
    return serialize_receipt(receipt, db)


@router.post("/{receipt_id}/reject")
def reject_receipt(receipt_id: int, data: ApprovalDecisionRequest, db: Session = Depends(get_db), user=Depends(receiving_approve_user)):
    receipt = _scoped_receipt_for_update(db, receipt_id, user)
    approval = get_request(db, "GOODS_RECEIPT", receipt.id)
    if not approval or approval.status != "PENDING":
        raise HTTPException(409, "Receiving report does not have pending approval")
    reject_current_step(db, request=approval, user=user, comment=data.comment)
    db.commit()
    db.refresh(receipt)
    return serialize_receipt(receipt, db)


@router.post("/{receipt_id}/post")
def post_receipt(receipt_id: int, db: Session = Depends(get_db), user=Depends(receiving_post_user)):
    receipt = _scoped_receipt_for_update(db, receipt_id, user)
    approval = get_request(db, "GOODS_RECEIPT", receipt.id)
    historical = receipt.source_type == "HISTORICAL_ENTRY" and approval is None
    if not historical and (not approval or approval.status != "APPROVED"):
        raise HTTPException(409, "Receiving report must complete approval before posting")
    return serialize_receipt(GoodsReceiptService.post(db=db, receipt_id=receipt_id, user=user), db)


@router.patch("/{receipt_id}/costs")
def correct_receipt_costs(receipt_id: int, data: GoodsReceiptCostCorrection, db: Session = Depends(get_db), user=Depends(receiving_manage_user)):
    _scoped_receipt(db, receipt_id, user)
    return serialize_receipt(GoodsReceiptService.correct_costs(db=db, receipt_id=receipt_id, data=data, user=user), db)


@router.post("/{receipt_id}/return")
def return_receipt(receipt_id: int, db: Session = Depends(get_db), user=Depends(receiving_return_user)):
    _scoped_receipt(db, receipt_id, user)
    return serialize_receipt(GoodsReceiptService.return_receipt(db=db, receipt_id=receipt_id, user=user), db)


@router.get("/{receipt_id}/allowed-actions")
def get_allowed_actions(receipt_id: int, db: Session = Depends(get_db), user=Depends(receiving_view_user)):
    receipt = _scoped_receipt(db, receipt_id, user)
    return receipt_actions(receipt, user, db)


@router.get("/{receipt_id}/print")
def print_receipt(receipt_id: int, db: Session = Depends(get_db), user=Depends(receiving_view_user)):
    receipt = _scoped_receipt(db, receipt_id, user)
    payload = get_receipt(receipt_id, db, user)
    remaining = remaining_items(receipt.purchase_order) if receipt.purchase_order else []
    payload["is_partial_receipt"] = bool(receipt.purchase_order and remaining)
    payload["remaining_items"] = remaining
    return {**payload, "document_type": "Receiving Report", **print_metadata(user)}

from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role
from app.models.approval_request import ApprovalRequest
from app.models.department import Department
from app.models.goods_receipt import GoodsReceipt
from app.models.location import Location
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.goods_receipt import GoodsReceiptCostCorrection, GoodsReceiptCreate
from app.services.approval import (
    approve_current_step,
    can_user_decide_step,
    current_steps,
    get_request,
    reject_current_step,
    start_approval,
)
from app.services.document_context import document_context, print_metadata
from app.services.goods_receipt_service import GoodsReceiptService

router = APIRouter(prefix="/goods-receipts", tags=["Goods Receipts"])


def receipt_actions(receipt: GoodsReceipt, user, db: Session):
    receiving_role = has_any_role(user, "WAREHOUSE", "PURCHASING")
    approval = get_request(db, "GOODS_RECEIPT", receipt.id)
    approval_status = approval.status if approval else None
    can_decide = bool(
        approval
        and approval.status == "PENDING"
        and any(can_user_decide_step(step, user) for step in current_steps(approval))
    )
    return {
        "can_edit": False,
        "can_submit": receipt.status == "DRAFT" and approval is None and receiving_role,
        "can_approve": can_decide,
        "can_reject": can_decide,
        "can_post": receipt.status == "DRAFT" and approval_status == "APPROVED" and receiving_role,
        "can_return": receipt.status == "POSTED" and receiving_role,
        "can_correct_cost": receipt.status in {"DRAFT", "POSTED"} and GoodsReceiptService.can_correct_cost(user),
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
        "location_name": receipt.location.name if receipt.location else None,
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
    requisitions = order.source_purchase_requisitions

    def inherited(field: str):
        current = getattr(order, field)
        if current is not None:
            return current
        values = {getattr(pr, field) for pr in requisitions if getattr(pr, field) is not None}
        if len(values) > 1:
            raise HTTPException(
                status_code=409,
                detail=f"Source purchase requisitions have different {field.replace('_id', '').replace('_', ' ')} values. Correct the PO before receiving.",
            )
        return next(iter(values), None)

    business_unit_id = inherited("business_unit_id")
    location_id = inherited("location_id")
    department_id = inherited("department_id")

    if order.business_unit_id is None and business_unit_id is not None:
        order.business_unit_id = business_unit_id
    if order.location_id is None and location_id is not None:
        order.location_id = location_id
    if order.department_id is None and department_id is not None:
        order.department_id = department_id

    data.business_unit_id = data.business_unit_id or business_unit_id
    data.location_id = data.location_id or location_id
    data.department_id = data.department_id or department_id
    db.flush()


@router.get("")
def list_receipts(
    purchase_order_id: int | None = None,
    destination_type: str | None = None,
    status: str | None = None,
    approval_status: str | None = None,
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(GoodsReceipt).options(
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
    waiting = db.query(GoodsReceipt).join(
        ApprovalRequest,
        (ApprovalRequest.entity_type == "GOODS_RECEIPT") & (ApprovalRequest.entity_id == GoodsReceipt.id),
    ).filter(ApprovalRequest.status == "PENDING").count()
    ready = db.query(GoodsReceipt).join(
        ApprovalRequest,
        (ApprovalRequest.entity_type == "GOODS_RECEIPT") & (ApprovalRequest.entity_id == GoodsReceipt.id),
    ).filter(GoodsReceipt.status == "DRAFT", ApprovalRequest.status == "APPROVED").count()
    posted = db.query(GoodsReceipt).filter(GoodsReceipt.status == "POSTED").count()
    return {
        "items": [serialize_receipt_summary(item, approval_map.get(item.id)) for item in rows],
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
        "summary": {"waiting_approval": waiting, "approved_to_post": ready, "posted": posted},
    }


@router.get("/receivable-purchase-orders")
def list_receivable_purchase_orders(db: Session = Depends(get_db), _=Depends(get_current_user)):
    orders = db.query(PurchaseOrder).filter(PurchaseOrder.status.in_({"APPROVED", "PARTIALLY_RECEIVED"})).order_by(PurchaseOrder.id.desc()).all()
    return [
        {
            "id": order.id,
            "po_number": order.po_number,
            "supplier_id": order.supplier_id,
            "supplier_name": order.supplier.name if order.supplier else None,
            "status": order.status,
            "business_unit_id": order.business_unit_id,
            "department_id": order.department_id,
            "location_id": order.location_id,
            "tax_amount": order.tax_amount,
            "total_amount": order.total_amount,
            "items": remaining_items(order),
        }
        for order in orders
        if remaining_items(order)
    ]


@router.get("/receivable-purchase-orders/{purchase_order_id}/items")
def get_remaining_purchase_order_items(purchase_order_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    order = db.get(PurchaseOrder, purchase_order_id)
    if not order:
        raise HTTPException(404, "Purchase order not found")
    if order.status not in {"APPROVED", "PARTIALLY_RECEIVED"}:
        raise HTTPException(409, "Purchase order is not receivable")
    return remaining_items(order)


@router.post("", status_code=201)
def create_receipt(data: GoodsReceiptCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if data.purchase_order_id:
        order = db.get(PurchaseOrder, data.purchase_order_id)
        if not order:
            raise HTTPException(404, "Purchase order not found")
        inherit_purchase_order_dimensions(order, data, db)
    return serialize_receipt(GoodsReceiptService.create(db=db, data=data, user=user), db)


@router.get("/{receipt_id}")
def get_receipt(receipt_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    receipt = db.get(GoodsReceipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "Goods receipt not found")
    result = serialize_receipt(receipt, db)
    result.update(document_context(db, "GOODS_RECEIPT", receipt.id, receipt.status, user))
    result["allowed_actions"] = receipt_actions(receipt, user, db)
    return result


@router.post("/{receipt_id}/submit")
def submit_receipt(receipt_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    receipt = db.get(GoodsReceipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "Goods receipt not found")
    if receipt.status != "DRAFT":
        raise HTTPException(409, "Only draft receiving reports can be submitted")
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
def approve_receipt(receipt_id: int, data: ApprovalDecisionRequest | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    receipt = db.get(GoodsReceipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "Goods receipt not found")
    approval = get_request(db, "GOODS_RECEIPT", receipt.id)
    if not approval or approval.status != "PENDING":
        raise HTTPException(409, "Receiving report does not have pending approval")
    approve_current_step(db, request=approval, user=user, comment=data.comment if data else None)
    db.commit()
    db.refresh(receipt)
    return serialize_receipt(receipt, db)


@router.post("/{receipt_id}/reject")
def reject_receipt(receipt_id: int, data: ApprovalDecisionRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    receipt = db.get(GoodsReceipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "Goods receipt not found")
    approval = get_request(db, "GOODS_RECEIPT", receipt.id)
    if not approval or approval.status != "PENDING":
        raise HTTPException(409, "Receiving report does not have pending approval")
    reject_current_step(db, request=approval, user=user, comment=data.comment)
    db.commit()
    db.refresh(receipt)
    return serialize_receipt(receipt, db)


@router.post("/{receipt_id}/post")
def post_receipt(receipt_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    receipt = db.get(GoodsReceipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "Goods receipt not found")
    approval = get_request(db, "GOODS_RECEIPT", receipt.id)
    if not approval or approval.status != "APPROVED":
        raise HTTPException(409, "Receiving report must complete approval before posting")
    return serialize_receipt(GoodsReceiptService.post(db=db, receipt_id=receipt_id, user=user), db)


@router.patch("/{receipt_id}/costs")
def correct_receipt_costs(receipt_id: int, data: GoodsReceiptCostCorrection, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return serialize_receipt(GoodsReceiptService.correct_costs(db=db, receipt_id=receipt_id, data=data, user=user), db)


@router.post("/{receipt_id}/return")
def return_receipt(receipt_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return serialize_receipt(GoodsReceiptService.return_receipt(db=db, receipt_id=receipt_id, user=user), db)


@router.get("/{receipt_id}/allowed-actions")
def get_allowed_actions(receipt_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    receipt = db.get(GoodsReceipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "Goods receipt not found")
    return receipt_actions(receipt, user, db)


@router.get("/{receipt_id}/print")
def print_receipt(receipt_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return {**get_receipt(receipt_id, db, user), "document_type": "Receiving Report", **print_metadata(user)}

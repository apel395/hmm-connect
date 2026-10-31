from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.approval_request import ApprovalRequest
from app.models.audit_log import AuditLog
from app.models.goods_receipt import GoodsReceipt
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_requisition import PurchaseRequisition
from app.models.stock_movement import StockMovement


router = APIRouter(tags=["Document Audit"])


def serialize_event(event: AuditLog):
    return {
        "id": event.id,
        "occurred_at": event.created_at,
        "actor_user_id": event.user_id,
        "actor_name": event.actor_name,
        "role_names": event.role_names or [],
        "department_name": event.department_name,
        "location_name": event.location_name,
        "action": event.action,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "summary": event.summary,
        "document_type": event.document_type,
        "document_number": event.document_number,
        "document_status": event.document_status,
        "reference_document": event.reference_document,
        "approval_level": event.approval_level,
        "approval_step": event.approval_step,
        "details": event.details,
        "before_data": event.before_data,
        "after_data": event.after_data,
        "source": event.source,
        "import_batch_id": event.import_batch_id,
    }


def serialize_approval(request: ApprovalRequest | None):
    if not request:
        return None
    current_step = next(
        (step for step in request.steps if step.step_order == request.current_step_order),
        None,
    )
    return {
        "id": request.id,
        "status": request.status,
        "workflow_code": request.workflow.code,
        "current_approver_role": (
            current_step.approver_role_name if current_step else None
        ),
        "steps": [
            {
                "step_order": step.step_order,
                "name": step.name,
                "required_role": step.approver_role_name,
                "status": step.status,
                "approved_by": step.approved_by.full_name if step.approved_by else None,
                "decided_by": step.approved_by.full_name if step.approved_by else None,
                "decided_by_roles": (
                    [role.name for role in step.approved_by.roles]
                    if step.approved_by else []
                ),
                "decided_as": (
                    "ADMIN"
                    if step.approved_by
                    and any(role.name == "ADMIN" for role in step.approved_by.roles)
                    else step.approver_role_name if step.approved_by else None
                ),
                "decided_at": step.decided_at,
                "comment": step.decision_comment,
            }
            for step in request.steps
        ],
    }


def document_events(db: Session, references: list[tuple[str, int]]):
    clauses = [
        (AuditLog.entity_type == entity_type) & (AuditLog.entity_id == entity_id)
        for entity_type, entity_id in references
    ]
    if not clauses:
        return []
    from sqlalchemy import or_
    return [
        serialize_event(event)
        for event in (
            db.query(AuditLog)
            .filter(or_(*clauses))
            .order_by(AuditLog.created_at, AuditLog.id)
            .all()
        )
    ]


@router.get("/audit/events")
def list_document_events(
    document_type: str | None = None,
    document_number: str | None = None,
    action: str | None = None,
    actor: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(AuditLog)
    if document_type:
        query = query.filter(AuditLog.document_type == document_type.upper())
    if document_number:
        query = query.filter(AuditLog.document_number.ilike(f"%{document_number}%"))
    if action:
        query = query.filter(AuditLog.action == action.upper())
    if actor:
        query = query.filter(AuditLog.actor_name.ilike(f"%{actor}%"))
    if date_from:
        query = query.filter(
            AuditLog.created_at >= datetime.combine(date_from, time.min, timezone.utc)
        )
    if date_to:
        query = query.filter(
            AuditLog.created_at <= datetime.combine(date_to, time.max, timezone.utc)
        )

    total_items = query.count()
    offset = (page - 1) * page_size
    items = [
        serialize_event(event)
        for event in query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    ]
    total_pages = (total_items + page_size - 1) // page_size

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


@router.get("/traceability/purchase-requisitions/{requisition_id}")
def trace_purchase_requisition(
    requisition_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    requisition = db.get(PurchaseRequisition, requisition_id)
    if not requisition:
        raise HTTPException(status_code=404, detail="Purchase requisition not found")
    orders = list(requisition.purchase_orders)
    if requisition.legacy_purchase_orders:
        orders.extend(
            order for order in requisition.legacy_purchase_orders if order not in orders
        )
    order_ids = [order.id for order in orders]
    receipts = (
        db.query(GoodsReceipt)
        .filter(GoodsReceipt.purchase_order_id.in_(order_ids))
        .all()
        if order_ids
        else []
    )
    receipt_ids = [receipt.id for receipt in receipts]
    movements = (
        db.query(StockMovement)
        .filter(StockMovement.goods_receipt_id.in_(receipt_ids))
        .all()
        if receipt_ids
        else []
    )
    references = [("PURCHASE_REQUISITION", requisition.id)]
    references += [("PURCHASE_ORDER", order.id) for order in orders]
    references += [("GOODS_RECEIPT", receipt.id) for receipt in receipts]
    approval = (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.entity_type == "PURCHASE_REQUISITION",
            ApprovalRequest.entity_id == requisition.id,
        )
        .first()
    )
    return {
        "document": {
            "type": "PR",
            "id": requisition.id,
            "number": requisition.pr_number,
            "status": requisition.status,
            "date": requisition.request_date,
            "total_amount": requisition.total_amount,
        },
        "approval": serialize_approval(approval),
        "purchase_orders": [
            {
                "id": order.id,
                "number": order.po_number,
                "status": order.status,
                "supplier": order.supplier.name,
                "total_amount": order.total_amount,
                "approval": serialize_approval(
                    db.query(ApprovalRequest)
                    .filter(
                        ApprovalRequest.entity_type == "PURCHASE_ORDER",
                        ApprovalRequest.entity_id == order.id,
                    )
                    .first()
                ),
            }
            for order in orders
        ],
        "goods_receipts": [
            {
                "id": receipt.id,
                "number": receipt.receipt_number,
                "purchase_order_id": receipt.purchase_order_id,
                "received_at": receipt.received_at,
                "warehouse": receipt.warehouse.name if receipt.warehouse else None,
                "destination_type": receipt.destination_type,
            }
            for receipt in receipts
        ],
        "stock_movements": [
            {
                "id": movement.id,
                "goods_receipt_id": movement.goods_receipt_id,
                "product_id": movement.product_id,
                "warehouse_id": movement.warehouse_id,
                "movement_type": movement.movement_type,
                "quantity": movement.quantity,
                "unit_cost": movement.unit_cost,
                "created_at": movement.created_at,
            }
            for movement in movements
        ],
        "events": document_events(db, references),
    }


@router.get("/traceability/purchase-orders/{purchase_order_id}")
def trace_purchase_order(
    purchase_order_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    order = db.get(PurchaseOrder, purchase_order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    requisition_ids = order.purchase_requisition_ids
    if order.purchase_requisition_id:
        requisition_ids.append(order.purchase_requisition_id)
    if requisition_ids:
        return trace_purchase_requisition(requisition_ids[0], db, user)
    receipts = list(order.goods_receipts)
    references = [("PURCHASE_ORDER", order.id)] + [
        ("GOODS_RECEIPT", receipt.id) for receipt in receipts
    ]
    return {
        "document": {
            "type": "PO",
            "id": order.id,
            "number": order.po_number,
            "status": order.status,
            "date": order.order_date,
            "total_amount": order.total_amount,
        },
        "approval": serialize_approval(
            db.query(ApprovalRequest)
            .filter(
                ApprovalRequest.entity_type == "PURCHASE_ORDER",
                ApprovalRequest.entity_id == order.id,
            )
            .first()
        ),
        "purchase_orders": [],
        "goods_receipts": [
            {
                "id": receipt.id,
                "number": receipt.receipt_number,
                "received_at": receipt.received_at,
            }
            for receipt in receipts
        ],
        "stock_movements": [],
        "events": document_events(db, references),
    }

from pydantic import BaseModel, Field
from typing import Literal
from uuid import UUID
from app.services.document_print_tracking import record_print, print_history

class PrintRequest(BaseModel):
    request_id: UUID
    action: Literal['PRINT_DIALOG', 'PDF_DOWNLOAD'] = 'PRINT_DIALOG'
    expected_revision: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    snapshot_hash: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')

@router.post('/document-events/{kind}/{document_id}/print')
def issue_print(kind:str,document_id:int,data:PrintRequest,db:Session=Depends(get_db),user=Depends(get_current_user)):
    return record_print(db,user,kind,document_id,str(data.request_id),action=data.action,expected_revision=data.expected_revision,snapshot_hash=data.snapshot_hash)


@router.get('/document-events/{kind}/{document_id}/print-history')
def document_print_history(kind: str, document_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return print_history(db, user, kind, document_id)

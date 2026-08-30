from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.approval_request import ApprovalRequest
from app.models.document_attachment import DocumentAttachment
from app.models.audit_log import AuditLog
from app.dependencies.authorization import has_permission, is_superuser, role_names
from app.services.approval import can_user_decide_step
from app.services.print_signatures import add_private_print_signatures


REOPENABLE_WORKFLOW_DOCUMENTS = {"PURCHASE_REQUISITION", "MARKET_LIST", "PURCHASE_ORDER"}

ACTION_PERMISSIONS = {
    "PURCHASE_REQUISITION": {
        "view": "pr.view", "edit": "pr.edit", "submit": "pr.submit", "approve": "pr.approve", "manage": "pr.manage",
    },
    "MARKET_LIST": {
        "view": "market_list.view", "edit": "market_list.edit", "submit": "market_list.submit",
        "approve": "market_list.approve", "manage": "market_list.manage",
    },
    "PURCHASE_ORDER": {
        "view": "po.view", "edit": "po.edit", "submit": "po.submit", "approve": "po.approve", "manage": "po.manage",
    },
    "GOODS_RECEIPT": {
        "view": "receiving.view", "edit": "receiving.edit", "submit": "receiving.submit",
        "approve": "receiving.approve", "manage": "receiving.manage",
    },
    "STORE_REQUEST": {
        "view": "store_request.view", "edit": "store_request.manage", "submit": "store_request.manage",
        "approve": "store_request.manage", "manage": "store_request.manage",
    },
    "STOCK_OPNAME": {
        "view": "stock_opname.view", "edit": "stock_opname.manage", "submit": "stock_opname.manage",
        "approve": "stock_opname.manage", "manage": "stock_opname.manage",
    },
}


def _can(user, entity_type: str, action: str) -> bool:
    code = ACTION_PERMISSIONS.get(entity_type, {}).get(action)
    return bool(code and has_permission(user, code))


def _entity_location_name(db: Session, entity_type: str, entity_id: int) -> str | None:
    if entity_type == "PURCHASE_REQUISITION":
        from app.models.purchase_requisition import PurchaseRequisition
        entity = db.get(PurchaseRequisition, entity_id)
    elif entity_type == "MARKET_LIST":
        from app.models.market_list import MarketList
        entity = db.get(MarketList, entity_id)
    elif entity_type == "PURCHASE_ORDER":
        from app.models.purchase_order import PurchaseOrder
        entity = db.get(PurchaseOrder, entity_id)
    elif entity_type == "GOODS_RECEIPT":
        from app.models.goods_receipt import GoodsReceipt
        entity = db.get(GoodsReceipt, entity_id)
    elif entity_type == "STORE_REQUEST":
        from app.models.store_request import StoreRequest
        entity = db.get(StoreRequest, entity_id)
    elif entity_type == "STOCK_OPNAME":
        from app.models.stock_opname import StockOpname
        entity = db.get(StockOpname, entity_id)
    else:
        entity = None
    location = getattr(entity, "location", None) if entity else None
    return location.name if location else None



def _entity_has_items(db: Session, entity_type: str, entity_id: int) -> bool:
    if entity_type == "STORE_REQUEST":
        from app.models.store_request import StoreRequest
        entity = db.get(StoreRequest, entity_id)
        return bool(entity and entity.items)
    if entity_type == "STOCK_OPNAME":
        from app.models.stock_opname import StockOpname
        entity = db.get(StockOpname, entity_id)
        return bool(entity and entity.items)
    return True


def document_context(db: Session, entity_type: str, entity_id: int, status: str, user) -> dict:
    request = db.query(ApprovalRequest).filter(
        ApprovalRequest.entity_type == entity_type,
        ApprovalRequest.entity_id == entity_id,
    ).order_by(ApprovalRequest.id.desc()).first()
    current = next((step for step in request.steps if step.step_order == request.current_step_order), None) if request else None
    admin = is_superuser(user)
    can_decide = bool(current and can_user_decide_step(current, user))
    pending = status == "PENDING_APPROVAL"
    editable_approval_steps = (
        [
            step
            for step in request.steps
            if request.current_step_order is not None
            and step.step_order >= request.current_step_order
            and step.status in {"PENDING", "WAITING"}
            and can_user_decide_step(step, user)
        ]
        if request and pending
        else []
    )
    can_edit_approval = bool(editable_approval_steps)
    actor_approval_level = (
        min(step.step_order for step in editable_approval_steps)
        if editable_approval_steps
        else None
    )
    can_receive = (
        entity_type == "PURCHASE_ORDER"
        and status in {"APPROVED", "PARTIALLY_RECEIVED"}
        and has_permission(user, "receiving.manage")
    )
    has_items = _entity_has_items(db, entity_type, entity_id)
    can_issue = (
        entity_type == "STORE_REQUEST"
        and has_items
        and status in {"APPROVED", "PARTIALLY_ISSUED"}
        and has_permission(user, "store_request.manage")
    )
    can_post = (
        entity_type == "STOCK_OPNAME"
        and has_items
        and status == "APPROVED"
        and has_permission(user, "stock_opname.manage")
    )
    can_reopen = admin and entity_type in REOPENABLE_WORKFLOW_DOCUMENTS and status != "DRAFT"
    events = db.query(AuditLog).filter(
        AuditLog.entity_type == entity_type,
        AuditLog.entity_id == entity_id,
    ).order_by(AuditLog.created_at.desc()).all()
    result = {
        "is_admin": admin,
        "location_name": _entity_location_name(db, entity_type, entity_id),
        "allowed_actions": {
            "can_edit": (status == "DRAFT" or (pending and can_edit_approval)) and _can(user, entity_type, "edit"),
            "can_submit": status == "DRAFT" and has_items and _can(user, entity_type, "submit"),
            "can_approve": pending and has_items and can_decide and _can(user, entity_type, "approve"),
            "can_reject": pending and can_decide and _can(user, entity_type, "approve"),
            "can_reopen": can_reopen and _can(user, entity_type, "manage"),
            "can_print": _can(user, entity_type, "view"),
            "can_view_history": _can(user, entity_type, "view"),
            "can_manage_attachments": _can(user, entity_type, "edit") or _can(user, entity_type, "manage"),
            "can_receive": can_receive,
            "can_issue": can_issue,
            "can_post": can_post,
        },
        "approval_history": [{
            "level": step.step_order,
            "name": step.name,
            "approver_role": step.approver_role_name,
            "location_name": step.location_name,
            "status": step.status,
            "approver_name": step.approved_by.full_name if step.approved_by else None,
            "decided_at": step.decided_at,
            "comment": step.decision_comment,
        } for step in request.steps] if request else [],
        "current_approval_level": request.current_step_order if request else None,
        "actor_approval_level": actor_approval_level,
        "attachment_count": db.query(DocumentAttachment).filter(
            DocumentAttachment.entity_type == entity_type,
            DocumentAttachment.entity_id == entity_id,
            DocumentAttachment.is_active.is_(True),
        ).count(),
        "activity_history": [{
            "id": event.id, "action": event.action, "summary": event.summary,
            "actor_name": event.actor_name or (event.user.full_name if event.user else None),
            "occurred_at": event.created_at,
        } for event in events],
    }
    return add_private_print_signatures(result)


def print_metadata(user) -> dict:
    return {
        "brand_name": "HMM-Connect",
        "hotel_name": "Hotel Mutiara Merdeka",
        "printed_by": user.full_name,
        "generated_at": datetime.now(timezone.utc),
    }

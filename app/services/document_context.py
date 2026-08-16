from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.approval_request import ApprovalRequest
from app.models.document_attachment import DocumentAttachment
from app.models.audit_log import AuditLog
from app.dependencies.authorization import has_any_role, is_superuser, role_names
from app.services.print_signatures import add_private_print_signatures


REOPENABLE_WORKFLOW_DOCUMENTS = {"PURCHASE_REQUISITION", "MARKET_LIST", "PURCHASE_ORDER"}


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
    else:
        entity = None
    location = getattr(entity, "location", None) if entity else None
    return location.name if location else None


def document_context(db: Session, entity_type: str, entity_id: int, status: str, user) -> dict:
    request = db.query(ApprovalRequest).filter(
        ApprovalRequest.entity_type == entity_type,
        ApprovalRequest.entity_id == entity_id,
    ).order_by(ApprovalRequest.id.desc()).first()
    current = next((step for step in request.steps if step.step_order == request.current_step_order), None) if request else None
    admin = is_superuser(user)
    roles = role_names(user)
    can_decide = bool(current and (
        admin or (
            current.approver_role_name.strip().upper() in roles
            and (not current.department_name or (user.department and user.department.name == current.department_name))
            and (not current.location_name or (user.location and user.location.name == current.location_name))
        )
    ))
    pending = status == "PENDING_APPROVAL"
    can_receive = entity_type == "PURCHASE_ORDER" and status in {"APPROVED", "PARTIALLY_RECEIVED"} and (
        admin or has_any_role(user, "WAREHOUSE")
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
            "can_edit": status == "DRAFT" or (pending and can_decide),
            "can_submit": status == "DRAFT",
            "can_approve": pending and can_decide,
            "can_reject": pending and can_decide,
            "can_reopen": can_reopen,
            "can_print": True,
            "can_view_history": True,
            "can_manage_attachments": True,
            "can_receive": can_receive,
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

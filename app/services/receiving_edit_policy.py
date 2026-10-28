"""Edit unposted receiving; archive decisions before reopening approved documents."""
from fastapi import HTTPException
from app.dependencies.authorization import has_permission
from app.services.approval import can_user_edit_pending_approval, get_request
from app.services.activity_service import ActivityService


def can_edit_receiving(receipt, approval, user):
    if receipt.status != "DRAFT" or not has_permission(user, "receiving.edit"):
        return False
    if approval is None:
        return True
    if approval.status == "APPROVED":
        return has_permission(user, "receiving.manage")
    return approval.status == "PENDING" and (has_permission(user, "receiving.manage") or can_user_edit_pending_approval(approval, user))


def reopen_approved_receiving(db, receipt, user):
    approval = get_request(db, "GOODS_RECEIPT", receipt.id, for_update=True)
    if not approval or approval.status != "APPROVED":
        return False
    if not can_edit_receiving(receipt, approval, user):
        raise HTTPException(403, "Receiving Manage and Edit permissions are required to edit an approved draft")
    if not approval.steps:
        raise HTTPException(409, "Approved receiving has no approval stages; review workflow setup")
    before = {"status": approval.status, "completed_at": approval.completed_at.isoformat() if approval.completed_at else None,
        "steps": [{"id": s.id, "step_order": s.step_order, "name": s.name, "status": s.status,
            "approved_by_id": s.approved_by_id, "decided_at": s.decided_at.isoformat() if s.decided_at else None,
            "decision_comment": s.decision_comment} for s in approval.steps]}
    first = min(s.step_order for s in approval.steps)
    approval.status = "PENDING"
    approval.current_step_order = first
    approval.completed_at = None
    for step in approval.steps:
        step.status = "PENDING" if step.step_order == first else "WAITING"
        step.approved_by_id = None
        step.decided_at = None
        step.decision_comment = None
    ActivityService.log(db=db, user=user, action="RECEIVING_APPROVAL_REOPENED", entity_type="GOODS_RECEIPT",
        entity_id=receipt.id, summary=f"Reopened approval after editing {receipt.receipt_number}",
        document_number=receipt.receipt_number, document_status=receipt.status, before_data=before,
        after_data={"status": "PENDING", "current_step_order": first})
    return True


def edit_block_reason(receipt, approval, user):
    if can_edit_receiving(receipt, approval, user):
        return None
    if receipt.status == "POSTED":
        return "This receiving is posted. An authorized receiving/Finance manager can use Depost for Edit when its accounting period and dependencies allow it. Use Correct Cost for price-only changes."
    if receipt.status == "RETURNED":
        return "This receiving was returned. Create a corrected receiving; the returned report remains in history."
    if not has_permission(user, "receiving.edit"):
        return "Receiving Edit permission is required."
    return "Editing is restricted at the current approval stage. An authorized receiving manager must review it."

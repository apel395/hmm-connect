from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.approval_request import ApprovalRequest, ApprovalRequestStep
from app.models.approval_workflow import ApprovalWorkflow


def get_request(db: Session, entity_type: str, entity_id: int):
    return (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.entity_type == entity_type,
            ApprovalRequest.entity_id == entity_id,
        )
        .first()
    )


def start_approval(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    workflow_code: str,
    user,
) -> ApprovalRequest:
    if get_request(db, entity_type, entity_id):
        raise HTTPException(status_code=409, detail="Approval already started")

    workflow = (
        db.query(ApprovalWorkflow)
        .filter(
            ApprovalWorkflow.code == workflow_code,
            ApprovalWorkflow.is_active.is_(True),
        )
        .first()
    )
    if not workflow or not workflow.steps:
        raise HTTPException(
            status_code=400,
            detail=f"Active approval workflow {workflow_code!r} is not configured",
        )

    request = ApprovalRequest(
        workflow_id=workflow.id,
        entity_type=entity_type,
        entity_id=entity_id,
        status="PENDING",
        current_step_order=workflow.steps[0].step_order,
        created_by_id=user.id,
    )
    for index, step in enumerate(workflow.steps):
        request.steps.append(
            ApprovalRequestStep(
                step_order=step.step_order,
                name=step.name,
                approver_role_name=step.approver_role.name,
                department_name=step.department.name if step.department else None,
                location_name=step.location.name if step.location else None,
                status="PENDING" if index == 0 else "WAITING",
            )
        )
    db.add(request)
    db.flush()
    return request


def _current_step(request: ApprovalRequest) -> ApprovalRequestStep:
    step = next(
        (
            item
            for item in request.steps
            if item.step_order == request.current_step_order
        ),
        None,
    )
    if not step:
        raise HTTPException(status_code=409, detail="No pending approval step")
    return step


def _authorize_step(step: ApprovalRequestStep, user) -> None:
    role_names = {role.name for role in user.roles}
    if "ADMIN" in role_names:
        return
    if step.approver_role_name not in role_names:
        raise HTTPException(status_code=403, detail="User cannot approve this step")
    if step.department_name and (
        not user.department or user.department.name != step.department_name
    ):
        raise HTTPException(status_code=403, detail="Department does not match")
    if step.location_name and (
        not user.location or user.location.name != step.location_name
    ):
        raise HTTPException(status_code=403, detail="Location does not match")


def approve_current_step(db: Session, *, request, user, comment=None) -> None:
    step = _current_step(request)
    _authorize_step(step, user)
    step.status = "APPROVED"
    step.approved_by_id = user.id
    step.decided_at = datetime.now(timezone.utc)
    step.decision_comment = comment

    remaining = [item for item in request.steps if item.status == "WAITING"]
    if not remaining:
        request.status = "APPROVED"
        request.current_step_order = None
        request.completed_at = datetime.now(timezone.utc)
        return

    next_step = min(remaining, key=lambda item: item.step_order)
    next_step.status = "PENDING"
    request.current_step_order = next_step.step_order
    db.flush()


def reject_current_step(db: Session, *, request, user, comment=None) -> None:
    step = _current_step(request)
    _authorize_step(step, user)
    step.status = "REJECTED"
    step.approved_by_id = user.id
    step.decided_at = datetime.now(timezone.utc)
    step.decision_comment = comment
    request.status = "REJECTED"
    request.current_step_order = None
    request.completed_at = datetime.now(timezone.utc)
    db.flush()

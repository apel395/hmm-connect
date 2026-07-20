from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.approval_request import ApprovalRequest, ApprovalRequestStep
from app.models.approval_workflow import ApprovalWorkflow
from app.models.user import User


WORKFLOW_STATUS_PENDING = "PENDING"
WORKFLOW_STATUS_APPROVED = "APPROVED"
WORKFLOW_STATUS_REJECTED = "REJECTED"


def get_workflow(db: Session, code: str) -> ApprovalWorkflow:
    workflow = (
        db.query(ApprovalWorkflow)
        .options(joinedload(ApprovalWorkflow.steps))
        .filter(
            ApprovalWorkflow.code == code,
            ApprovalWorkflow.is_active.is_(True),
        )
        .first()
    )
    if not workflow or not workflow.steps:
        raise HTTPException(
            status_code=500,
            detail=f"Approval workflow {code} is not configured",
        )
    return workflow


def get_request(db: Session, entity_type: str, entity_id: int) -> ApprovalRequest | None:
    return (
        db.query(ApprovalRequest)
        .options(joinedload(ApprovalRequest.steps))
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
    user: User,
) -> ApprovalRequest:
    existing = get_request(db, entity_type, entity_id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Approval workflow already started for this document",
        )

    workflow = get_workflow(db, workflow_code)
    ordered_steps = sorted(workflow.steps, key=lambda step: step.step_order)

    request = ApprovalRequest(
        workflow_id=workflow.id,
        entity_type=entity_type,
        entity_id=entity_id,
        status=WORKFLOW_STATUS_PENDING,
        current_step_order=ordered_steps[0].step_order,
        created_by_id=user.id,
    )

    for index, workflow_step in enumerate(ordered_steps):
        request.steps.append(
            ApprovalRequestStep(
                step_order=workflow_step.step_order,
                name=workflow_step.name,
                approver_role_name=workflow_step.approver_role.name,
                department_name=(
                    workflow_step.department.name
                    if workflow_step.department
                    else None
                ),
                location_name=(
                    workflow_step.location.name
                    if workflow_step.location
                    else None
                ),
                status="PENDING" if index == 0 else "WAITING",
            )
        )

    db.add(request)
    db.flush()
    return request


def current_step(request: ApprovalRequest) -> ApprovalRequestStep | None:
    if request.status != WORKFLOW_STATUS_PENDING:
        return None
    return next(
        (
            step
            for step in request.steps
            if step.step_order == request.current_step_order
            and step.status == "PENDING"
        ),
        None,
    )


def user_can_approve(user: User, step: ApprovalRequestStep) -> bool:
    role_names = {role.name for role in user.roles}
    if step.approver_role_name not in role_names:
        return False

    if step.department_name and (
        not user.department or user.department.name != step.department_name
    ):
        return False

    if step.location_name and (
        not user.location or user.location.name != step.location_name
    ):
        return False

    return True


def approve_current_step(
    db: Session,
    *,
    request: ApprovalRequest,
    user: User,
    comment: str | None = None,
) -> ApprovalRequest:
    step = current_step(request)
    if not step:
        raise HTTPException(status_code=400, detail="No pending approval step")

    if not user_can_approve(user, step):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Approval requires role {step.approver_role_name}"
                + (
                    f" in {step.department_name}"
                    if step.department_name
                    else ""
                )
            ),
        )

    step.status = "APPROVED"
    step.approved_by_id = user.id
    step.decided_at = datetime.now(timezone.utc)
    step.decision_comment = comment

    next_step = next(
        (
            candidate
            for candidate in request.steps
            if candidate.step_order > step.step_order
            and candidate.status == "WAITING"
        ),
        None,
    )

    if next_step:
        next_step.status = "PENDING"
        request.current_step_order = next_step.step_order
    else:
        request.status = WORKFLOW_STATUS_APPROVED
        request.current_step_order = None
        request.completed_at = datetime.now(timezone.utc)

    db.flush()
    return request


def reject_current_step(
    db: Session,
    *,
    request: ApprovalRequest,
    user: User,
    comment: str | None = None,
) -> ApprovalRequest:
    step = current_step(request)
    if not step:
        raise HTTPException(status_code=400, detail="No pending approval step")

    if not user_can_approve(user, step):
        raise HTTPException(
            status_code=403,
            detail=f"Approval requires role {step.approver_role_name}",
        )

    step.status = "REJECTED"
    step.approved_by_id = user.id
    step.decided_at = datetime.now(timezone.utc)
    step.decision_comment = comment
    request.status = WORKFLOW_STATUS_REJECTED
    request.current_step_order = None
    request.completed_at = datetime.now(timezone.utc)

    db.flush()
    return request

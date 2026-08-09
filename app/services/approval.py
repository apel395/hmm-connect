from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.approval_request import ApprovalRequest, ApprovalRequestStep
from app.models.approval_workflow import ApprovalWorkflow, ApprovalWorkflowStep
from app.models.role import Role
from app.dependencies.authorization import is_superuser, role_names


def get_request(db: Session, entity_type: str, entity_id: int):
    return (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.entity_type == entity_type,
            ApprovalRequest.entity_id == entity_id,
        )
        .first()
    )


def _normalized_role_name(value: str) -> str:
    return "_".join(
        part
        for part in "".join(
            character if character.isalnum() else " " for character in value.upper()
        ).split()
        if part
    )


def _administrator_role(db: Session) -> Role | None:
    roles = db.query(Role).order_by(Role.id).all()
    preferred = {
        "SYSTEM_ADMINISTRATOR", "ERP_ADMINISTRATOR", "SUPER_ADMIN",
        "ADMINISTRATOR", "SYSTEM_ADMIN", "ERP_ADMIN", "ADMIN",
    }
    for role in roles:
        if _normalized_role_name(role.name) in preferred:
            return role
    for role in roles:
        normalized = _normalized_role_name(role.name)
        if "ADMIN" in normalized or "ADMINISTRATOR" in normalized:
            return role
    return None


def _is_generated_default(workflow: ApprovalWorkflow) -> bool:
    expected_names = {"PURCHASE REQUISITION APPROVAL", "PURCHASE ORDER APPROVAL"}
    if workflow.name.strip().upper() not in expected_names:
        return False
    return all(
        "ADMIN" in _normalized_role_name(step.approver_role.name)
        or "ADMINISTRATOR" in _normalized_role_name(step.approver_role.name)
        for step in workflow.steps
    )


def _ensure_default_workflow(db: Session, *, workflow_code: str) -> ApprovalWorkflow | None:
    entity_by_code = {
        "PR_APPROVAL": "PURCHASE_REQUISITION",
        "PO_APPROVAL": "PURCHASE_ORDER",
    }
    entity_type = entity_by_code.get(workflow_code)
    if not entity_type:
        return None

    workflow = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.code == workflow_code).first()
    if workflow and workflow.is_active and workflow.steps:
        return workflow
    if workflow and not workflow.is_active:
        return None

    administrator_role = _administrator_role(db)
    if not administrator_role:
        return None

    if not workflow:
        workflow = ApprovalWorkflow(
            code=workflow_code,
            name=("Purchase Requisition Approval" if workflow_code == "PR_APPROVAL" else "Purchase Order Approval"),
            entity_type=entity_type,
            is_active=True,
        )
        db.add(workflow)
        db.flush()

    if not workflow.steps or _is_generated_default(workflow):
        workflow.steps.clear()
        workflow.steps.extend([
            ApprovalWorkflowStep(step_order=1, name="Approval Level 1", approver_role_id=administrator_role.id),
            ApprovalWorkflowStep(step_order=2, name="Approval Level 2", approver_role_id=administrator_role.id),
        ])
        db.flush()
    return workflow


def start_approval(db: Session, *, entity_type: str, entity_id: int, workflow_code: str, user) -> ApprovalRequest:
    if get_request(db, entity_type, entity_id):
        raise HTTPException(status_code=409, detail="Approval already started")

    workflow = _ensure_default_workflow(db, workflow_code=workflow_code)
    if not workflow or not workflow.steps:
        raise HTTPException(status_code=400, detail=f"Active approval workflow {workflow_code!r} is not configured")

    first_order = min(step.step_order for step in workflow.steps)
    request = ApprovalRequest(
        workflow_id=workflow.id,
        entity_type=entity_type,
        entity_id=entity_id,
        status="PENDING",
        current_step_order=first_order,
        created_by_id=user.id,
    )
    for step in workflow.steps:
        request.steps.append(ApprovalRequestStep(
            step_order=step.step_order,
            name=step.name,
            approver_role_name=step.approver_role.name,
            department_name=step.department.name if step.department else None,
            location_name=step.location.name if step.location else None,
            status="PENDING" if step.step_order == first_order else "WAITING",
        ))
    db.add(request)
    db.flush()
    return request


def current_steps(request: ApprovalRequest) -> list[ApprovalRequestStep]:
    if request.current_step_order is None:
        return []
    return [
        step for step in request.steps
        if step.step_order == request.current_step_order and step.status == "PENDING"
    ]


def can_user_decide_step(step: ApprovalRequestStep, user) -> bool:
    if is_superuser(user):
        return True
    if step.approver_role_name.strip().upper() not in role_names(user):
        return False
    if step.department_name and (not user.department or user.department.name != step.department_name):
        return False
    if step.location_name and (not user.location or user.location.name != step.location_name):
        return False
    return True


def _select_current_step(request: ApprovalRequest, user) -> ApprovalRequestStep:
    pending = current_steps(request)
    if not pending:
        raise HTTPException(status_code=409, detail="No pending approval step")
    for step in pending:
        if can_user_decide_step(step, user):
            return step
    raise HTTPException(status_code=403, detail="User cannot approve the current stage")


def _advance_stage(db: Session, request: ApprovalRequest) -> None:
    if current_steps(request):
        db.flush()
        return
    waiting = [step for step in request.steps if step.status == "WAITING"]
    if not waiting:
        request.status = "APPROVED"
        request.current_step_order = None
        request.completed_at = datetime.now(timezone.utc)
        db.flush()
        return
    next_order = min(step.step_order for step in waiting)
    for step in waiting:
        if step.step_order == next_order:
            step.status = "PENDING"
    request.current_step_order = next_order
    db.flush()


def approve_current_step(db: Session, *, request, user, comment=None) -> None:
    step = _select_current_step(request, user)
    step.status = "APPROVED"
    step.approved_by_id = user.id
    step.decided_at = datetime.now(timezone.utc)
    step.decision_comment = comment
    _advance_stage(db, request)


def reject_current_step(db: Session, *, request, user, comment=None) -> None:
    if not comment or not str(comment).strip():
        raise HTTPException(status_code=400, detail="Rejection reason is required")
    step = _select_current_step(request, user)
    step.status = "REJECTED"
    step.approved_by_id = user.id
    step.decided_at = datetime.now(timezone.utc)
    step.decision_comment = str(comment).strip()
    request.status = "REJECTED"
    request.current_step_order = None
    request.completed_at = datetime.now(timezone.utc)
    db.flush()

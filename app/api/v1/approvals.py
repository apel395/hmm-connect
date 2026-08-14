from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import is_superuser
from app.models.approval_request import ApprovalRequest
from app.models.approval_workflow import ApprovalWorkflow, ApprovalWorkflowStep
from app.models.department import Department
from app.models.location import Location
from app.models.role import Role
from app.services.approval import can_user_decide_step, current_steps


router = APIRouter(prefix="/approvals", tags=["Approvals"])


class WorkflowStepInput(BaseModel):
    step_order: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=150)
    approver_role_id: int
    department_id: int | None = None
    location_id: int | None = None


class WorkflowInput(BaseModel):
    code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=150)
    entity_type: str = Field(min_length=2, max_length=80)
    is_active: bool = True
    steps: list[WorkflowStepInput]


def _require_admin(user) -> None:
    if not is_superuser(user):
        raise HTTPException(status_code=403, detail="Only system administrators can configure approval workflows")


def _serialize_workflow(workflow: ApprovalWorkflow) -> dict:
    return {
        "id": workflow.id,
        "code": workflow.code,
        "name": workflow.name,
        "entity_type": workflow.entity_type,
        "is_active": workflow.is_active,
        "steps": [
            {
                "id": step.id,
                "step_order": step.step_order,
                "name": step.name,
                "approver_role_id": step.approver_role_id,
                "approver_role_name": step.approver_role.name,
                "department_id": step.department_id,
                "department_name": step.department.name if step.department else None,
                "location_id": step.location_id,
                "location_name": step.location.name if step.location else None,
                "mode": "PARALLEL" if sum(1 for item in workflow.steps if item.step_order == step.step_order) > 1 else "SEQUENTIAL",
            }
            for step in workflow.steps
        ],
    }


def _serialize_request(request: ApprovalRequest, user=None) -> dict:
    pending = current_steps(request)
    return {
        "id": request.id,
        "entity_type": request.entity_type,
        "entity_id": request.entity_id,
        "workflow_code": request.workflow.code,
        "workflow_name": request.workflow.name,
        "status": request.status,
        "current_step_order": request.current_step_order,
        "current_stage": [step.name for step in pending],
        "created_by_id": request.created_by_id,
        "created_by_name": request.created_by.full_name if request.created_by else None,
        "created_at": request.created_at,
        "completed_at": request.completed_at,
        "can_decide": bool(user and any(can_user_decide_step(step, user) for step in pending)),
        "steps": [
            {
                "id": step.id,
                "step_order": step.step_order,
                "name": step.name,
                "approver_role_name": step.approver_role_name,
                "department_name": step.department_name,
                "location_name": step.location_name,
                "status": step.status,
                "approved_by_name": step.approved_by.full_name if step.approved_by else None,
                "decided_at": step.decided_at,
                "decision_comment": step.decision_comment,
            }
            for step in request.steps
        ],
    }


def _validate_steps(db: Session, steps: list[WorkflowStepInput]) -> None:
    if not steps:
        raise HTTPException(status_code=400, detail="Approval workflow must contain at least one step")
    for step in steps:
        if not db.get(Role, step.approver_role_id):
            raise HTTPException(status_code=400, detail=f"Approver role {step.approver_role_id} does not exist")
        if step.department_id and not db.get(Department, step.department_id):
            raise HTTPException(status_code=400, detail=f"Department {step.department_id} does not exist")
        if step.location_id and not db.get(Location, step.location_id):
            raise HTTPException(status_code=400, detail=f"Location {step.location_id} does not exist")


@router.get("/inbox")
def approval_inbox(
    view: str = Query(default="pending", pattern="^(pending|submitted|completed|rejected|all)$"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = db.query(ApprovalRequest).order_by(ApprovalRequest.id.desc())
    requests = query.all()
    if view == "pending":
        requests = [request for request in requests if request.status == "PENDING" and any(can_user_decide_step(step, user) for step in current_steps(request))]
    elif view == "submitted":
        requests = [request for request in requests if request.created_by_id == user.id and request.status == "PENDING"]
    elif view == "completed":
        requests = [request for request in requests if request.status == "APPROVED" and (is_superuser(user) or request.created_by_id == user.id or any(step.approved_by_id == user.id for step in request.steps))]
    elif view == "rejected":
        requests = [request for request in requests if request.status == "REJECTED" and (is_superuser(user) or request.created_by_id == user.id or any(step.approved_by_id == user.id for step in request.steps))]
    elif not is_superuser(user):
        requests = [request for request in requests if request.created_by_id == user.id or any(can_user_decide_step(step, user) or step.approved_by_id == user.id for step in request.steps)]
    return [_serialize_request(request, user) for request in requests]


@router.get("/workflows")
def list_workflows(
    entity_type: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _require_admin(user)
    query = db.query(ApprovalWorkflow)
    if entity_type:
        query = query.filter(ApprovalWorkflow.entity_type == entity_type.upper())
    return [_serialize_workflow(item) for item in query.order_by(ApprovalWorkflow.entity_type, ApprovalWorkflow.code).all()]


@router.post("/workflows", status_code=201)
def create_workflow(data: WorkflowInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _require_admin(user)
    _validate_steps(db, data.steps)
    code = data.code.strip().upper()
    if db.query(ApprovalWorkflow).filter(ApprovalWorkflow.code == code).first():
        raise HTTPException(status_code=409, detail="Approval workflow code already exists")
    workflow = ApprovalWorkflow(code=code, name=data.name.strip(), entity_type=data.entity_type.strip().upper(), is_active=data.is_active)
    for step in sorted(data.steps, key=lambda item: (item.step_order, item.name)):
        workflow.steps.append(ApprovalWorkflowStep(
            step_order=step.step_order,
            name=step.name.strip(),
            approver_role_id=step.approver_role_id,
            department_id=step.department_id,
            location_id=step.location_id,
        ))
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return _serialize_workflow(workflow)


@router.put("/workflows/{workflow_id}")
def update_workflow(workflow_id: int, data: WorkflowInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _require_admin(user)
    _validate_steps(db, data.steps)
    workflow = db.get(ApprovalWorkflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Approval workflow not found")
    duplicate = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.code == data.code.strip().upper(), ApprovalWorkflow.id != workflow_id).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Approval workflow code already exists")
    workflow.code = data.code.strip().upper()
    workflow.name = data.name.strip()
    workflow.entity_type = data.entity_type.strip().upper()
    workflow.is_active = data.is_active
    workflow.steps.clear()
    for step in sorted(data.steps, key=lambda item: (item.step_order, item.name)):
        workflow.steps.append(ApprovalWorkflowStep(
            step_order=step.step_order,
            name=step.name.strip(),
            approver_role_id=step.approver_role_id,
            department_id=step.department_id,
            location_id=step.location_id,
        ))
    db.commit()
    db.refresh(workflow)
    return _serialize_workflow(workflow)


@router.get("/{entity_type}/{entity_id}")
def get_approval(entity_type: str, entity_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    request = db.query(ApprovalRequest).filter(
        ApprovalRequest.entity_type == entity_type.upper(),
        ApprovalRequest.entity_id == entity_id,
    ).first()
    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return _serialize_request(request, user)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.approval_workflow import ApprovalWorkflow, ApprovalWorkflowStep
from app.models.department import Department
from app.models.location import Location
from app.models.role import Role
from app.schemas.approval import (
    ApprovalWorkflowCreate,
    ApprovalWorkflowResponse,
    ApprovalWorkflowStepResponse,
)
from app.services.audit import record_audit


router = APIRouter(prefix="/approval-workflows", tags=["Approval Workflows"])


def workflow_query(db: Session):
    return db.query(ApprovalWorkflow).options(
        joinedload(ApprovalWorkflow.steps).joinedload(ApprovalWorkflowStep.approver_role),
        joinedload(ApprovalWorkflow.steps).joinedload(ApprovalWorkflowStep.department),
        joinedload(ApprovalWorkflow.steps).joinedload(ApprovalWorkflowStep.location),
    )


def to_response(workflow: ApprovalWorkflow) -> ApprovalWorkflowResponse:
    return ApprovalWorkflowResponse(
        id=workflow.id,
        code=workflow.code,
        name=workflow.name,
        entity_type=workflow.entity_type,
        is_active=workflow.is_active,
        steps=[
            ApprovalWorkflowStepResponse(
                id=step.id,
                step_order=step.step_order,
                name=step.name,
                approver_role_id=step.approver_role_id,
                approver_role_name=step.approver_role.name,
                department_id=step.department_id,
                department_name=step.department.name if step.department else None,
                location_id=step.location_id,
                location_name=step.location.name if step.location else None,
            )
            for step in sorted(workflow.steps, key=lambda item: item.step_order)
        ],
    )


@router.get("", response_model=list[ApprovalWorkflowResponse])
def get_approval_workflows(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return [to_response(workflow) for workflow in workflow_query(db).order_by(ApprovalWorkflow.id).all()]


@router.post("", response_model=ApprovalWorkflowResponse, status_code=201)
def create_approval_workflow(
    data: ApprovalWorkflowCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if db.query(ApprovalWorkflow).filter(ApprovalWorkflow.code == data.code.strip()).first():
        raise HTTPException(status_code=409, detail="Approval workflow code already exists")

    orders = [step.step_order for step in data.steps]
    if len(orders) != len(set(orders)):
        raise HTTPException(status_code=400, detail="Approval step order must be unique")

    workflow = ApprovalWorkflow(
        code=data.code.strip().upper(),
        name=data.name.strip(),
        entity_type=data.entity_type.strip().upper(),
        is_active=True,
    )

    for step_data in sorted(data.steps, key=lambda item: item.step_order):
        role = db.query(Role).filter(Role.id == step_data.approver_role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="Approval role not found")

        department = None
        if step_data.department_id is not None:
            department = db.query(Department).filter(Department.id == step_data.department_id).first()
            if not department:
                raise HTTPException(status_code=404, detail="Approval department not found")

        location = None
        if step_data.location_id is not None:
            location = db.query(Location).filter(Location.id == step_data.location_id).first()
            if not location:
                raise HTTPException(status_code=404, detail="Approval location not found")

        workflow.steps.append(
            ApprovalWorkflowStep(
                step_order=step_data.step_order,
                name=step_data.name.strip(),
                approver_role_id=role.id,
                department_id=department.id if department else None,
                location_id=location.id if location else None,
            )
        )

    db.add(workflow)
    db.flush()

    record_audit(
        db=db,
        user=current_user,
        action="CREATE",
        entity_type="APPROVAL_WORKFLOW",
        entity_id=workflow.id,
        summary=f"Created approval workflow {workflow.code}",
        details={"workflow_code": workflow.code, "step_count": len(workflow.steps)},
    )

    db.commit()
    return to_response(workflow_query(db).filter(ApprovalWorkflow.id == workflow.id).first())


@router.put("/{workflow_id}", response_model=ApprovalWorkflowResponse)
def replace_approval_workflow(
    workflow_id: int,
    data: ApprovalWorkflowCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    workflow = workflow_query(db).filter(ApprovalWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Approval workflow not found")

    orders = [step.step_order for step in data.steps]
    if len(orders) != len(set(orders)):
        raise HTTPException(status_code=400, detail="Approval step order must be unique")

    before = {
        "code": workflow.code,
        "name": workflow.name,
        "entity_type": workflow.entity_type,
        "steps": [
            {
                "step_order": step.step_order,
                "name": step.name,
                "approver_role_name": step.approver_role.name,
            }
            for step in workflow.steps
        ],
    }

    workflow.code = data.code.strip().upper()
    workflow.name = data.name.strip()
    workflow.entity_type = data.entity_type.strip().upper()
    for old_step in list(workflow.steps):
        db.delete(old_step)
    db.flush()

    for step_data in sorted(data.steps, key=lambda item: item.step_order):
        role = db.query(Role).filter(Role.id == step_data.approver_role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="Approval role not found")

        department = None
        if step_data.department_id is not None:
            department = db.query(Department).filter(Department.id == step_data.department_id).first()
            if not department:
                raise HTTPException(status_code=404, detail="Approval department not found")

        location = None
        if step_data.location_id is not None:
            location = db.query(Location).filter(Location.id == step_data.location_id).first()
            if not location:
                raise HTTPException(status_code=404, detail="Approval location not found")

        workflow.steps.append(
            ApprovalWorkflowStep(
                step_order=step_data.step_order,
                name=step_data.name.strip(),
                approver_role_id=role.id,
                department_id=department.id if department else None,
                location_id=location.id if location else None,
            )
        )

    record_audit(
        db=db,
        user=current_user,
        action="UPDATE",
        entity_type="APPROVAL_WORKFLOW",
        entity_id=workflow.id,
        summary=f"Updated approval workflow {workflow.code}",
        details={"before": before},
    )

    db.commit()
    return to_response(workflow_query(db).filter(ApprovalWorkflow.id == workflow.id).first())

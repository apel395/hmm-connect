from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.approval_request import ApprovalRequest, ApprovalRequestStep
from app.models.approval_workflow import ApprovalWorkflow
from app.schemas.approval import ApprovalStatusResponse, ApprovalStepResponse


router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.get("/{entity_type}/{entity_id}", response_model=ApprovalStatusResponse)
def get_approval_status(
    entity_type: str,
    entity_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    request = (
        db.query(ApprovalRequest)
        .options(
            joinedload(ApprovalRequest.workflow),
            joinedload(ApprovalRequest.steps).joinedload(ApprovalRequestStep.approved_by),
        )
        .filter(
            ApprovalRequest.entity_type == entity_type.upper(),
            ApprovalRequest.entity_id == entity_id,
        )
        .first()
    )

    if not request:
        raise HTTPException(status_code=404, detail="Approval workflow not found")

    current_step = next(
        (
            step
            for step in request.steps
            if step.step_order == request.current_step_order
            and step.status == "PENDING"
        ),
        None,
    )

    return ApprovalStatusResponse(
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        workflow_code=request.workflow.code,
        workflow_name=request.workflow.name,
        status=request.status,
        current_step_order=request.current_step_order,
        current_step_name=current_step.name if current_step else None,
        current_approver_role=(
            current_step.approver_role_name if current_step else None
        ),
        steps=[
            ApprovalStepResponse(
                step_order=step.step_order,
                name=step.name,
                approver_role_name=step.approver_role_name,
                department_name=step.department_name,
                location_name=step.location_name,
                status=step.status,
                approved_by_name=(
                    step.approved_by.full_name
                    if step.approved_by
                    else None
                ),
                decided_at=step.decided_at,
                decision_comment=step.decision_comment,
            )
            for step in sorted(request.steps, key=lambda item: item.step_order)
        ],
    )

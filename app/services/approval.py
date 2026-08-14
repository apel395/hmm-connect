from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.dependencies.authorization import is_superuser, role_names
from app.models.approval_request import ApprovalRequest, ApprovalRequestStep
from app.models.approval_workflow import ApprovalWorkflow, ApprovalWorkflowStep
from app.models.role import Role


PURCHASING_ROLE_CHAIN = (
    (1, "Store Approval", "STORE", True),
    (2, "Chef Approval", "CHEF", True),
    (3, "PM / Camp Boss Approval", "PM/CAMP BOSS", True),
    (4, "Head Office Purchasing Approval", "HO PURCHASING", False),
    (5, "Finance Approval", "FINANCE", False),
    (6, "General Manager Approval", "GENERAL MANAGER", False),
)


def get_request(db: Session, entity_type: str, entity_id: int):
    return db.query(ApprovalRequest).filter(ApprovalRequest.entity_type == entity_type, ApprovalRequest.entity_id == entity_id).first()


def reset_approval(db: Session, entity_type: str, entity_id: int) -> None:
    request = get_request(db, entity_type, entity_id)
    if request:
        db.delete(request)
        db.flush()


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
        "SYSTEM_ADMINISTRATOR",
        "ERP_ADMINISTRATOR",
        "SUPER_ADMIN",
        "ADMINISTRATOR",
        "SYSTEM_ADMIN",
        "ERP_ADMIN",
        "ADMIN",
    }
    for role in roles:
        if _normalized_role_name(role.name) in preferred:
            return role
    return next(
        (role for role in roles if "ADMIN" in _normalized_role_name(role.name)),
        None,
    )


def _role_by_name(db: Session, name: str) -> Role | None:
    normalized = _normalized_role_name(name)
    return next(
        (
            role
            for role in db.query(Role).order_by(Role.id).all()
            if _normalized_role_name(role.name) == normalized
        ),
        None,
    )


def _workflow_entity_type(workflow_code: str) -> str | None:
    return {
        "PR_APPROVAL": "PURCHASE_REQUISITION",
        "PO_APPROVAL": "PURCHASE_ORDER",
        "RR_APPROVAL": "GOODS_RECEIPT",
    }.get(workflow_code)


def _workflow_name(workflow_code: str) -> str:
    return {
        "PR_APPROVAL": "Purchase Requisition Approval",
        "PO_APPROVAL": "Purchase Order Approval",
        "RR_APPROVAL": "Receiving Report Approval",
    }[workflow_code]


def _is_legacy_generated_default(workflow: ApprovalWorkflow) -> bool:
    if workflow.code not in {"PR_APPROVAL", "PO_APPROVAL", "RR_APPROVAL"}:
        return False
    if not workflow.steps:
        return True
    legacy = {"ADMIN", "ADMINISTRATOR", "HO_APPROVER_1", "HO_APPROVER_2"}
    return all(
        _normalized_role_name(step.approver_role.name) in legacy
        or "ADMIN" in _normalized_role_name(step.approver_role.name)
        for step in workflow.steps
    )


def _ensure_default_workflow(
    db: Session,
    *,
    workflow_code: str,
    user=None,
) -> ApprovalWorkflow | None:
    entity_type = _workflow_entity_type(workflow_code)
    if not entity_type:
        return None

    workflow = (
        db.query(ApprovalWorkflow)
        .filter(ApprovalWorkflow.code == workflow_code)
        .first()
    )
    if workflow and not workflow.is_active:
        return None
    if not workflow:
        workflow = ApprovalWorkflow(
            code=workflow_code,
            name=_workflow_name(workflow_code),
            entity_type=entity_type,
            is_active=True,
        )
        db.add(workflow)
        db.flush()

    if not workflow.steps or _is_legacy_generated_default(workflow):
        configured_roles = []
        missing_roles = []
        for order, step_name, role_name, _ in PURCHASING_ROLE_CHAIN:
            role = _role_by_name(db, role_name)
            if role:
                configured_roles.append((order, step_name, role))
            else:
                missing_roles.append(role_name)

        if missing_roles:
            # Keep the administrator/superuser bypass available while the ERP is
            # still being tested. This temporary workflow is regenerated into the
            # real business chain automatically as soon as all business roles exist.
            if user is not None and is_superuser(user):
                administrator_role = _administrator_role(db)
                if not administrator_role:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Administrator testing bypass is unavailable because no "
                            "administrator role exists"
                        ),
                    )
                configured_roles = [
                    (1, "Administrator Testing Approval", administrator_role)
                ]
            else:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Purchasing approval workflow is incomplete. Configure these "
                        "roles before submitting: " + ", ".join(missing_roles)
                    ),
                )

        workflow.steps.clear()
        workflow.steps.extend(
            ApprovalWorkflowStep(
                step_order=order,
                name=step_name,
                approver_role_id=role.id,
            )
            for order, step_name, role in configured_roles
        )
        db.flush()

    return workflow


def _entity_location(db: Session, entity_type: str, entity_id: int):
    if entity_type == "PURCHASE_REQUISITION":
        from app.models.purchase_requisition import PurchaseRequisition

        entity = db.get(PurchaseRequisition, entity_id)
    elif entity_type == "PURCHASE_ORDER":
        from app.models.purchase_order import PurchaseOrder

        entity = db.get(PurchaseOrder, entity_id)
    elif entity_type == "GOODS_RECEIPT":
        from app.models.goods_receipt import GoodsReceipt

        entity = db.get(GoodsReceipt, entity_id)
    else:
        entity = None
    return getattr(entity, "location", None) if entity else None


def _is_local_purchasing_role(role_name: str) -> bool:
    return _normalized_role_name(role_name) in {
        _normalized_role_name("STORE"),
        _normalized_role_name("CHEF"),
        _normalized_role_name("PM/CAMP BOSS"),
    }


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

    workflow = _ensure_default_workflow(
        db,
        workflow_code=workflow_code,
        user=user,
    )
    if not workflow or not workflow.steps:
        raise HTTPException(
            status_code=400,
            detail=f"Active approval workflow {workflow_code!r} is not configured",
        )

    entity_location = _entity_location(db, entity_type, entity_id)
    local_steps = [
        step
        for step in workflow.steps
        if _is_local_purchasing_role(step.approver_role.name)
    ]
    # Superuser testing remains possible even while organization master data is
    # incomplete. Ordinary business users still require a valid site/location.
    if local_steps and entity_location is None and not is_superuser(user):
        raise HTTPException(
            status_code=409,
            detail="Location is required before starting the purchasing approval workflow",
        )

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
        location_name = step.location.name if step.location else None
        if (
            not location_name
            and entity_location
            and _is_local_purchasing_role(step.approver_role.name)
        ):
            location_name = entity_location.name
        request.steps.append(
            ApprovalRequestStep(
                step_order=step.step_order,
                name=step.name,
                approver_role_name=step.approver_role.name,
                department_name=(step.department.name if step.department else None),
                location_name=location_name,
                status="PENDING" if step.step_order == first_order else "WAITING",
            )
        )

    db.add(request)
    db.flush()
    return request


def current_steps(request: ApprovalRequest) -> list[ApprovalRequestStep]:
    if request.current_step_order is None:
        return []
    return [
        step
        for step in request.steps
        if step.step_order == request.current_step_order and step.status == "PENDING"
    ]


def can_user_decide_step(step: ApprovalRequestStep, user) -> bool:
    if is_superuser(user):
        return True
    if step.approver_role_name.strip().upper() not in role_names(user):
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


def _select_current_step(
    request: ApprovalRequest,
    user,
) -> ApprovalRequestStep:
    for step in current_steps(request):
        if can_user_decide_step(step, user):
            return step
    if not current_steps(request):
        raise HTTPException(status_code=409, detail="No pending approval step")
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

from datetime import datetime

from pydantic import BaseModel, Field


class ApprovalStepResponse(BaseModel):
    step_order: int
    name: str
    approver_role_name: str
    department_name: str | None
    location_name: str | None
    status: str
    approved_by_name: str | None = None
    decided_at: datetime | None = None
    decision_comment: str | None = None


class ApprovalStatusResponse(BaseModel):
    entity_type: str
    entity_id: int
    workflow_code: str
    workflow_name: str
    status: str
    current_step_order: int | None
    current_step_name: str | None
    current_approver_role: str | None
    steps: list[ApprovalStepResponse]


class ApprovalDecisionRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=1000)


class ApprovalWorkflowStepCreate(BaseModel):
    step_order: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=150)
    approver_role_id: int
    department_id: int | None = None
    location_id: int | None = None


class ApprovalWorkflowCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=150)
    entity_type: str = Field(min_length=1, max_length=80)
    steps: list[ApprovalWorkflowStepCreate] = Field(min_length=1)


class ApprovalWorkflowStepResponse(BaseModel):
    id: int
    step_order: int
    name: str
    approver_role_id: int
    approver_role_name: str
    department_id: int | None
    department_name: str | None
    location_id: int | None
    location_name: str | None


class ApprovalWorkflowResponse(BaseModel):
    id: int
    code: str
    name: str
    entity_type: str
    is_active: bool
    steps: list[ApprovalWorkflowStepResponse]

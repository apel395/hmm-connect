from pydantic import BaseModel


class ApprovalDecisionRequest(BaseModel):
    comment: str | None = None

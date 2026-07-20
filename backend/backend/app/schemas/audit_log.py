from datetime import datetime

from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None
    user_name: str | None = None
    actor_name: str | None = None
    department_id: int | None = None
    department_name: str | None = None
    location_id: int | None = None
    location_name: str | None = None
    role_names: list[str] = Field(default_factory=list)
    action: str
    entity_type: str
    entity_id: int | None
    summary: str
    details: dict | None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse] = Field(default_factory=list)

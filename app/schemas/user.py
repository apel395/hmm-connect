from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.auth import RoleSummary


class DepartmentSummary(BaseModel):
    id: int
    code: str
    name: str

    model_config = {"from_attributes": True}


class LocationSummary(BaseModel):
    id: int
    code: str
    name: str
    location_type: str

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    is_active: bool
    department_id: int | None = None
    location_id: int | None = None
    department: DepartmentSummary | None = None
    location: LocationSummary | None = None
    roles: list[RoleSummary] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

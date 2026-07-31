from datetime import datetime

from pydantic import BaseModel, Field, field_validator

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


class UserDetailResponse(UserResponse):
    role_ids: list[int] = Field(default_factory=list)


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=50)
    email: str | None = Field(
        default=None,
        min_length=3,
        max_length=120,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    is_active: bool | None = None
    department_id: int | None = None
    location_id: int | None = None

    @field_validator("username", "email", "full_name", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be empty")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return value.lower() if value is not None else None


class UserRolesUpdate(BaseModel):
    role_ids: list[int] = Field(default_factory=list)

    @field_validator("role_ids")
    @classmethod
    def reject_duplicate_roles(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("role_ids must not contain duplicates")
        return value

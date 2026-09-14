from pydantic import BaseModel, Field, field_validator


class PermissionSummary(BaseModel):
    id: int
    code: str
    description: str | None = None

    model_config = {"from_attributes": True}


class RoleSummary(BaseModel):
    id: int
    name: str
    description: str | None = None
    permissions: list[PermissionSummary] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class UserSummary(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    is_active: bool
    business_unit_id: int | None = None
    department_id: int | None = None
    location_id: int | None = None
    default_business_unit_id: int | None = None
    default_department_id: int | None = None
    default_location_id: int | None = None
    roles: list[RoleSummary] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserSummary


class RegistrationRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    full_name: str = Field(min_length=1, max_length=150)
    email: str = Field(
        min_length=3,
        max_length=120,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    password: str = Field(min_length=1)

    @field_validator("username", "full_name", "email", mode="before")
    @classmethod
    def trim_required_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be empty")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class RegistrationResponse(BaseModel):
    id: int
    username: str
    full_name: str
    email: str
    is_active: bool
    requires_admin_access: bool
    message: str

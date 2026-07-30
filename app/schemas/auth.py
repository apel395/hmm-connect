from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


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
    roles: list[RoleSummary] = Field(default_factory=list)

    model_config = {"from_attributes": True}

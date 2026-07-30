from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserSummary(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    is_active: bool

    model_config = {"from_attributes": True}

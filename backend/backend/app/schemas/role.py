from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=200)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=200)


class RoleResponse(BaseModel):
    id: int
    name: str
    description: str | None

    class Config:
        from_attributes = True

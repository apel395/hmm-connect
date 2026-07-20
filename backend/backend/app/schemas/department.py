from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=100)


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class DepartmentResponse(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool

    class Config:
        from_attributes = True

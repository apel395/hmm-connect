from pydantic import BaseModel


class WarehouseCreate(BaseModel):
    code: str
    name: str
    address: str | None = None


class WarehouseResponse(BaseModel):
    id: int
    code: str
    name: str
    address: str | None
    is_active: bool

    class Config:
        from_attributes = True

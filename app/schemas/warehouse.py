from pydantic import BaseModel, Field


class WarehouseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    address: str | None = None
    location_id: int | None = None


class WarehouseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    address: str | None = None
    location_id: int | None = None
    is_active: bool | None = None

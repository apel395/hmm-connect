from decimal import Decimal

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=150,
    )
    group_code: str = Field(
        min_length=1,
        max_length=10,
    )
    group_name: str = Field(
        min_length=1,
        max_length=100,
    )
    subgroup_code: str = Field(
        min_length=1,
        max_length=10,
    )
    subgroup_name: str = Field(
        min_length=1,
        max_length=100,
    )
    uom: str = Field(
        min_length=1,
        max_length=20,
    )
    usage_uom: str = Field(
        min_length=1,
        max_length=20,
    )
    conversion: Decimal = Field(
        gt=0,
    )


class ProductResponse(BaseModel):
    id: int
    code: str
    name: str

    group_code: str
    group_name: str

    subgroup_code: str
    subgroup_name: str

    uom: str
    usage_uom: str
    conversion: Decimal

    is_active: bool

    class Config:
        from_attributes = True

from decimal import Decimal

from pydantic import BaseModel


class ProductCreate(BaseModel):
    code: str
    name: str
    group_code: str
    group_name: str
    subgroup_code: str
    subgroup_name: str
    uom: str
    usage_uom: str
    conversion: Decimal = Decimal("1")
    description: str | None = None
    cost_price: Decimal = Decimal("0")
    selling_price: Decimal = Decimal("0")
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: str | None = None
    group_code: str | None = None
    group_name: str | None = None
    subgroup_code: str | None = None
    subgroup_name: str | None = None
    uom: str | None = None
    usage_uom: str | None = None
    conversion: Decimal | None = None
    description: str | None = None
    cost_price: Decimal | None = None
    selling_price: Decimal | None = None
    is_active: bool | None = None

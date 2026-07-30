from decimal import Decimal

from pydantic import BaseModel, Field


class SupplierProductCreate(BaseModel):
    product_id: int
    supplier_price: Decimal | None = Field(default=None, ge=0)
    lead_time_days: int | None = Field(default=None, ge=0)
    is_preferred: bool = False
    supplier_sku: str | None = None


class SupplierProductResponse(SupplierProductCreate):
    id: int
    supplier_id: int

    product_code: str
    product_name: str

    product_uom: str
    product_usage_uom: str

    conversion: Decimal

    class Config:
        from_attributes = True


class SupplierProductMatchResponse(BaseModel):
    supplier_id: int
    supplier_code: str
    supplier_name: str
    supplier_price: Decimal | None
    lead_time_days: int | None
    is_preferred: bool
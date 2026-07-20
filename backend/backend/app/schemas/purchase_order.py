from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class PurchaseOrderItemCreate(BaseModel):
    product_id: int
    quantity: Decimal
    unit_price: Decimal
    purchase_requisition_item_id: int | None = None


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    purchase_requisition_ids: list[int] = Field(default_factory=list)
    expected_date: date | None = None
    expiry_date: date | None = None
    receipt_tolerance_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    notes: str | None = None
    items: list[PurchaseOrderItemCreate]


class PurchaseOrderItemResponse(BaseModel):
    id: int
    purchase_order_id: int
    purchase_requisition_item_id: int | None
    product_id: int
    quantity: Decimal
    received_quantity: Decimal
    unit_price: Decimal
    total_price: Decimal

    class Config:
        from_attributes = True


class PurchaseOrderResponse(BaseModel):
    id: int
    po_number: str
    supplier_id: int
    purchase_requisition_id: int | None
    purchase_requisition_ids: list[int]
    status: str
    order_date: date
    expected_date: date | None
    expiry_date: date | None
    receipt_tolerance_percent: Decimal
    total_amount: Decimal
    notes: str | None
    items: list[PurchaseOrderItemResponse]

    class Config:
        from_attributes = True

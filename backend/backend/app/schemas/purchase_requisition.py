from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class PurchaseRequisitionItemCreate(BaseModel):
    product_id: int
    quantity: Decimal
    estimated_price: Decimal


class PurchaseRequisitionCreate(BaseModel):
    notes: str | None = None
    items: list[PurchaseRequisitionItemCreate]


class PurchaseRequisitionConvertCreate(BaseModel):
    supplier_id: int


class PurchaseRequisitionItemResponse(BaseModel):
    id: int
    product_id: int
    product_code: str
    product_name: str
    product_uom: str
    quantity: Decimal
    estimated_price: Decimal
    total_price: Decimal

    class Config:
        from_attributes = True


class PurchaseRequisitionResponse(BaseModel):
    id: int
    pr_number: str
    status: str
    request_date: date
    total_amount: Decimal
    items: list[PurchaseRequisitionItemResponse]

    class Config:
        from_attributes = True

class TraceabilityEventResponse(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: int | None
    summary: str
    user_name: str | None
    created_at: str


class TraceabilityPurchaseOrderResponse(BaseModel):
    id: int
    po_number: str
    status: str


class TraceabilityGoodsReceiptResponse(BaseModel):
    id: int
    receipt_number: str
    purchase_order_id: int


class TraceabilityStockMovementResponse(BaseModel):
    id: int
    product_id: int
    quantity: Decimal
    goods_receipt_id: int | None


class PurchaseRequisitionTraceabilityResponse(BaseModel):
    purchase_requisition_id: int
    pr_number: str
    purchase_orders: list[TraceabilityPurchaseOrderResponse]
    goods_receipts: list[TraceabilityGoodsReceiptResponse]
    stock_movements: list[TraceabilityStockMovementResponse]
    events: list[TraceabilityEventResponse]

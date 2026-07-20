from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class AccountPayableResponse(BaseModel):
    id: int
    supplier_id: int
    purchase_order_id: int | None
    invoice_number: str | None
    invoice_date: date | None
    due_date: date | None
    amount: Decimal
    status: str

    class Config:
        from_attributes = True


class AccountReceiptResponse(BaseModel):
    id: int
    goods_receipt_id: int
    product_id: int
    account_id: int
    quantity: Decimal
    unit_cost: Decimal
    total_amount: Decimal
    created_at: datetime

    class Config:
        from_attributes = True

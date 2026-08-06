from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, model_validator
class SupplierInvoiceLineInput(BaseModel):
    product_id: int | None = None; purchase_order_item_id: int | None = None; goods_receipt_item_id: int | None = None
    description: str = Field(min_length=1); quantity: Decimal = Field(ge=0); uom: str | None = None
    unit_price: Decimal = Field(ge=0); account_id: int | None = None; department_id: int | None = None; notes: str | None = None
class SupplierInvoiceInput(BaseModel):
    business_unit_id: int | None = None
    supplier_invoice_number: str = Field(min_length=1, max_length=100); supplier_id: int; invoice_date: date
    received_date: date | None = None; due_date: date | None = None; purchase_order_id: int | None = None; goods_receipt_id: int | None = None
    department_id: int | None = None; location_id: int | None = None; currency: str = Field(default="IDR", min_length=3, max_length=3)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0); tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    withholding_tax_amount: Decimal = Field(default=Decimal("0"), ge=0); total_amount: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None; source_type: Literal["LIVE", "HISTORICAL_IMPORT"] = "LIVE"; lines: list[SupplierInvoiceLineInput]
    @model_validator(mode="after")
    def validate_lines(self):
        if not self.lines: raise ValueError("Invoice must contain at least one line")
        return self

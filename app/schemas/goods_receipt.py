from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class GoodsReceiptItemCreate(BaseModel):
    purchase_order_item_id: int | None = None
    market_list_item_id: int | None = None
    product_id: int | None = None
    expense_account_id: int | None = None
    destination_type: Literal["WAREHOUSE", "DIRECT_USE"] | None = None
    destination_override_reason: str | None = Field(default=None, max_length=500)
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal | None = Field(default=None, gt=0)
    is_taxable: bool = False
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)

    @model_validator(mode="after")
    def validate_tax(self):
        if not self.is_taxable:
            self.tax_rate = Decimal("0")
        return self


class GoodsReceiptCreate(BaseModel):
    business_unit_id: int | None = None
    location_id: int | None = None
    department_id: int | None = None
    market_list_id: int | None = None
    purchase_order_id: int | None = None
    supplier_id: int | None = None
    received_at: datetime | None = None
    source_type: Literal["LIVE", "HISTORICAL_IMPORT", "HISTORICAL_ENTRY"] = "LIVE"
    external_reference: str | None = Field(default=None, max_length=100)
    receipt_type: Literal["GOODS", "SERVICE"] = "GOODS"
    warehouse_id: int | None = None
    destination_type: Literal["WAREHOUSE", "DIRECT_USE"] | None = None
    notes: str | None = None
    supplier_invoice_number: str | None = Field(default=None, max_length=100)
    supplier_document_total: Decimal | None = Field(default=None, gt=0)
    supplier_invoice_date: date | None = None
    supplier_invoice_due_date: date | None = None
    tax_invoice_number: str | None = Field(default=None, max_length=100)
    tax_invoice_date: date | None = None
    supplier_document_url: str | None = Field(default=None, max_length=2000)
    discount_amount: Decimal = Field(default=Decimal('0'), ge=0)
    shipping_fee_amount: Decimal = Field(default=Decimal('0'), ge=0)
    admin_fee_amount: Decimal = Field(default=Decimal('0'), ge=0)
    other_fee_amount: Decimal = Field(default=Decimal('0'), ge=0)
    other_fee_description: str | None = Field(default=None, max_length=250)
    shipping_fee_account_id: int | None = None
    admin_fee_account_id: int | None = None
    other_fee_account_id: int | None = None
    cost_correction_reason: str | None = Field(default=None, max_length=500)
    items: list[GoodsReceiptItemCreate]

    @model_validator(mode="after")
    def validate_source(self):
        if not self.items:
            raise ValueError("Receipt must contain items")
        if self.purchase_order_id and self.market_list_id:
            raise ValueError("Choose one source: Purchase Order or Market List")
        if self.market_list_id and any(item.market_list_item_id is None for item in self.items):
            raise ValueError("ML receipts require a Market List item on every line")
        if self.purchase_order_id:
            if any(item.purchase_order_item_id is None for item in self.items):
                raise ValueError("PO receipts require purchase_order_item_id for every line")
        else:
            if self.supplier_id is None:
                raise ValueError("Direct receipts require supplier_id")
            if self.business_unit_id is None or self.department_id is None or self.location_id is None:
                raise ValueError("Direct receipts require business unit, department and location")
            if any(item.product_id is None or item.unit_cost is None for item in self.items):
                raise ValueError("Direct receipt lines require product_id and unit_cost")
        return self


class GoodsReceiptCostCorrectionLine(BaseModel):
    item_id: int
    unit_cost: Decimal = Field(gt=0)


class GoodsReceiptCostCorrection(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    items: list[GoodsReceiptCostCorrectionLine]

    @model_validator(mode="after")
    def validate_items(self):
        if not self.items:
            raise ValueError("At least one receipt item cost is required")
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValueError("A receipt item may appear only once")
        return self


class GoodsReceiptItemUpdate(BaseModel):
    item_id: int | None = None
    product_id: int | None = None
    expense_account_id: int | None = None
    destination_type: Literal["WAREHOUSE", "DIRECT_USE"] | None = None
    destination_override_reason: str | None = Field(default=None, max_length=500)
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(gt=0)
    is_taxable: bool
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)

    @model_validator(mode="after")
    def validate_tax(self):
        if not self.is_taxable:
            self.tax_rate = Decimal("0")
        if self.item_id is None and self.product_id is None:
            raise ValueError("New receiving lines require product_id")
        if self.item_id is not None and self.product_id is not None:
            raise ValueError("Existing receiving lines cannot change product identity")
        return self


class GoodsReceiptUpdate(BaseModel):
    received_at: datetime
    location_id: int | None = None
    external_reference: str | None = Field(default=None, max_length=100)
    destination_type: Literal["WAREHOUSE", "DIRECT_USE"] | None = None
    warehouse_id: int | None = None
    notes: str | None = None
    supplier_invoice_number: str | None = Field(default=None, max_length=100)
    supplier_invoice_date: date | None = None
    supplier_invoice_due_date: date | None = None
    tax_invoice_number: str | None = Field(default=None, max_length=100)
    tax_invoice_date: date | None = None
    supplier_document_url: str | None = Field(default=None, max_length=2000)
    discount_amount: Decimal = Field(default=Decimal('0'), ge=0)
    shipping_fee_amount: Decimal = Field(default=Decimal('0'), ge=0)
    admin_fee_amount: Decimal = Field(default=Decimal('0'), ge=0)
    other_fee_amount: Decimal = Field(default=Decimal('0'), ge=0)
    other_fee_description: str | None = Field(default=None, max_length=250)
    shipping_fee_account_id: int | None = None
    admin_fee_account_id: int | None = None
    other_fee_account_id: int | None = None
    items: list[GoodsReceiptItemUpdate]

    supplier_document_total: Decimal | None = Field(default=None, gt=0)
    @model_validator(mode="after")
    def validate_update(self):
        if not self.items:
            raise ValueError("Receipt must contain items")
        stored_ids = [item.item_id for item in self.items if item.item_id is not None]
        if len(set(stored_ids)) != len(stored_ids):
            raise ValueError("A receipt item may appear only once")
        return self



class GoodsReceiptDepost(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

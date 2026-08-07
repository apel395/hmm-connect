from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class SupplierAdjustmentCreate(BaseModel):
    adjustment_type: Literal["CREDIT_NOTE", "DEBIT_NOTE"]
    supplier_invoice_id: int
    adjustment_date: date
    amount: Decimal = Field(gt=0)
    adjustment_account_id: int
    reason: str = Field(min_length=1, max_length=255)
    notes: str | None = None


class SupplierAdjustmentUpdate(BaseModel):
    adjustment_date: date | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    adjustment_account_id: int | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = None

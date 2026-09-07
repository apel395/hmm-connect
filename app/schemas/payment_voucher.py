from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class VoucherAllocationInput(BaseModel):
    supplier_invoice_id: int
    allocated_amount: Decimal = Field(gt=0)


class PaymentVoucherCreate(BaseModel):
    location_id: int
    voucher_date: date
    period_from: date | None = None
    period_to: date | None = None
    notes: str | None = None
    source_type: Literal["LIVE", "HISTORICAL_IMPORT"] = "LIVE"
    allocations: list[VoucherAllocationInput]

    @model_validator(mode="after")
    def validate(self):
        if not self.allocations:
            raise ValueError("Voucher requires at least one invoice allocation")
        if len({x.supplier_invoice_id for x in self.allocations}) != len(self.allocations):
            raise ValueError("Duplicate invoice in voucher")
        return self


class PaymentVoucherUpdate(PaymentVoucherCreate):
    pass

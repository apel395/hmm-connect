from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator

DocumentType = Literal["PURCHASE_REQUISITION", "PURCHASE_ORDER", "GOODS_RECEIPT", "SUPPLIER_INVOICE", "PAYMENT", "JOURNAL_ENTRY"]
ImportMode = Literal["STRICT", "PARTIAL", "DRY_RUN"]


class ImportBatchCreate(BaseModel):
    batch_name: str = Field(min_length=1, max_length=150)
    import_type: DocumentType
    import_mode: ImportMode = "STRICT"
    period_from: date | None = None
    period_to: date | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def valid_period(self):
        if self.period_from and self.period_to and self.period_to < self.period_from:
            raise ValueError("Period to cannot be before period from")
        return self


class ConfirmImport(BaseModel):
    confirm_warnings: bool = False

from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator

class BankTransferInput(BaseModel):
    transfer_date: date
    source_account_id: int
    destination_account_id: int
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    reference_number: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    @model_validator(mode="after")
    def distinct_accounts(self):
        if self.source_account_id == self.destination_account_id: raise ValueError("Source and destination accounts must differ")
        return self

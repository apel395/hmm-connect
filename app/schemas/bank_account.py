from pydantic import BaseModel, Field


class BankAccountInput(BaseModel):
    bank_name: str = Field(min_length=1, max_length=120)
    account_name: str = Field(min_length=1, max_length=180)
    account_number: str = Field(min_length=1, max_length=100)
    account_holder: str | None = Field(default=None, max_length=180)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    business_unit_id: int
    location_id: int | None = None
    coa_account_id: int
    is_active: bool = True

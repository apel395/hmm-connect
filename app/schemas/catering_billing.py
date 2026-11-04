from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class CateringBilling(BaseModel):
    template: Literal["phr", "standard"] = "phr"
    title: str = Field(default="INVOICE", min_length=1, max_length=100)
    billing_name: str = Field(default="", max_length=200)
    billing_address: str = Field(default="", max_length=1000)
    attention: str = Field(default="", max_length=200)
    contract_number: str = Field(default="", max_length=100)
    contract_date: date | None = None
    company_address: str = Field(default="", max_length=1000)
    payment_instructions: str = Field(default="", max_length=2000)
    footer: str = Field(default="", max_length=1000)
    signer_name: str = Field(default="", max_length=200)
    signer_position: str = Field(default="", max_length=200)


class CateringLocationSettings(BaseModel):
    customer_id: int | None = Field(default=None, gt=0)
    department_id: int | None = Field(default=None, gt=0)
    revenue_account_id: int | None = Field(default=None, gt=0)
    receivable_account_id: int | None = Field(default=None, gt=0)
    payment_term_days: int | None = Field(default=None, ge=0, le=365)
    service_product_ids: list[int] = Field(default_factory=list, max_length=200)
    billing: CateringBilling = Field(default_factory=CateringBilling)

    @model_validator(mode="after")
    def unique_products(self):
        if any(i <= 0 for i in self.service_product_ids) or len(set(self.service_product_ids)) != len(self.service_product_ids):
            raise ValueError("Choose each service once")
        return self

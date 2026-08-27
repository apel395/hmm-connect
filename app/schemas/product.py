from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

TaxCategory = Literal["STANDARD", "EXEMPT", "NON_VAT", "SPECIAL", "REVIEW_REQUIRED"]


class ProductCreate(BaseModel):
    code: str
    name: str
    group_code: str
    group_name: str
    subgroup_code: str
    subgroup_name: str
    uom: str
    usage_uom: str
    conversion: Decimal = Decimal("1")
    description: str | None = None
    cost_price: Decimal = Decimal("0")
    selling_price: Decimal = Decimal("0")
    tax_category: TaxCategory = "REVIEW_REQUIRED"
    is_taxable: bool = False
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    tax_reason: str | None = Field(default=None, max_length=255)
    tax_reference: str | None = Field(default=None, max_length=255)
    minimum_stock: Decimal = Field(default=Decimal("0"), ge=0)
    is_market_item: bool = False
    is_active: bool = True

    @model_validator(mode="after")
    def validate_tax_profile(self):
        if not self.is_taxable:
            self.tax_rate = Decimal("0")
        if self.tax_category in {"EXEMPT", "NON_VAT", "REVIEW_REQUIRED"}:
            self.is_taxable = False
            self.tax_rate = Decimal("0")
        return self


class ProductUpdate(BaseModel):
    name: str | None = None
    group_code: str | None = None
    group_name: str | None = None
    subgroup_code: str | None = None
    subgroup_name: str | None = None
    uom: str | None = None
    usage_uom: str | None = None
    conversion: Decimal | None = None
    description: str | None = None
    cost_price: Decimal | None = None
    selling_price: Decimal | None = None
    tax_category: TaxCategory | None = None
    is_taxable: bool | None = None
    tax_rate: Decimal | None = Field(default=None, ge=0, le=100)
    tax_reason: str | None = Field(default=None, max_length=255)
    tax_reference: str | None = Field(default=None, max_length=255)
    minimum_stock: Decimal | None = Field(default=None, ge=0)
    is_market_item: bool | None = None
    is_active: bool | None = None


class ProductTaxProfileUpdate(BaseModel):
    tax_category: TaxCategory
    is_taxable: bool = False
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    tax_reason: str | None = Field(default=None, max_length=255)
    tax_reference: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_tax_profile(self):
        if self.tax_category in {"EXEMPT", "NON_VAT", "REVIEW_REQUIRED"}:
            self.is_taxable = False
            self.tax_rate = Decimal("0")
        elif not self.is_taxable:
            self.tax_rate = Decimal("0")
        return self

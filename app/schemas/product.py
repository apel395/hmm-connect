from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

TaxCategory = Literal["STANDARD", "EXEMPT", "NON_TAXABLE", "SPECIAL", "REVIEW_REQUIRED"]
InventoryTreatment = Literal["STOCK", "DIRECT_USE", "FIXED_ASSET", "NON_STOCK", "REVIEW_REQUIRED"]


class ProductCreate(BaseModel):
    code: str = ""
    auto_code: bool = False
    name: str
    group_code: str
    group_name: str
    subgroup_code: str
    subgroup_name: str
    uom: str
    usage_uom: str
    conversion: Decimal = Decimal("1")
    department_id: int | None = Field(default=None, gt=0)
    description: str | None = None
    item_type: Literal["BUY", "SELL"] = "BUY"
    catalog_type: Literal["CATERING", "HOTEL"] = "CATERING"
    reference_cost_method: Literal["LAST_PURCHASE", "AVERAGE_PURCHASE", "MANUAL"] = "LAST_PURCHASE"
    cost_price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    selling_price: Decimal = Decimal("0")
    sales_service_name: str | None = Field(default=None, max_length=120)
    sales_business_unit_id: int | None = None
    sales_location_id: int | None = None
    service_charge_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    pbjt_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    sales_ppn_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    pph23_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    tax_category: TaxCategory = "REVIEW_REQUIRED"
    is_taxable: bool = False
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    tax_reason: str | None = Field(default=None, max_length=255)
    tax_reference: str | None = Field(default=None, max_length=255)
    minimum_stock: Decimal = Field(default=Decimal("0"), ge=0)
    inventory_account_id: int | None = None
    purchase_account_id: int | None = None
    cogs_account_id: int | None = None
    asset_account_id: int | None = None
    inventory_treatment: InventoryTreatment = "REVIEW_REQUIRED"
    is_market_item: bool = False
    is_active: bool = True

    @model_validator(mode="after")
    def validate_tax_profile(self):
        if not self.is_taxable:
            self.tax_rate = Decimal("0")
        if self.tax_category in {"EXEMPT", "NON_TAXABLE", "REVIEW_REQUIRED"}:
            self.is_taxable = False
            self.tax_rate = Decimal("0")
        return self


class ProductUpdate(BaseModel):
    correct_existing_stock: bool = False
    stock_correction_reason: str | None = Field(default=None, max_length=500)
    regenerate_code: bool = False
    expected_code: str | None = Field(default=None, max_length=20)
    name: str | None = None
    group_code: str | None = None
    group_name: str | None = None
    subgroup_code: str | None = None
    subgroup_name: str | None = None
    uom: str | None = None
    usage_uom: str | None = None
    conversion: Decimal | None = None
    department_id: int | None = Field(default=None, gt=0)
    description: str | None = None
    item_type: Literal["BUY", "SELL"] | None = None
    catalog_type: Literal["CATERING", "HOTEL"] | None = None
    reference_cost_method: Literal["LAST_PURCHASE", "AVERAGE_PURCHASE", "MANUAL"] | None = None
    cost_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    selling_price: Decimal | None = None
    sales_service_name: str | None = Field(default=None, max_length=120)
    sales_business_unit_id: int | None = None
    sales_location_id: int | None = None
    service_charge_rate: Decimal | None = Field(default=None, ge=0, le=100)
    pbjt_rate: Decimal | None = Field(default=None, ge=0, le=100)
    sales_ppn_rate: Decimal | None = Field(default=None, ge=0, le=100)
    pph23_rate: Decimal | None = Field(default=None, ge=0, le=100)
    tax_category: TaxCategory | None = None
    is_taxable: bool | None = None
    tax_rate: Decimal | None = Field(default=None, ge=0, le=100)
    tax_reason: str | None = Field(default=None, max_length=255)
    tax_reference: str | None = Field(default=None, max_length=255)
    minimum_stock: Decimal | None = Field(default=None, ge=0)
    inventory_account_id: int | None = None
    purchase_account_id: int | None = None
    cogs_account_id: int | None = None
    asset_account_id: int | None = None
    inventory_treatment: InventoryTreatment | None = None
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
        if self.tax_category in {"EXEMPT", "NON_TAXABLE", "REVIEW_REQUIRED"}:
            self.is_taxable = False
            self.tax_rate = Decimal("0")
            return self
        if not self.is_taxable:
            raise ValueError("STANDARD or SPECIAL tax profile must be taxable")
        if self.tax_rate <= 0:
            raise ValueError("Tax rate must be greater than zero for a taxable product")
        return self

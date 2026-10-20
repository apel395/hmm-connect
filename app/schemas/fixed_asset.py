from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator

class CategoryInput(BaseModel):
    @model_validator(mode='before')
    @classmethod
    def non_depreciable_default(cls, values):
        if isinstance(values, dict) and values.get('is_depreciable') is False and 'default_useful_life_months' not in values:
            return {**values, 'default_useful_life_months': None}
        return values

    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=120)
    is_depreciable: bool = True
    default_useful_life_months: int | None = Field(default=48, gt=0)
    default_residual_percentage: Decimal = Field(default=Decimal("0"), ge=0, lt=100)
    asset_account_id: int
    accumulated_depreciation_account_id: int | None = None
    depreciation_expense_account_id: int | None = None
    disposal_gain_account_id: int | None = None
    disposal_loss_account_id: int | None = None
    is_active: bool = True
    description: str | None = None

class AssetInput(BaseModel):
    product_id: int | None = None
    asset_name: str = Field(min_length=1)
    asset_category_id: int
    description: str | None = None
    serial_number: str | None = None
    barcode: str | None = None
    acquisition_date: date
    capitalization_date: date | None = None
    accumulated_depreciation: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=4)
    acquisition_cost: Decimal = Field(gt=0)
    residual_value: Decimal = Field(default=Decimal("0"), ge=0)
    useful_life_months: int | None = Field(default=None, gt=0)
    depreciation_method: str = "STRAIGHT_LINE"
    depreciation_start_date: date | None = None
    business_unit_id: int
    location_id: int | None = None
    department_id: int | None = None
    custodian_user_id: int | None = None
    supplier_id: int | None = None
    purchase_invoice_id: int | None = None
    purchase_order_id: int | None = None
    goods_receipt_id: int | None = None
    asset_account_id: int
    accumulated_depreciation_account_id: int | None = None
    depreciation_expense_account_id: int | None = None
    disposal_gain_account_id: int | None = None
    disposal_loss_account_id: int | None = None
    source_type: str = "MANUAL"
    external_reference: str | None = None
    notes: str | None = None

class AssetUpdate(BaseModel):
    product_id: int | None = None
    asset_name: str | None = None
    description: str | None = None
    serial_number: str | None = None
    barcode: str | None = None
    business_unit_id: int | None = None
    location_id: int | None = None
    department_id: int | None = None
    custodian_user_id: int | None = None
    notes: str | None = None

class CapitalizeInput(BaseModel):
    capitalization_date: date
    depreciation_start_date: date | None = None
    offset_account_id: int | None = None
    create_journal: bool = False

class TransferInput(BaseModel):
    create_journal: bool = True
    movement_date: date
    business_unit_id: int
    location_id: int | None = None
    department_id: int | None = None
    custodian_user_id: int | None = None
    reference_number: str | None = None
    notes: str | None = None

class DisposalInput(BaseModel):
    disposal_date: date
    disposal_proceeds: Decimal = Field(default=Decimal("0"), ge=0)
    cash_account_id: int | None = None
    buyer_reference: str | None = None
    reason: str | None = None
    notes: str | None = None

class WriteOffInput(BaseModel):
    write_off_date: date
    reason: str | None = None
    notes: str | None = None

class RunInput(BaseModel):
    period_year: int
    period_month: int = Field(ge=1, le=12)
    business_unit_id: int | None = None
    location_id: int | None = None
    notes: str | None = None

class CategoryAssignmentInput(BaseModel):
    asset_category_id: int

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


AccountType = Literal["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"]
NormalBalance = Literal["DEBIT", "CREDIT"]
AccountSubtype = Literal["CASH", "BANK", "PETTY_CASH", "OTHER"]
CashFlowCategory = Literal["OPERATING", "INVESTING", "FINANCING", "NON_CASH", "UNCLASSIFIED"]
FinancialStatementGroup = Literal[
    "CURRENT_ASSET", "NON_CURRENT_ASSET", "CURRENT_LIABILITY",
    "NON_CURRENT_LIABILITY", "EQUITY", "OPERATING_REVENUE",
    "OTHER_REVENUE", "COST_OF_REVENUE", "OPERATING_EXPENSE", "OTHER_EXPENSE",
]


class ChartOfAccountBase(BaseModel):
    account_code: str = Field(min_length=1, max_length=30)
    account_name: str = Field(min_length=1, max_length=150)
    account_type: AccountType
    parent_account_id: int | None = None
    normal_balance: NormalBalance | None = None
    description: str | None = Field(default=None, max_length=500)
    is_posting: bool = True
    is_active: bool = True
    account_subtype: AccountSubtype = "OTHER"
    cash_flow_category: CashFlowCategory | None = None
    financial_statement_group: FinancialStatementGroup | None = None

    @field_validator("account_code", "account_name")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("description")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ChartOfAccountCreate(ChartOfAccountBase):
    pass


class ChartOfAccountUpdate(BaseModel):
    account_code: str | None = Field(default=None, min_length=1, max_length=30)
    account_name: str | None = Field(default=None, min_length=1, max_length=150)
    account_type: AccountType | None = None
    parent_account_id: int | None = None
    normal_balance: NormalBalance | None = None
    description: str | None = Field(default=None, max_length=500)
    account_subtype: AccountSubtype | None = None
    cash_flow_category: CashFlowCategory | None = None
    financial_statement_group: FinancialStatementGroup | None = None
    is_posting: bool | None = None
    is_active: bool | None = None

    @field_validator("account_code", "account_name")
    @classmethod
    def strip_present(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ChartOfAccountRead(ChartOfAccountBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    normal_balance: NormalBalance
    is_system: bool
    created_at: datetime
    updated_at: datetime


class ChartOfAccountTree(ChartOfAccountRead):
    children: list["ChartOfAccountTree"] = Field(default_factory=list)


class ChartOfAccountLookup(BaseModel):
    id: int
    account_code: str
    account_name: str
    account_type: AccountType
    normal_balance: NormalBalance
    is_posting: bool
    is_active: bool
    account_subtype: AccountSubtype
    cash_flow_category: CashFlowCategory | None = None
    financial_statement_group: FinancialStatementGroup | None = None


class ChartOfAccountPage(BaseModel):
    items: list[ChartOfAccountRead]
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool

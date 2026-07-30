from pydantic import BaseModel, Field


class ChartOfAccountCreate(BaseModel):
    account_number: str = Field(min_length=1, max_length=30)
    account_name: str = Field(min_length=1, max_length=150)
    account_type: str = Field(min_length=1, max_length=30)
    cash_flow_category: str | None = None
    parent_account_id: int | None = None
    is_posting: bool = True
    is_active: bool = True


class ChartOfAccountUpdate(BaseModel):
    account_name: str | None = None
    account_type: str | None = None
    cash_flow_category: str | None = None
    parent_account_id: int | None = None
    is_posting: bool | None = None
    is_active: bool | None = None

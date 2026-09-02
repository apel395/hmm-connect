from datetime import datetime

from pydantic import BaseModel, Field


class FiscalAccountBase(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=250)
    category: str = Field(min_length=1, max_length=60)
    parent_code: str | None = Field(default=None, max_length=20)
    is_header: bool = False
    is_active: bool = True


class FiscalAccountCreate(FiscalAccountBase):
    sort_order: int = 0


class FiscalAccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=250)
    category: str | None = Field(default=None, min_length=1, max_length=60)
    parent_code: str | None = Field(default=None, max_length=20)
    is_header: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class FiscalAccountRead(FiscalAccountBase):
    id: int
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FiscalAccountPage(BaseModel):
    items: list[FiscalAccountRead]
    total: int
    page: int
    page_size: int
    pages: int


class FiscalMappingRead(BaseModel):
    id: int
    fiscal_account_id: int
    fiscal_code: str
    fiscal_name: str
    commercial_account_id: int
    commercial_code: str
    commercial_name: str

    model_config = {"from_attributes": True}


class FiscalMappingCreate(BaseModel):
    fiscal_account_id: int
    commercial_account_id: int


class FiscalMappingPage(BaseModel):
    items: list[FiscalMappingRead]
    total: int
    page: int
    page_size: int
    pages: int
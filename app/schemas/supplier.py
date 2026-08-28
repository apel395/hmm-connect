from pydantic import BaseModel, Field


class SupplierCreate(BaseModel):
    code: str
    name: str
    address: str | None = None
    bank_name: str | None = None
    bank_account_number: str | None = None
    bank_account_name: str | None = None
    is_pkp: bool = False
    npwp: str | None = Field(default=None, max_length=32)
    nitku: str | None = Field(default=None, max_length=32)
    tax_registration_name: str | None = Field(default=None, max_length=150)
    payable_account_id: int | None = None
    is_active: bool = True


class SupplierUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    bank_name: str | None = None
    bank_account_number: str | None = None
    bank_account_name: str | None = None
    is_pkp: bool | None = None
    npwp: str | None = Field(default=None, max_length=32)
    nitku: str | None = Field(default=None, max_length=32)
    tax_registration_name: str | None = Field(default=None, max_length=150)
    payable_account_id: int | None = None
    is_active: bool | None = None

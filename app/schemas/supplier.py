from pydantic import BaseModel


class SupplierCreate(BaseModel):
    code: str
    name: str
    address: str | None = None
    bank_name: str | None = None
    bank_account_number: str | None = None
    bank_account_name: str | None = None
    is_active: bool = True


class SupplierUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    bank_name: str | None = None
    bank_account_number: str | None = None
    bank_account_name: str | None = None
    is_active: bool | None = None

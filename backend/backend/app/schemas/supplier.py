from pydantic import BaseModel, Field


class SupplierRowCreate(BaseModel):
    pic_name: str | None = None
    phone: str | None = None
    unit: str | None = None
    item: str | None = None


class SupplierRowResponse(SupplierRowCreate):
    id: int

    class Config:
        from_attributes = True


class SupplierUpdate(BaseModel):
    code: str
    name: str
    address: str | None = None
    bank_name: str | None = None
    bank_account_number: str | None = None
    bank_account_name: str | None = None
    rows: list[SupplierRowCreate] = Field(
        default_factory=list,
    )


class SupplierCreate(BaseModel):
    code: str
    name: str
    address: str | None = None
    bank_name: str | None = None
    bank_account_number: str | None = None
    bank_account_name: str | None = None
    rows: list[SupplierRowCreate] = Field(
        default_factory=list,
    )


class SupplierResponse(BaseModel):
    id: int
    code: str
    name: str
    address: str | None
    bank_name: str | None
    bank_account_number: str | None
    bank_account_name: str | None
    is_active: bool
    rows: list[SupplierRowResponse] = Field(
        default_factory=list,
    )

    class Config:
        from_attributes = True

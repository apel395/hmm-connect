from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class JournalLineCreate(BaseModel):
    business_unit_id: int | None = None
    account_id: int
    debit: Decimal = Field(default=Decimal("0"))
    credit: Decimal = Field(default=Decimal("0"))
    description: str | None = None
    department_id: int | None = None
    location_id: int | None = None
    supplier_id: int | None = None


class JournalCreate(BaseModel):
    business_unit_id: int | None = None
    location_id: int | None = None
    department_id: int | None = None
    posting_date: date
    document_type: str
    document_number: str

    reference_type: str
    reference_id: int

    description: str | None = None

    lines: list[JournalLineCreate]


class JournalLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    debit: Decimal
    credit: Decimal
    description: str | None


class JournalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    journal_number: str
    posting_date: date
    status: str

    lines: list[JournalLineResponse]


class JournalBulkAction(BaseModel):
    journal_ids: list[int] = Field(min_length=1, max_length=100)


class JournalUpdate(BaseModel):
    posting_date: date | None = None
    location_id: int | None = None
    description: str | None = None
    lines: list[JournalLineCreate] | None = None

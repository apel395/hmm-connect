from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class JournalLineCreate(BaseModel):
    account_id: int
    debit: Decimal = Field(default=Decimal("0"))
    credit: Decimal = Field(default=Decimal("0"))
    description: str | None = None


class JournalCreate(BaseModel):
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

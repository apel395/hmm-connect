from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class JournalVoucherLineCreate(BaseModel):

    account_id: int

    debit: Decimal = 0

    credit: Decimal = 0

    description: str | None = None


class JournalVoucherCreate(BaseModel):

    voucher_date: date

    description: str

    lines: list[JournalVoucherLineCreate]

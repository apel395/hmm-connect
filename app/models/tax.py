from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CompanyTaxProfile(Base, TimestampMixin):
    """Annual company tax identity used to populate the SPT 1771 header.

    One row per tax year (the Indonesian tax year is the calendar year).
    """

    __tablename__ = "company_tax_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    tax_year: Mapped[int] = mapped_column(
        nullable=False, unique=True, index=True
    )
    npwp: Mapped[str | None] = mapped_column(String(32), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(250), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    klu: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    representative_name: Mapped[str | None] = mapped_column(String(150), nullable=True)


class TaxCredit(Base, TimestampMixin):
    """Prepaid corporate income tax credits applied on the SPT 1771.

    In Indonesian withholding-tax terminology these are the PPh credits that
    reduce the annual PPh terutang: PPh 25 installments (angsuran), PPh 22
    (importer/procurer withholding), PPh 23 (service withholding), PPh 24
    (foreign tax credit), and PPh 22 import self-withholding.
    """

    __tablename__ = "tax_credits"

    CREDIT_TYPES = ("PPh 22", "PPh 23", "PPh 24", "PPh 25", "OTHER")

    id: Mapped[int] = mapped_column(primary_key=True)
    tax_year: Mapped[int] = mapped_column(nullable=False, index=True)
    credit_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(String(250), nullable=True)
    counterparty_npwp: Mapped[str | None] = mapped_column(String(32), nullable=True)
    counterparty_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

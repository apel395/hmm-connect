from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AccountReceivable(Base, TimestampMixin):

    __tablename__ = "account_receivables"

    id: Mapped[int] = mapped_column(primary_key=True)

    source_sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales_transactions.id", ondelete="RESTRICT"), unique=True, nullable=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("chart_of_accounts.id", ondelete="RESTRICT"), nullable=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True)
    business_unit_id: Mapped[int | None] = mapped_column(ForeignKey("business_units.id", ondelete="RESTRICT"), nullable=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True)

    invoice_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"),
    )

    invoice_date: Mapped[date] = mapped_column(
        Date,
    )

    due_date: Mapped[date] = mapped_column(
        Date,
    )

    amount: Mapped[float] = mapped_column(
        Numeric(18,2),
    )

    received_amount: Mapped[float] = mapped_column(
        Numeric(18,2),
        default=0,
    )

    outstanding_amount: Mapped[float] = mapped_column(
        Numeric(18,2),
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="UNPAID",
    )

    customer = relationship(
        "Customer",
        back_populates="account_receivables",
    )

from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class CustomerPayment(Base, TimestampMixin):

    __tablename__ = "customer_payments"

    id: Mapped[int] = mapped_column(primary_key=True)

    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=True)
    cash_account_id: Mapped[int | None] = mapped_column(ForeignKey("chart_of_accounts.id", ondelete="RESTRICT"), nullable=True)
    request_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    payment_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
    )

    account_receivable_id: Mapped[int] = mapped_column(
        ForeignKey("account_receivables.id"),
    )

    payment_date: Mapped[date] = mapped_column(
        Date,
    )

    amount: Mapped[float] = mapped_column(
        Numeric(18, 2),
    )

    payment_method: Mapped[str] = mapped_column(
        String(30),
    )

    reference_number: Mapped[str | None] = mapped_column(
        String(100),
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="POSTED",
    )

    account_receivable = relationship(
        "AccountReceivable",
    )

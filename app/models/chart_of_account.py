from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ChartOfAccount(Base, TimestampMixin):
    __tablename__ = "chart_of_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)

    account_number: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        index=True,
    )

    account_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    account_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    normal_balance: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    cash_flow_category: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    parent_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("chart_of_accounts.id"),
        nullable=True,
        index=True,
    )

    is_posting: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    parent = relationship(
        "ChartOfAccount",
        remote_side=[id],
        back_populates="children",
    )

    children = relationship(
        "ChartOfAccount",
        back_populates="parent",
    )

    account_receipts = relationship(
        "AccountReceipt",
        back_populates="account",
    )

    general_ledger_entries = relationship(
        "GeneralLedger",
        back_populates="account",
    )

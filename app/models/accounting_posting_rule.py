from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class AccountingPostingRule(Base, TimestampMixin):
    __tablename__ = "accounting_posting_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    debit_account_id: Mapped[int] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=False)
    credit_account_id: Mapped[int] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=False)
    input_vat_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("chart_of_accounts.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    debit_account = relationship("ChartOfAccount", foreign_keys=[debit_account_id])
    credit_account = relationship("ChartOfAccount", foreign_keys=[credit_account_id])
    input_vat_account = relationship("ChartOfAccount", foreign_keys=[input_vat_account_id])
    created_by = relationship("User")

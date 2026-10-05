from sqlalchemy import Boolean, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class FinancialReportSetting(Base, TimestampMixin):
    __tablename__ = "financial_report_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_type: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    selected_account_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    header_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

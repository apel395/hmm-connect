from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class StockReconciliationRequest(Base):
    __tablename__ = "stock_reconciliation_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)
    requested_qty: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    variance_qty: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    product = relationship("Product")
    warehouse = relationship("Warehouse")
    created_by = relationship("User")

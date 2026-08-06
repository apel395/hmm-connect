from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Table, Text, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


purchase_order_requisition_table = Table(
    "purchase_order_requisitions",
    Base.metadata,
    Column(
        "purchase_order_id",
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "purchase_requisition_id",
        ForeignKey("purchase_requisitions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class PurchaseOrder(Base, TimestampMixin):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    po_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True)
    business_unit_id: Mapped[int | None] = mapped_column(ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True, index=True)

    purchase_requisition_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_requisitions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    order_date: Mapped[date] = mapped_column(Date, default=date.today)
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(30), default="LIVE", nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="IDR", nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    imported_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    supplier = relationship("Supplier", back_populates="purchase_orders")
    department = relationship("Department")
    location = relationship("Location")

    purchase_requisition = relationship(
        "PurchaseRequisition",
        back_populates="legacy_purchase_orders",
        foreign_keys=[purchase_requisition_id],
    )

    purchase_requisitions = relationship(
        "PurchaseRequisition",
        secondary=purchase_order_requisition_table,
        back_populates="purchase_orders",
    )

    items = relationship(
        "PurchaseOrderItem",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
    )

    goods_receipts = relationship(
        "GoodsReceipt",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
    )

    @property
    def purchase_requisition_ids(self) -> list[int]:
        ids = [pr.id for pr in self.purchase_requisitions]
        if self.purchase_requisition_id and self.purchase_requisition_id not in ids:
            ids.append(self.purchase_requisition_id)
        return ids

    @property
    def source_purchase_requisitions(self):
        requisitions = list(self.purchase_requisitions)
        if self.purchase_requisition and all(
            item.id != self.purchase_requisition.id for item in requisitions
        ):
            requisitions.append(self.purchase_requisition)
        return requisitions

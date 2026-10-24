from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class SalesTransaction(Base, TimestampMixin):
    __tablename__ = "sales_transactions"

    __table_args__ = (Index('uq_pos_active_table', 'pos_table_id', unique=True,
        postgresql_where=text("status = 'DRAFT' AND pos_table_id IS NOT NULL"), sqlite_where=text("status = 'DRAFT' AND pos_table_id IS NOT NULL")),)
    pos_table_id: Mapped[int | None] = mapped_column(ForeignKey('pos_tables.id', ondelete='RESTRICT'), nullable=True)
    cashier_session_id: Mapped[int | None] = mapped_column(ForeignKey('pos_cashier_sessions.id', ondelete='RESTRICT'), nullable=True, index=True)
    order_mode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    event_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    order_request_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    transaction_type: Mapped[str] = mapped_column(String(20), default="POS", nullable=False, index=True)
    table_number: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    queue_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False, index=True)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    warehouse_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    business_unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("business_units.id", ondelete="RESTRICT"), nullable=True
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
    )
    revenue_account_id: Mapped[int | None] = mapped_column(ForeignKey("chart_of_accounts.id", ondelete="RESTRICT"), nullable=True)
    invoice_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    receivable_account_id: Mapped[int | None] = mapped_column(ForeignKey("chart_of_accounts.id", ondelete="RESTRICT"), nullable=True)
    ar_correction_journal_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    payment_received: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    change_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    service_charge_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    journal_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True, index=True
    )

    warehouse = relationship("Warehouse")
    location = relationship("Location")
    customer = relationship("Customer")
    created_by = relationship("User", foreign_keys=[created_by_id])
    posted_by = relationship("User", foreign_keys=[posted_by_id])
    voided_by = relationship("User", foreign_keys=[voided_by_id])
    journal_entry = relationship("JournalEntry", foreign_keys=[journal_entry_id])
    lines = relationship(
        "SalesTransactionLine",
        back_populates="transaction",
        cascade="all, delete-orphan",
        order_by="SalesTransactionLine.line_number",
    )


class SalesTransactionLine(Base):
    __tablename__ = "sales_transaction_lines"
    __table_args__ = (
        UniqueConstraint(
            "sales_transaction_id", "product_id", name="uq_sales_transaction_product"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sales_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("sales_transactions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    service_charge_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0, nullable=False)
    tax_type: Mapped[str] = mapped_column(String(20), default="LEGACY", server_default="LEGACY", nullable=False)
    tax_account_id: Mapped[int | None] = mapped_column(ForeignKey("chart_of_accounts.id", ondelete="RESTRICT"), nullable=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0, nullable=False)
    service_charge_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    line_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    uom: Mapped[str] = mapped_column(String(30), default="", nullable=False)

    transaction = relationship("SalesTransaction", back_populates="lines")
    product = relationship("Product")

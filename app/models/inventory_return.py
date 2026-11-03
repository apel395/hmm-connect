from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class InventoryReturn(Base, TimestampMixin):
    __tablename__ = 'inventory_returns'
    __table_args__ = (CheckConstraint("purpose IN ('REPLACEMENT','AP_CREDIT')", name='ck_return_purpose'), CheckConstraint("status IN ('DRAFT','POSTED','VOID')", name='ck_return_status'))
    id: Mapped[int] = mapped_column(primary_key=True)
    request_key: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    goods_receipt_id: Mapped[int] = mapped_column(ForeignKey('goods_receipts.id'), index=True)
    purpose: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default='DRAFT')
    return_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)
    clearing_account_id: Mapped[int] = mapped_column(ForeignKey('chart_of_accounts.id'))
    created_by_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey('journal_entries.id'))
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    credit_date: Mapped[date | None] = mapped_column(Date)
    credit_reference: Mapped[str | None] = mapped_column(String(150))
    credit_net: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    credit_tax: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    credit_applied: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    supplier_credit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    supplier_credit_account_id: Mapped[int | None] = mapped_column(ForeignKey('chart_of_accounts.id'))
    supplier_invoice_id: Mapped[int | None] = mapped_column(ForeignKey('supplier_invoices.id'), index=True)
    supplier_adjustment_id: Mapped[int | None] = mapped_column(ForeignKey('supplier_adjustments.id'), unique=True)
    credit_journal_id: Mapped[int | None] = mapped_column(ForeignKey('journal_entries.id'))
    receipt = relationship('GoodsReceipt', foreign_keys=[goods_receipt_id])
    items = relationship('InventoryReturnItem', back_populates='document', cascade='all, delete-orphan')


class InventoryReturnItem(Base):
    __tablename__ = 'inventory_return_items'
    __table_args__ = (UniqueConstraint('return_id', 'goods_receipt_item_id', name='uq_return_receipt_line'), CheckConstraint('quantity > 0', name='ck_return_positive_quantity'))
    id: Mapped[int] = mapped_column(primary_key=True)
    return_id: Mapped[int] = mapped_column(ForeignKey('inventory_returns.id'), index=True)
    goods_receipt_item_id: Mapped[int] = mapped_column(ForeignKey('goods_receipt_items.id'), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    uom: Mapped[str] = mapped_column(String(30))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    line_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    inventory_account_id: Mapped[int | None] = mapped_column(ForeignKey('chart_of_accounts.id'))
    document = relationship('InventoryReturn', back_populates='items')
    receipt_item = relationship('GoodsReceiptItem')


class InventoryReplacement(Base):
    __tablename__ = 'inventory_return_replacements'
    __table_args__ = (CheckConstraint('quantity > 0', name='ck_replacement_positive_quantity'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    return_item_id: Mapped[int] = mapped_column(ForeignKey('inventory_return_items.id'), index=True)
    goods_receipt_item_id: Mapped[int] = mapped_column(ForeignKey('goods_receipt_items.id'), unique=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    return_item = relationship('InventoryReturnItem')
    receipt_item = relationship('GoodsReceiptItem')

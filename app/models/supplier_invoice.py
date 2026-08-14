from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, event
from sqlalchemy.orm import Mapped, Session as OrmSession, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class SupplierInvoice(Base, TimestampMixin):
    __tablename__ = "supplier_invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    internal_invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    supplier_invoice_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    received_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    tax_invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    tax_invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    purchase_order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id", ondelete="SET NULL"), index=True)
    goods_receipt_id: Mapped[int | None] = mapped_column(ForeignKey("goods_receipts.id", ondelete="SET NULL"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"))
    business_unit_id: Mapped[int | None] = mapped_column(ForeignKey("business_units.id", ondelete="SET NULL"), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="IDR", nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18,2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18,2), default=0, nullable=False)
    withholding_tax_amount: Mapped[Decimal] = mapped_column(Numeric(18,2), default=0, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(18,2), default=0, nullable=False)
    adjustment_amount: Mapped[Decimal] = mapped_column(Numeric(18,2), default=0, nullable=False)
    balance_amount: Mapped[Decimal] = mapped_column(Numeric(18,2), default=0, nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), default="UNPAID", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(30), default="LIVE", nullable=False, index=True)
    external_reference: Mapped[str | None] = mapped_column(String(100))
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    imported_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supplier = relationship("Supplier"); purchase_order = relationship("PurchaseOrder"); goods_receipt = relationship("GoodsReceipt")
    department = relationship("Department"); location = relationship("Location"); created_by = relationship("User", foreign_keys=[created_by_id])
    lines = relationship("SupplierInvoiceLine", back_populates="invoice", cascade="all, delete-orphan")


class SupplierInvoiceLine(Base):
    __tablename__ = "supplier_invoice_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_invoice_id: Mapped[int] = mapped_column(ForeignKey("supplier_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    purchase_order_item_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_order_items.id", ondelete="SET NULL"))
    goods_receipt_item_id: Mapped[int | None] = mapped_column(ForeignKey("goods_receipt_items.id", ondelete="SET NULL"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18,4), nullable=False)
    uom: Mapped[str | None] = mapped_column(String(20))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    line_amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    is_taxable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5,2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18,2), default=0, nullable=False)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("chart_of_accounts.id"))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)
    invoice = relationship("SupplierInvoice", back_populates="lines"); product = relationship("Product"); account = relationship("ChartOfAccount")


@event.listens_for(OrmSession, "before_flush")
def _sync_supplier_invoice_balance(session, _flush_context, _instances):
    candidates = set(session.new).union(session.dirty)
    for invoice in candidates:
        if not isinstance(invoice, SupplierInvoice):
            continue

        total = Decimal(invoice.total_amount or 0)
        paid = Decimal(invoice.paid_amount or 0)
        adjustments = Decimal(invoice.adjustment_amount or 0)
        balance = max(Decimal("0"), total - paid - adjustments)
        invoice.balance_amount = balance
        if balance == 0 and total > 0:
            invoice.payment_status = "PAID"
        elif paid > 0 or adjustments > 0:
            invoice.payment_status = "PARTIALLY_PAID"
        else:
            invoice.payment_status = "UNPAID"

        if str(invoice.status or "").upper() == "VERIFIED" and Decimal(invoice.tax_amount or 0) > 0:
            supplier = invoice.supplier
            if supplier and not supplier.is_pkp:
                raise HTTPException(
                    status_code=409,
                    detail="Supplier invoice contains PPN but supplier is not marked as PKP",
                )
            if not invoice.tax_invoice_number or not invoice.tax_invoice_date:
                raise HTTPException(
                    status_code=409,
                    detail="Tax invoice number and tax invoice date are required before verifying an invoice with PPN",
                )

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, event
from sqlalchemy.orm import Mapped, Session as OrmSession, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150))
    group_code: Mapped[str] = mapped_column(String(10))
    group_name: Mapped[str] = mapped_column(String(50))
    subgroup_code: Mapped[str] = mapped_column(String(10))
    subgroup_name: Mapped[str] = mapped_column(String(100))
    uom: Mapped[str] = mapped_column(String(20))
    usage_uom: Mapped[str] = mapped_column(String(20))
    conversion: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=1)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    tax_category: Mapped[str] = mapped_column(String(30), default="REVIEW_REQUIRED", nullable=False)
    is_taxable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0, nullable=False)
    tax_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)

    minimum_stock: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    reorder_level: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    maximum_stock: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    preferred_supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    inventory_account_id: Mapped[int | None] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=True)
    purchase_account_id: Mapped[int | None] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=True)
    cogs_account_id: Mapped[int | None] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    inventory = relationship("Inventory", back_populates="product", cascade="all, delete-orphan")
    suppliers = relationship("SupplierProduct", back_populates="product", cascade="all, delete-orphan")


ZERO = Decimal("0")
HUNDRED = Decimal("100")


def _tax_amount(amount, taxable, rate):
    amount = Decimal(amount or 0)
    rate = Decimal(rate or 0)
    return (amount * rate / HUNDRED) if taxable and rate > 0 else ZERO


def _copy_tax(target, source, base_amount):
    target.is_taxable = bool(getattr(source, "is_taxable", False))
    target.tax_rate = Decimal(getattr(source, "tax_rate", 0) or 0) if target.is_taxable else ZERO
    target.tax_amount = _tax_amount(base_amount, target.is_taxable, target.tax_rate)


@event.listens_for(OrmSession, "before_flush")
def _sync_purchasing_tax_snapshots(session, _flush_context, _instances):
    """Keep item-master tax treatment authoritative while preserving document snapshots."""
    from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
    from app.models.purchase_order import PurchaseOrder
    from app.models.purchase_order_item import PurchaseOrderItem
    from app.models.purchase_requisition import PurchaseRequisition
    from app.models.purchase_requisition_item import PurchaseRequisitionItem
    from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine

    candidates = set(session.new).union(session.dirty)

    for row in candidates:
        if isinstance(row, PurchaseRequisitionItem):
            product = row.product or session.get(Product, row.product_id)
            if product:
                _copy_tax(row, product, Decimal(row.quantity or 0) * Decimal(row.estimated_price or 0))
                row.total_price = Decimal(row.quantity or 0) * Decimal(row.estimated_price or 0)

        elif isinstance(row, PurchaseOrderItem):
            source = None
            if row.purchase_requisition_item_id:
                source = session.get(PurchaseRequisitionItem, row.purchase_requisition_item_id)
            if source is None:
                source = row.product or session.get(Product, row.product_id)
            if source:
                _copy_tax(row, source, Decimal(row.quantity or 0) * Decimal(row.unit_price or 0))
                row.total_price = Decimal(row.quantity or 0) * Decimal(row.unit_price or 0)

        elif isinstance(row, GoodsReceiptItem):
            source = None
            if row.purchase_order_item_id:
                source = session.get(PurchaseOrderItem, row.purchase_order_item_id)
            if source is None:
                source = row.product or session.get(Product, row.product_id)
            if source:
                _copy_tax(row, source, Decimal(row.quantity or 0) * Decimal(row.unit_cost or 0))

        elif isinstance(row, SupplierInvoiceLine):
            source = None
            if row.goods_receipt_item_id:
                source = session.get(GoodsReceiptItem, row.goods_receipt_item_id)
            elif row.purchase_order_item_id:
                source = session.get(PurchaseOrderItem, row.purchase_order_item_id)
            if source is None and row.product_id:
                source = session.get(Product, row.product_id)
            if source:
                _copy_tax(row, source, Decimal(row.quantity or 0) * Decimal(row.unit_price or 0))
            row.line_amount = Decimal(row.quantity or 0) * Decimal(row.unit_price or 0)

    headers = set()
    for row in candidates:
        if isinstance(row, PurchaseRequisition): headers.add(row)
        elif isinstance(row, PurchaseRequisitionItem) and row.purchase_requisition: headers.add(row.purchase_requisition)
        elif isinstance(row, PurchaseOrder): headers.add(row)
        elif isinstance(row, PurchaseOrderItem) and row.purchase_order: headers.add(row.purchase_order)
        elif isinstance(row, GoodsReceipt): headers.add(row)
        elif isinstance(row, GoodsReceiptItem) and row.goods_receipt: headers.add(row.goods_receipt)
        elif isinstance(row, SupplierInvoice): headers.add(row)
        elif isinstance(row, SupplierInvoiceLine) and row.invoice: headers.add(row.invoice)

    for header in headers:
        if isinstance(header, PurchaseRequisition):
            header.subtotal = sum((Decimal(i.quantity or 0) * Decimal(i.estimated_price or 0) for i in header.items), ZERO)
            header.tax_amount = sum((Decimal(i.tax_amount or 0) for i in header.items), ZERO)
            header.total_amount = header.subtotal + header.tax_amount
        elif isinstance(header, PurchaseOrder):
            header.subtotal = sum((Decimal(i.quantity or 0) * Decimal(i.unit_price or 0) for i in header.items), ZERO)
            header.tax_amount = sum((Decimal(i.tax_amount or 0) for i in header.items), ZERO)
            header.total_amount = header.subtotal - Decimal(header.discount_amount or 0) + header.tax_amount
        elif isinstance(header, GoodsReceipt):
            header.subtotal = sum((Decimal(i.quantity or 0) * Decimal(i.unit_cost or 0) for i in header.items), ZERO)
            header.tax_amount = sum((Decimal(i.tax_amount or 0) for i in header.items), ZERO)
            header.total_amount = header.subtotal + header.tax_amount
        elif isinstance(header, SupplierInvoice):
            header.subtotal = sum((Decimal(i.quantity or 0) * Decimal(i.unit_price or 0) for i in header.lines), ZERO)
            header.tax_amount = sum((Decimal(i.tax_amount or 0) for i in header.lines), ZERO)
            header.total_amount = header.subtotal - Decimal(header.discount_amount or 0) + header.tax_amount - Decimal(header.withholding_tax_amount or 0)

    # Unknown tax treatment must be reviewed before operational approval/posting.
    for header in headers:
        status = str(getattr(header, "status", "") or "").upper()
        locked_statuses = {"PENDING_APPROVAL", "APPROVED", "POSTED", "VERIFIED", "RECEIVED", "PARTIALLY_RECEIVED"}
        if status not in locked_statuses:
            continue
        products = []
        if isinstance(header, PurchaseRequisition): products = [i.product for i in header.items]
        elif isinstance(header, PurchaseOrder): products = [i.product for i in header.items]
        elif isinstance(header, GoodsReceipt): products = [i.product for i in header.items]
        elif isinstance(header, SupplierInvoice): products = [i.product for i in header.lines if i.product]
        unresolved = [p for p in products if p and p.tax_category == "REVIEW_REQUIRED"]
        if unresolved:
            names = ", ".join(p.name for p in unresolved[:5])
            raise ValueError(f"Tax review required before document can continue: {names}")

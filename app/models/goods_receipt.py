from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, event, func, text
from sqlalchemy.orm import Mapped, Session as OrmSession, mapped_column, relationship

from app.models.base import Base


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    purchase_order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id"), nullable=True, index=True)
    market_list_id: Mapped[int | None] = mapped_column(ForeignKey("market_lists.id"), nullable=True, index=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True)
    received_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    destination_type: Mapped[str] = mapped_column(String(30), default="INVENTORY", nullable=False)
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True, index=True)
    business_unit_id: Mapped[int | None] = mapped_column(ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True, index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(30), default="LIVE", nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_note_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    receipt_type: Mapped[str] = mapped_column(String(30), default="GOODS", nullable=False)
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    imported_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    purchase_order = relationship("PurchaseOrder", back_populates="goods_receipts")
    market_list = relationship("MarketList")
    supplier = relationship("Supplier")
    received_by = relationship("User", foreign_keys=[received_by_id])
    warehouse = relationship("Warehouse")
    business_unit = relationship("BusinessUnit")
    department = relationship("Department")
    location = relationship("Location")
    items = relationship("GoodsReceiptItem", back_populates="goods_receipt", cascade="all, delete-orphan")


class GoodsReceiptItem(Base):
    __tablename__ = "goods_receipt_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    goods_receipt_id: Mapped[int] = mapped_column(ForeignKey("goods_receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    purchase_order_item_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_order_items.id"), nullable=True)
    market_list_item_id: Mapped[int | None] = mapped_column(ForeignKey("market_list_items.id"), nullable=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    expense_account_id: Mapped[int | None] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=True)
    destination_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    destination_override_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_taxable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)

    goods_receipt = relationship("GoodsReceipt", back_populates="items")
    purchase_order_item = relationship("PurchaseOrderItem", back_populates="goods_receipt_items")
    product = relationship("Product")


@event.listens_for(OrmSession, "before_flush")
def _inherit_po_receiving_dimensions(session, _flush_context, _instances):
    """Make the source PO authoritative for organization dimensions on PO receipts.

    A client payload must never be able to move a PO-based receipt to another
    Business Unit, Location, or Department. Direct receipts are unaffected.
    """
    from app.models.purchase_order import PurchaseOrder

    candidates = set(session.new).union(session.dirty)
    for receipt in candidates:
        if not isinstance(receipt, GoodsReceipt) or receipt.purchase_order_id is None:
            continue

        purchase_order = receipt.purchase_order or session.get(PurchaseOrder, receipt.purchase_order_id)
        if purchase_order is None:
            raise HTTPException(status_code=404, detail="Purchase order not found")

        receipt.business_unit_id = purchase_order.business_unit_id
        receipt.location_id = purchase_order.location_id
        receipt.department_id = purchase_order.department_id


@event.listens_for(OrmSession, "before_flush")
def _prevent_duplicate_po_receiving_drafts(session, _flush_context, _instances):
    """Allow at most one active DRAFT receiving report per PO.

    PostgreSQL advisory transaction locks serialize concurrent double-click/API
    requests for the same PO. The second request waits for the first transaction
    and then receives a clean 409 instead of inserting a duplicate draft.
    """
    candidates = [
        row for row in session.new
        if isinstance(row, GoodsReceipt)
        and row.purchase_order_id is not None
        and str(row.status or "DRAFT").upper() == "DRAFT"
    ]
    if not candidates:
        return

    seen_po_ids: set[int] = set()
    for receipt in candidates:
        po_id = int(receipt.purchase_order_id)
        if po_id in seen_po_ids:
            raise HTTPException(
                status_code=409,
                detail=f"Only one receiving draft can be created for purchase order {po_id} at a time",
            )
        seen_po_ids.add(po_id)

        bind = session.get_bind()
        if bind.dialect.name == "postgresql":
            # Namespace 484d4d (HMM) keeps this application lock distinct from
            # unrelated advisory locks while remaining deterministic per PO.
            session.execute(
                text("SELECT pg_advisory_xact_lock(:namespace, :po_id)"),
                {"namespace": 4742477, "po_id": po_id},
            )

        existing = (
            session.query(GoodsReceipt)
            .filter(
                GoodsReceipt.purchase_order_id == po_id,
                GoodsReceipt.status == "DRAFT",
            )
            .order_by(GoodsReceipt.id.desc())
            .first()
        )
        if existing:
            po_number = existing.purchase_order.po_number if existing.purchase_order else f"PO #{po_id}"
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Receiving draft {existing.receipt_number} already exists for {po_number}. "
                    "Open the existing draft instead of creating another one."
                ),
            )

"""Purchasing insights from posted receiving lines (net of draft/void documents)."""
from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from math import ceil

from sqlalchemy import distinct, func, or_
from sqlalchemy.orm import Session

from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from app.services.location_access import apply_location_scope


class PurchasingInsightsService:
    def __init__(self, db: Session, user):
        self.db = db
        self.user = user

    def _lines(self):
        query = (
            self.db.query(GoodsReceiptItem)
            .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptItem.goods_receipt_id)
            .filter(GoodsReceipt.status == "POSTED")
        )
        return apply_location_scope(query, GoodsReceipt.location_id, self.user)

    @staticmethod
    def _start(day: date) -> datetime:
        return datetime.combine(day, time.min, timezone.utc)

    def rankings(self, *, year: int, month: int, limit: int = 5) -> dict:
        first = date(year, month, 1)
        last = date(year, month, monthrange(year, month)[1])
        lines = self._lines().filter(
            GoodsReceipt.received_at >= self._start(first),
            GoodsReceipt.received_at < self._start(last + timedelta(days=1)),
        )
        value = GoodsReceiptItem.quantity * GoodsReceiptItem.unit_cost
        products = (
            lines.join(Product, Product.id == GoodsReceiptItem.product_id)
            .with_entities(
                Product.id, Product.code, Product.name, Product.uom,
                func.coalesce(func.sum(GoodsReceiptItem.quantity), 0).label("quantity"),
                func.coalesce(func.sum(value), 0).label("received_value"),
                func.count(distinct(GoodsReceipt.id)).label("receipt_count"),
            )
            .group_by(Product.id, Product.code, Product.name, Product.uom)
        )
        suppliers = (
            lines.outerjoin(Supplier, Supplier.id == GoodsReceipt.supplier_id)
            .with_entities(
                Supplier.id, Supplier.code, Supplier.name,
                func.count(distinct(GoodsReceipt.id)).label("receipt_count"),
                func.coalesce(func.sum(value), 0).label("received_value"),
            )
            .group_by(Supplier.id, Supplier.code, Supplier.name)
        )

        def product_row(row):
            return {
                "product_id": row.id, "product_code": row.code,
                "product_name": row.name, "uom": row.uom,
                "quantity": row.quantity, "received_value": row.received_value,
                "receipt_count": row.receipt_count,
            }

        def supplier_row(row):
            return {
                "supplier_id": row.id, "supplier_code": row.code,
                "supplier_name": row.name or "Unassigned supplier",
                "receipt_count": row.receipt_count,
                "received_value": row.received_value,
            }

        return {
            "year": year, "month": month,
            "date_from": first, "date_to": last,
            "source": "POSTED_GOODS_RECEIPT",
            "cost_basis": "EXCLUDING_TAX",
            "top_items_by_quantity": [
                product_row(row) for row in products.order_by(
                    func.sum(GoodsReceiptItem.quantity).desc(), Product.code
                ).limit(limit).all()
            ],
            "top_items_by_cost": [
                product_row(row) for row in products.order_by(
                    func.sum(value).desc(), Product.code
                ).limit(limit).all()
            ],
            "top_suppliers_by_receipts": [
                supplier_row(row) for row in suppliers.order_by(
                    func.count(distinct(GoodsReceipt.id)).desc(), Supplier.name
                ).limit(limit).all()
            ],
            "top_suppliers_by_cost": [
                supplier_row(row) for row in suppliers.order_by(
                    func.sum(value).desc(), Supplier.name
                ).limit(limit).all()
            ],
        }

    def price_history(
        self, *, product_id: int | None = None, supplier_id: int | None = None,
        search: str | None = None, date_from: date | None = None,
        date_to: date | None = None, page: int = 1, page_size: int = 50,
    ) -> dict:
        query = (
            self._lines()
            .join(Product, Product.id == GoodsReceiptItem.product_id)
            .outerjoin(Supplier, Supplier.id == GoodsReceipt.supplier_id)
            .outerjoin(PurchaseOrder, PurchaseOrder.id == GoodsReceipt.purchase_order_id)
        )
        if product_id:
            query = query.filter(GoodsReceiptItem.product_id == product_id)
        if supplier_id:
            query = query.filter(GoodsReceipt.supplier_id == supplier_id)
        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.filter(or_(
                Product.code.ilike(term), Product.name.ilike(term),
                Supplier.name.ilike(term), GoodsReceipt.receipt_number.ilike(term),
            ))
        if date_from:
            query = query.filter(GoodsReceipt.received_at >= self._start(date_from))
        if date_to:
            query = query.filter(
                GoodsReceipt.received_at < self._start(date_to + timedelta(days=1))
            )
        total = query.count()
        rows = query.with_entities(
            GoodsReceiptItem, GoodsReceipt, Product, Supplier, PurchaseOrder
        ).order_by(
            GoodsReceipt.received_at.desc(), GoodsReceiptItem.id.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()
        return {
            "items": [
                {
                    "receipt_item_id": item.id, "receipt_id": receipt.id,
                    "receipt_number": receipt.receipt_number,
                    "received_at": receipt.received_at,
                    "purchase_order_id": order.id if order else None,
                    "purchase_order_number": order.po_number if order else None,
                    "supplier_id": supplier.id if supplier else None,
                    "supplier_name": supplier.name if supplier else "Unassigned supplier",
                    "product_id": product.id, "product_code": product.code,
                    "product_name": product.name, "uom": product.uom,
                    "quantity": item.quantity, "unit_cost": item.unit_cost,
                    "line_value": Decimal(item.quantity or 0) * Decimal(item.unit_cost or 0),
                }
                for item, receipt, product, supplier, order in rows
            ],
            "page": page, "page_size": page_size, "total_items": total,
            "total_pages": ceil(total / page_size) if total else 0,
            "has_next": page * page_size < total, "has_previous": page > 1,
            "cost_basis": "EXCLUDING_TAX",
        }

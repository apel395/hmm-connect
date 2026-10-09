"""Read-only purchase reference costs; never write inventory valuation or journals."""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy import func
from app.models.product import Product
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.location import Location
from app.services.location_access import assigned_location_id, apply_location_scope


def purchasing_unit(db, user, requested=None):
    location_id = assigned_location_id(user)
    if location_id:
        location = db.get(Location, location_id)
        unit_id = location.business_unit_id if location else None
        if requested is not None and requested != unit_id:
            raise HTTPException(403, "Item business unit is outside your assigned location")
        return unit_id
    return requested


def scoped_items(query, db, user, catalog_type=None):
    if catalog_type:
        query = query.filter(Product.catalog_type == catalog_type)
    return query


def validate_reference_profile(db, payload, existing=None):
    method = payload.get("reference_cost_method", getattr(existing, "reference_cost_method", "LAST_PURCHASE"))
    if method not in {"LAST_PURCHASE", "AVERAGE_PURCHASE", "MANUAL"}:
        raise HTTPException(422, "Choose a reference cost method")


def receipt_costs(db, product_ids, user, business_unit_id=None):
    if not product_ids:
        return {}
    query = db.query(GoodsReceiptItem.product_id, GoodsReceiptItem.quantity, GoodsReceiptItem.unit_cost,
        GoodsReceipt.received_at, GoodsReceipt.receipt_number,
        func.row_number().over(partition_by=GoodsReceiptItem.product_id,
            order_by=(GoodsReceipt.received_at.desc(), GoodsReceipt.id.desc(), GoodsReceiptItem.id.desc())).label("rank"))
    query = query.join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptItem.goods_receipt_id).filter(
        GoodsReceipt.status == "POSTED", GoodsReceipt.received_at >= datetime(2026, 1, 1, tzinfo=timezone.utc),
        GoodsReceiptItem.product_id.in_(product_ids), GoodsReceiptItem.quantity > 0)
    query = apply_location_scope(query, GoodsReceipt.location_id, user)
    unit_id = purchasing_unit(db, user, business_unit_id)
    if unit_id:
        query = query.filter(GoodsReceipt.business_unit_id == unit_id)
    history = query.subquery()
    latest = db.query(history).filter(history.c.rank == 1).all()
    averages = db.query(history.c.product_id,
        (func.sum(history.c.quantity * history.c.unit_cost) / func.sum(history.c.quantity)).label("average")).group_by(history.c.product_id).all()
    average_map = {row.product_id: Decimal(str(row.average)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP) for row in averages}
    return {row.product_id: {"last_purchase_price": row.unit_cost,
        "average_purchase_price": average_map[row.product_id],
        "last_purchase_date": row.received_at.date(), "last_purchase_receipt_number": row.receipt_number} for row in latest}


def reference_payload(product, history=None):
    history = history or {}
    method = product.reference_cost_method or "LAST_PURCHASE"
    key = "average_purchase_price" if method == "AVERAGE_PURCHASE" else "last_purchase_price"
    price = product.cost_price if method == "MANUAL" else history.get(key)
    source = method if price is not None else "MASTER_FALLBACK"
    if price is None:
        price = product.cost_price or Decimal("0")
    return {**history, "reference_cost": price, "reference_cost_source": source}


def serialize_item(product, history=None):
    return {**{column.name: getattr(product, column.name) for column in Product.__table__.columns},
            **reference_payload(product, history)}

from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session as OrmSession

from app.models.market_list import MarketList, MarketListItem
from app.models.product import Product
from app.models.purchase_requisition import PurchaseRequisition
from app.models.purchase_requisition_item import PurchaseRequisitionItem


MARKET_SUBGROUPS = {"VEGETABLES", "FRUIT"}


def is_market_list_product(product: Product | None) -> bool:
    return bool(product) and (product.subgroup_name or "").strip().upper() in MARKET_SUBGROUPS


def _product(session: OrmSession, item) -> Product | None:
    return getattr(item, "product", None) or session.get(Product, item.product_id)


def _validate_market_item(session: OrmSession, item: MarketListItem) -> None:
    product = _product(session, item)
    if not product or not product.is_active:
        raise HTTPException(status_code=409, detail="Market List contains a missing or inactive product")
    if not is_market_list_product(product):
        raise HTTPException(
            status_code=409,
            detail=f"{product.code} - {product.name} must use Purchase Requisition; Market List only accepts VEGETABLES and FRUIT.",
        )


def _validate_pr_item(session: OrmSession, item: PurchaseRequisitionItem) -> None:
    product = _product(session, item)
    if not product or not product.is_active:
        raise HTTPException(status_code=409, detail="Purchase Requisition contains a missing or inactive product")
    if is_market_list_product(product):
        raise HTTPException(
            status_code=409,
            detail=f"{product.code} - {product.name} must use Market List because it belongs to {product.subgroup_name}.",
        )


@event.listens_for(OrmSession, "before_flush")
def _enforce_purchasing_item_routing(session, _flush_context, _instances):
    candidates = set(session.new).union(session.dirty)

    market_items: set[MarketListItem] = {
        row for row in candidates if isinstance(row, MarketListItem)
    }
    pr_items: set[PurchaseRequisitionItem] = {
        row for row in candidates if isinstance(row, PurchaseRequisitionItem)
    }

    for row in candidates:
        if isinstance(row, MarketList):
            market_items.update(row.items)
        elif isinstance(row, PurchaseRequisition):
            pr_items.update(row.items)

    for item in market_items:
        _validate_market_item(session, item)
    for item in pr_items:
        _validate_pr_item(session, item)

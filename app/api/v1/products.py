from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import is_superuser, require_permission
from app.models.item_group import ItemGroup
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.schemas.product import ProductCreate, ProductTaxProfileUpdate, ProductUpdate
from app.services.direct_coa_service import DirectCoaService


router = APIRouter(prefix="/products", tags=["Products"])
MARKET_SUBGROUPS = {"VEGETABLES", "FRUIT"}


def _is_market_subgroup(subgroup_name: str | None) -> bool:
    return (subgroup_name or "").strip().upper() in MARKET_SUBGROUPS


def _apply_filters(query, *, active_only: bool, search: str | None, market_only: bool = False, exclude_market: bool = False):
    if active_only:
        query = query.filter(Product.is_active.is_(True))
    subgroup = func.upper(func.trim(Product.subgroup_name))
    if market_only:
        query = query.filter(subgroup.in_(MARKET_SUBGROUPS))
    elif exclude_market:
        query = query.filter(
            or_(Product.subgroup_name.is_(None), ~subgroup.in_(MARKET_SUBGROUPS))
        )
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Product.code.ilike(term), Product.name.ilike(term)))
    return query


def _validate_coa_mappings(db: Session, payload: dict, product: Product | None = None) -> None:
    resolver = DirectCoaService(db)
    values = {
        "inventory_account_id": payload.get("inventory_account_id", product.inventory_account_id if product else None),
        "purchase_account_id": payload.get("purchase_account_id", product.purchase_account_id if product else None),
        "cogs_account_id": payload.get("cogs_account_id", product.cogs_account_id if product else None),
    }
    if values["inventory_account_id"]:
        probe = type("ProductProbe", (), {"code": payload.get("code") or (product.code if product else "new"), **values})()
        resolver.inventory_account(probe)
    for field, label in (("purchase_account_id", "consumption/expense"), ("cogs_account_id", "COGS")):
        if values[field]:
            account = resolver.account(values[field], f"Item {label}")
            if account.account_type != "EXPENSE" or account.normal_balance != "DEBIT":
                raise HTTPException(422, f"Item {label} COA must be a debit-balance expense")


def _last_purchase_prices(db: Session, product_ids: list[int]) -> dict[int, dict]:
    if not product_ids:
        return {}
    rows = (
        db.query(PurchaseOrderItem.product_id, PurchaseOrderItem.unit_price, PurchaseOrder.order_date, PurchaseOrder.po_number)
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id)
        .filter(PurchaseOrderItem.product_id.in_(product_ids), PurchaseOrder.status.notin_(("DRAFT", "REJECTED", "CANCELLED", "EXPIRED")))
        .order_by(PurchaseOrderItem.product_id, PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc(), PurchaseOrderItem.id.desc())
        .all()
    )
    latest: dict[int, dict] = {}
    for product_id, unit_price, order_date, po_number in rows:
        if product_id not in latest:
            latest[product_id] = {"last_purchase_price": unit_price, "last_purchase_date": order_date, "last_purchase_po_number": po_number}
    return latest


@router.get("")
def list_products(active_only: bool = True, market_only: bool = False, exclude_market: bool = False, search: str | None = Query(default=None, max_length=100), page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100), db: Session = Depends(get_db), _=Depends(get_current_user)):
    query = _apply_filters(db.query(Product), active_only=active_only, search=search, market_only=market_only, exclude_market=exclude_market)
    total = query.count()
    rows = query.order_by(Product.code).offset((page - 1) * page_size).limit(page_size).all()
    total_pages = ceil(total / page_size) if total else 0
    return {"items": rows, "page": page, "page_size": page_size, "total_items": total, "total_pages": total_pages, "has_next": page < total_pages, "has_previous": page > 1}


@router.get("/classification-master")
def classification_master(db: Session = Depends(get_db), _=Depends(get_current_user)):
    groups = (
        db.query(ItemGroup)
        .options(selectinload(ItemGroup.subgroups))
        .filter(ItemGroup.is_active.is_(True))
        .order_by(ItemGroup.code)
        .all()
    )
    return [
        {
            "id": group.id,
            "code": group.code,
            "name": group.name,
            "subgroups": [
                {"id": subgroup.id, "code": subgroup.code, "name": subgroup.name}
                for subgroup in sorted(group.subgroups, key=lambda item: item.code)
                if subgroup.is_active
            ],
        }
        for group in groups
    ]


@router.get("/lookup")
def lookup_products(search: str = Query(default="", max_length=100), market_only: bool = False, exclude_market: bool = False, limit: int = Query(default=30, ge=1, le=100), db: Session = Depends(get_db), _=Depends(get_current_user)):
    query = _apply_filters(db.query(Product), active_only=True, search=search, market_only=market_only, exclude_market=exclude_market)
    rows = query.order_by(Product.name, Product.code).limit(limit).all()
    price_history = _last_purchase_prices(db, [row.id for row in rows])
    return [{"id": row.id, "code": row.code, "name": row.name, "description": row.description, "uom": row.uom, "usage_uom": row.usage_uom, "conversion_factor": row.conversion_factor, "tax_category": row.tax_category, "is_taxable": row.is_taxable, "tax_rate": row.tax_rate, "is_market_item": _is_market_subgroup(row.subgroup_name), **price_history.get(row.id, {"last_purchase_price": None, "last_purchase_date": None, "last_purchase_po_number": None})} for row in rows]


@router.post("", status_code=201)
def create_product(data: ProductCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not is_superuser(user):
        raise HTTPException(status_code=403, detail="Only SYSTEM_ADMINISTRATOR can create new Item Master records")
    normalized_code = data.code.strip().upper()
    normalized_name = " ".join(data.name.strip().lower().split())
    if db.query(Product).filter(func.upper(func.trim(Product.code)) == normalized_code).first():
        raise HTTPException(status_code=409, detail="Product code already exists")
    duplicate_name = db.query(Product).filter(
        func.lower(func.regexp_replace(func.trim(Product.name), r"\s+", " ", "g")) == normalized_name
    ).first()
    if duplicate_name:
        raise HTTPException(
            status_code=409,
            detail=f"Product name duplicates existing item {duplicate_name.code} — {duplicate_name.name}",
        )
    payload = data.model_dump()
    payload["is_market_item"] = _is_market_subgroup(payload.get("subgroup_name"))
    _validate_coa_mappings(db, payload)
    product = Product(**payload)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.patch("/{product_id}/tax-profile")
def update_product_tax_profile(
    product_id: int,
    data: ProductTaxProfileUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("products.manage")),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.tax_category = data.tax_category
    product.is_taxable = data.is_taxable
    product.tax_rate = data.tax_rate
    product.tax_reason = data.tax_reason
    product.tax_reference = data.tax_reference
    db.commit()
    db.refresh(product)
    return product


@router.patch("/{product_id}")
def update_product(product_id: int, data: ProductUpdate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    payload = data.model_dump(exclude_unset=True)
    _validate_coa_mappings(db, payload, product)
    for field, value in payload.items():
        if field != "is_market_item":
            setattr(product, field, value)
    product.is_market_item = _is_market_subgroup(product.subgroup_name)
    db.commit()
    db.refresh(product)
    return product

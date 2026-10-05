from math import ceil
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import is_superuser, require_permission
from app.models.item_group import ItemGroup
from app.models.business_unit import BusinessUnit
from app.models.location import Location
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.supplier import Supplier
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
        query = query.filter(or_(Product.subgroup_name.is_(None), ~subgroup.in_(MARKET_SUBGROUPS)))
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Product.code.ilike(term), Product.name.ilike(term)))
    return query

def _normalize_item_coa(payload: dict, product: Product | None = None) -> None:
    """Keep only mappings used by the explicitly selected item treatment.

    This changes master configuration only; it never adjusts balances or journals.
    Stock issue expense is optional here and is used only when stock goes OUT.
    """
    fields = {"inventory_account_id", "purchase_account_id", "asset_account_id", "cogs_account_id"}
    if not (fields.intersection(payload) or "inventory_treatment" in payload):
        return
    treatment = payload.get("inventory_treatment", getattr(product, "inventory_treatment", "REVIEW_REQUIRED"))
    allowed = {
        "STOCK": {"inventory_account_id", "cogs_account_id"},
        "DIRECT_USE": {"purchase_account_id"},
        "NON_STOCK": {"purchase_account_id"},
        "FIXED_ASSET": {"asset_account_id"},
    }.get(treatment)
    if allowed is None:
        return
    for field in fields - allowed:
        payload[field] = None


def _validate_coa_mappings(db: Session, payload: dict, product: Product | None = None) -> None:
    resolver = DirectCoaService(db)
    values = {
        "inventory_account_id": payload.get("inventory_account_id", product.inventory_account_id if product else None),
        "purchase_account_id": payload.get("purchase_account_id", product.purchase_account_id if product else None),
        # OUT mapping is independent of the receiving inventory mapping.
        "cogs_account_id": payload.get("cogs_account_id"),
        "asset_account_id": payload.get("asset_account_id", getattr(product, "asset_account_id", None) if product else None),
    }
    if values["inventory_account_id"]:
        probe = type("ProductProbe", (), {"code": payload.get("code") or (product.code if product else "new"), **values})()
        resolver.inventory_account(probe)
    for field, label in (("purchase_account_id", "consumption/expense"), ("cogs_account_id", "COGS")):
        if field == "cogs_account_id" and product and values[field] == product.cogs_account_id:
            continue
        if values[field]:
            account = resolver.account(values[field], f"Item {label}")
            if account.account_type != "EXPENSE" or account.normal_balance != "DEBIT":
                raise HTTPException(422, f"Item {label} COA must be a debit-balance expense")
    if values["asset_account_id"]:
        account = resolver.account(values["asset_account_id"], "Item fixed asset")
        if account.account_type != "ASSET" or account.normal_balance != "DEBIT" or account.account_subtype in resolver.BANK_SUBTYPES:
            raise HTTPException(422, "Item fixed asset COA must be a debit-balance non-cash asset")

def _validate_treatment(payload: dict, product: Product | None = None) -> None:
    treatment = payload.get("inventory_treatment", getattr(product, "inventory_treatment", "REVIEW_REQUIRED") if product else "REVIEW_REQUIRED")
    item_type = payload.get("item_type", getattr(product, "item_type", "BUY") if product else "BUY")
    inventory_account_id = payload.get("inventory_account_id", product.inventory_account_id if product else None)
    purchase_account_id = payload.get("purchase_account_id", product.purchase_account_id if product else None)
    asset_account_id = payload.get("asset_account_id", getattr(product, "asset_account_id", None) if product else None)

    if treatment == "STOCK" and not inventory_account_id:
        raise HTTPException(422, "STOCK items require an Inventory Asset COA")
    if treatment in {"DIRECT_USE", "NON_STOCK"} and not purchase_account_id and not (item_type == "SELL" and treatment == "NON_STOCK"):
        raise HTTPException(422, f"{treatment} items require an Expense / Consumption COA")
    if treatment == "FIXED_ASSET" and not asset_account_id:
        raise HTTPException(422, "FIXED_ASSET items require a Fixed Asset COA")


def _validate_sales_profile(db: Session, payload: dict, product: Product | None = None) -> None:
    if any(field in payload and payload[field] is None for field in ("pbjt_rate", "sales_ppn_rate", "pph23_rate")):
        raise HTTPException(422, "Sales tax rates must be numbers between 0 and 100")
    values = {field: payload.get(field, getattr(product, field, None) if product else None)
              for field in ("sales_business_unit_id", "sales_location_id", "pbjt_rate", "sales_ppn_rate", "pph23_rate")}
    if Decimal(values["pbjt_rate"] or 0) > 0 and Decimal(values["sales_ppn_rate"] or 0) > 0:
        raise HTTPException(422, "PBJT and PPN cannot both apply to the same selling item")
    business_unit_id, location_id = values["sales_business_unit_id"], values["sales_location_id"]
    if business_unit_id:
        unit = db.get(BusinessUnit, business_unit_id)
        if not unit or not unit.is_active:
            raise HTTPException(422, "Select an active sales business unit")
    if location_id:
        location = db.get(Location, location_id)
        if not location or not location.is_active:
            raise HTTPException(422, "Select an active sales location")
        if not business_unit_id or location.business_unit_id != business_unit_id:
            raise HTTPException(422, "Sales location must belong to the selected business unit")


def _last_purchase_prices(db: Session, product_ids: list[int]) -> dict[int, dict]:
    if not product_ids:
        return {}
    rows = (db.query(PurchaseOrderItem.product_id, PurchaseOrderItem.unit_price, PurchaseOrder.order_date, PurchaseOrder.po_number).join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id).filter(PurchaseOrderItem.product_id.in_(product_ids), PurchaseOrder.status.notin_(("DRAFT", "REJECTED", "CANCELLED", "EXPIRED"))).order_by(PurchaseOrderItem.product_id, PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc(), PurchaseOrderItem.id.desc()).all())
    latest: dict[int, dict] = {}
    for product_id, unit_price, order_date, po_number in rows:
        if product_id not in latest:
            latest[product_id] = {"last_purchase_price": unit_price, "last_purchase_date": order_date, "last_purchase_po_number": po_number}
    return latest

@router.get("")
def list_products(
    active_only: bool = True,
    market_only: bool = False,
    exclude_market: bool = False,
    item_type: Annotated[str | None, Query(pattern="^(BUY|SELL)$")] = None,
    inventory_treatment: Annotated[str | None, Query(pattern="^(STOCK|DIRECT_USE|FIXED_ASSET|NON_STOCK|REVIEW_REQUIRED)$")] = None,
    tax_category: Annotated[str | None, Query(pattern="^(STANDARD|EXEMPT|NON_TAXABLE|SPECIAL|REVIEW_REQUIRED)$")] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = _apply_filters(db.query(Product), active_only=active_only, search=search, market_only=market_only, exclude_market=exclude_market)
    if item_type:
        query = query.filter(Product.item_type == item_type)
    if inventory_treatment:
        query = query.filter(Product.inventory_treatment == inventory_treatment)
    if tax_category:
        query = query.filter(Product.tax_category == tax_category)
    total = query.count()
    rows = query.order_by(Product.code).offset((page - 1) * page_size).limit(page_size).all()
    total_pages = ceil(total / page_size) if total else 0
    return {"items": rows, "page": page, "page_size": page_size, "total_items": total, "total_pages": total_pages, "has_next": page < total_pages, "has_previous": page > 1}

def classification_catalog(groups, products, item_type=None):
    catalog = {}
    blocked_groups = {group.code for group in groups if not group.is_active}
    blocked_subgroups = {sub.code for group in groups for sub in group.subgroups if not sub.is_active}
    for group in groups:
        kind = group.item_type or "BUY"
        if not group.is_active or (item_type and kind != item_type):
            continue
        catalog[(kind, group.code)] = {
            "id": group.id, "code": group.code, "name": group.name, "item_type": kind,
            "subgroups": {sub.code: {"id": sub.id, "code": sub.code, "name": sub.name}
                         for sub in group.subgroups if sub.is_active},
        }
    for kind, code, name, sub_code, sub_name in sorted(products, key=lambda row: tuple(str(value or "") for value in row)):
        kind = kind or "BUY"
        if not code or not name or code in blocked_groups or (item_type and kind != item_type):
            continue
        group = catalog.setdefault((kind, code), {
            "id": 0, "code": code, "name": name, "item_type": kind, "subgroups": {},
        })
        if sub_code and sub_name and sub_code not in blocked_subgroups:
            group["subgroups"].setdefault(sub_code, {"id": 0, "code": sub_code, "name": sub_name})
    return [{**group, "subgroups": sorted(group["subgroups"].values(), key=lambda sub: sub["code"])}
            for _, group in sorted(catalog.items())]


@router.get("/classification-master")
def classification_master(item_type: Annotated[str | None, Query(pattern="^(BUY|SELL)$")] = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    # Imported products can predate the separate classification master tables.
    # Include their existing classifications without changing product records.
    groups = db.query(ItemGroup).options(selectinload(ItemGroup.subgroups)).order_by(ItemGroup.code).all()
    products = db.query(Product.item_type, Product.group_code, Product.group_name,
                        Product.subgroup_code, Product.subgroup_name).filter(Product.is_active.is_(True)).distinct().all()
    return classification_catalog(groups, products, item_type)

@router.get("/lookup")
def lookup_products(search: Annotated[str, Query(max_length=100)] = "", market_only: bool = False, exclude_market: bool = False, limit: int = Query(default=30, ge=1, le=100), db: Session = Depends(get_db), _=Depends(get_current_user)):
    query = _apply_filters(db.query(Product), active_only=True, search=search, market_only=market_only, exclude_market=exclude_market)
    rows = query.order_by(Product.name, Product.code).limit(limit).all()
    price_history = _last_purchase_prices(db, [row.id for row in rows])
    return [{"id": row.id, "code": row.code, "name": row.name, "description": row.description, "uom": row.uom, "usage_uom": row.usage_uom, "conversion": row.conversion, "tax_category": row.tax_category, "is_taxable": row.is_taxable, "tax_rate": row.tax_rate, "inventory_treatment": row.inventory_treatment, "inventory_account_id": row.inventory_account_id, "purchase_account_id": row.purchase_account_id, "cogs_account_id": row.cogs_account_id, "asset_account_id": row.asset_account_id, "is_market_item": _is_market_subgroup(row.subgroup_name), **price_history.get(row.id, {"last_purchase_price": None, "last_purchase_date": None, "last_purchase_po_number": None})} for row in rows]

@router.get("/{product_id}")
def product_detail(product_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Item not found")

    stock = []
    if product.inventory_treatment == "STOCK":
        inventory_rows = (db.query(Inventory).options(selectinload(Inventory.warehouse))
                          .filter(Inventory.product_id == product_id)
                          .order_by(Inventory.warehouse_id).all())
        stock = [{"warehouse_id": row.warehouse_id,
                  "warehouse": row.warehouse.name if row.warehouse else None,
                  "quantity": row.quantity, "average_cost": row.average_cost,
                  "value": row.quantity * row.average_cost} for row in inventory_rows]

    orders = (db.query(PurchaseOrderItem, PurchaseOrder, Supplier)
              .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id)
              .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
              .filter(PurchaseOrderItem.product_id == product_id,
                      PurchaseOrder.status.notin_(("DRAFT", "REJECTED", "CANCELLED", "EXPIRED")))
              .order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc(), PurchaseOrderItem.id.desc())
              .limit(20).all())
    purchases = [{"order_id": order.id, "po_number": order.po_number,
                  "order_date": order.order_date, "supplier": supplier.name,
                  "quantity": line.quantity, "unit_price": line.unit_price,
                  "uom": line.uom or product.uom} for line, order, supplier in orders]

    receipts = (db.query(GoodsReceiptItem, GoodsReceipt)
                .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptItem.goods_receipt_id)
                .filter(GoodsReceiptItem.product_id == product_id, GoodsReceipt.status == "POSTED")
                .order_by(GoodsReceipt.received_at.desc(), GoodsReceipt.id.desc(), GoodsReceiptItem.id.desc())
                .limit(20).all())
    receiving = [{"receipt_id": receipt.id, "receipt_number": receipt.receipt_number,
                  "received_at": receipt.received_at, "quantity": line.quantity,
                  "unit_cost": line.unit_cost, "warehouse_id": receipt.warehouse_id}
                 for line, receipt in receipts]
    unit = db.get(BusinessUnit, product.sales_business_unit_id) if product.sales_business_unit_id else None
    location = db.get(Location, product.sales_location_id) if product.sales_location_id else None
    return {"item": product, "stock": stock, "purchases": purchases, "receiving": receiving,
            "sales_scope": {"business_unit": unit.name if unit else None,
                            "location": location.name if location else None}}

@router.post("", status_code=201)
def create_product(data: ProductCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not is_superuser(user):
        raise HTTPException(status_code=403, detail="Only SYSTEM_ADMINISTRATOR can create new Item Master records")
    normalized_code = data.code.strip().upper()
    normalized_name = " ".join(data.name.strip().lower().split())
    if db.query(Product).filter(func.upper(func.trim(Product.code)) == normalized_code).first():
        raise HTTPException(status_code=409, detail="Product code already exists")
    duplicate_name = db.query(Product).filter(func.lower(func.regexp_replace(func.trim(Product.name), r"\s+", " ", "g")) == normalized_name).first()
    if duplicate_name:
        raise HTTPException(status_code=409, detail=f"Product name duplicates existing item {duplicate_name.code} — {duplicate_name.name}")
    payload = data.model_dump()
    if str(payload.get("subgroup_name") or "").strip().upper() == "GRESORIS":
        payload["subgroup_name"] = "GROCERIES"
    payload["is_market_item"] = _is_market_subgroup(payload.get("subgroup_name"))
    _normalize_item_coa(payload)
    _validate_treatment(payload)
    _validate_coa_mappings(db, payload)
    _validate_sales_profile(db, payload)
    product = Product(**payload)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product

@router.patch("/{product_id}/tax-profile")
def update_product_tax_profile(product_id: int, data: ProductTaxProfileUpdate, db: Session = Depends(get_db), _=Depends(require_permission("products.manage"))):
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
    if str(payload.get("subgroup_name") or "").strip().upper() == "GRESORIS":
        payload["subgroup_name"] = "GROCERIES"
    _normalize_item_coa(payload, product)
    _validate_treatment(payload, product)
    _validate_coa_mappings(db, payload, product)
    _validate_sales_profile(db, payload, product)
    for field, value in payload.items():
        if field != "is_market_item":
            setattr(product, field, value)
    product.is_market_item = _is_market_subgroup(product.subgroup_name)
    db.commit()
    db.refresh(product)
    return product

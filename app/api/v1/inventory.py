from datetime import date, timedelta
from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.chart_of_account import ChartOfAccount
from app.models.goods_receipt import GoodsReceipt
from app.models.inventory import Inventory
from app.models.location import Location
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.warehouse import Warehouse
from app.services.location_access import apply_warehouse_scope, resolve_location_id


router = APIRouter(prefix="/inventory", tags=["Inventory"])


def _paged(rows, *, page: int, page_size: int, total: int):
    total_pages = ceil(total / page_size) if total else 0
    return {
        "items": rows,
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


def inventory_row(inventory: Inventory, product: Product, warehouse: Warehouse, account: ChartOfAccount | None = None, *, quantity=None, stock_value=None):
    quantity = Decimal(inventory.quantity or 0) if quantity is None else Decimal(quantity)
    stock_value = quantity * Decimal(inventory.average_cost or 0) if stock_value is None else Decimal(stock_value)
    average_cost = stock_value / quantity if quantity else Decimal('0')
    minimum_stock = Decimal(product.minimum_stock or 0)
    is_monitored = minimum_stock > 0
    is_low_stock = is_monitored and quantity <= minimum_stock
    shortage = max(minimum_stock - quantity, Decimal("0")) if is_low_stock else Decimal("0")
    return {
        "id": inventory.id,
        "product_id": product.id,
        "product_code": product.code,
        "product_name": product.name,
        "inventory_account_id": product.inventory_account_id,
        "inventory_account_code": account.account_number if account else None,
        "inventory_account_name": account.account_name if account else None,
        "location_id": warehouse.location_id,
        "uom": product.uom,
        "warehouse_id": warehouse.id,
        "warehouse_code": warehouse.code,
        "warehouse_name": warehouse.name,
        "quantity": quantity,
        "average_cost": average_cost,
        "stock_value": stock_value,
        "minimum_stock": minimum_stock,
        "low_stock": is_low_stock,
        "shortage": shortage,
        # Compatibility fields for older UI clients. Both now follow the one
        # canonical business rule: current warehouse stock <= item minimum.
        "below_minimum": is_low_stock,
        "needs_reorder": is_low_stock,
    }


def _inventory_base(db: Session, user, warehouse_id: int | None = None):
    query = (
        db.query(Inventory, Product, Warehouse)
        .join(Product, Product.id == Inventory.product_id)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .outerjoin(ChartOfAccount, ChartOfAccount.id == Product.inventory_account_id)
        .outerjoin(Location, Location.id == Warehouse.location_id)
        .filter(Product.is_active.is_(True), Warehouse.is_active.is_(True))
    )
    query = apply_warehouse_scope(query, user)
    if warehouse_id:
        query = query.filter(Inventory.warehouse_id == warehouse_id)
    return query


def _effective_movement_date():
    # Receiving uses the business receipt date; other movements use their event date.
    return func.date(case(
        ((StockMovement.reference_type == "GOODS_RECEIPT")
         & (StockMovement.goods_receipt_id.is_not(None)), GoodsReceipt.received_at),
        else_=StockMovement.created_at,
    ))


@router.get("")
def list_inventory(
    warehouse_id: int | None = None,
    account_id: int | None = None,
    location_id: int | None = None,
    as_of: date | None = None,
    movement_class: str | None = None,
    health: str | None = Query(default=None, pattern="^(HEALTHY|LOW_STOCK|REORDER|BELOW_MINIMUM)$"),
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=5000),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if movement_class not in (None, "FAST", "SLOW", "DEAD"):
        raise HTTPException(422, "Invalid stock movement class")
    scoped = _inventory_base(db, user, warehouse_id)
    if account_id:
        scoped = scoped.filter(Product.inventory_account_id == account_id)
    if location_id:
        scoped = scoped.filter(Warehouse.location_id == location_id)

    if as_of is None:
        quantity = func.coalesce(Inventory.quantity, 0)
        stock_value = quantity * func.coalesce(Inventory.average_cost, 0)
    else:
        # Roll the current snapshot back using movements after the selected day.
        # This keeps manually entered opening stock in the baseline.
        signed_qty = case(
            (StockMovement.movement_type == "OUT", -StockMovement.quantity),
            else_=StockMovement.quantity,
        )
        signed_value = signed_qty * func.coalesce(StockMovement.unit_cost, 0)
        later = (
            db.query(
                StockMovement.product_id.label("product_id"),
                StockMovement.warehouse_id.label("warehouse_id"),
                func.sum(signed_qty).label("quantity"),
                func.sum(signed_value).label("value"),
            )
            .outerjoin(GoodsReceipt, GoodsReceipt.id == StockMovement.goods_receipt_id)
            .filter(_effective_movement_date() > as_of)
            .group_by(StockMovement.product_id, StockMovement.warehouse_id)
            .subquery()
        )
        scoped = scoped.outerjoin(
            later,
            (later.c.product_id == Inventory.product_id)
            & (later.c.warehouse_id == Inventory.warehouse_id),
        )
        quantity = func.coalesce(Inventory.quantity, 0) - func.coalesce(later.c.quantity, 0)
        stock_value = (
            func.coalesce(Inventory.quantity, 0) * func.coalesce(Inventory.average_cost, 0)
            - func.coalesce(later.c.value, 0)
        )

    as_of_date = as_of or date.today()
    movement_date = _effective_movement_date()
    history = (
        db.query(
            StockMovement.product_id.label("product_id"),
            StockMovement.warehouse_id.label("warehouse_id"),
            func.max(case(
                (StockMovement.movement_type == "OUT", movement_date),
                else_=None,
            )).label("last_out"),
            func.max(movement_date).label("last_movement"),
        )
        .outerjoin(GoodsReceipt, GoodsReceipt.id == StockMovement.goods_receipt_id)
        .filter(movement_date <= as_of_date)
        .group_by(StockMovement.product_id, StockMovement.warehouse_id)
        .subquery()
    )
    scoped = scoped.outerjoin(
        history,
        (history.c.product_id == Inventory.product_id)
        & (history.c.warehouse_id == Inventory.warehouse_id),
    )
    recent_cutoff = as_of_date - timedelta(days=30)
    dead_cutoff = as_of_date - timedelta(days=90)
    movement_status = case(
        (quantity <= 0, "EMPTY"),
        (history.c.last_out >= recent_cutoff, "FAST"),
        (func.coalesce(history.c.last_movement, date(as_of_date.year, 1, 1)) < dead_cutoff, "DEAD"),
        else_="SLOW",
    )

    minimum = func.coalesce(Product.minimum_stock, 0)
    monitored = minimum > 0
    low_stock = monitored & (quantity <= minimum)
    query = scoped
    if health in {"LOW_STOCK", "REORDER", "BELOW_MINIMUM"}:
        query = query.filter(low_stock)
    elif health == "HEALTHY":
        query = query.filter(or_(minimum <= 0, quantity > minimum))
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Product.code.ilike(term), Product.name.ilike(term), Warehouse.name.ilike(term)))

    movement_totals = query.with_entities(*[
        func.coalesce(func.sum(case((movement_status == label, 1), else_=0)), 0)
        for label in ("FAST", "SLOW", "DEAD")
    ], *[
        func.coalesce(func.sum(case((movement_status == label, stock_value), else_=0)), 0)
        for label in ("FAST", "SLOW", "DEAD")
    ]).one()
    if movement_class:
        query = query.filter(movement_status == movement_class)

    summary_rows = query.with_entities(
        func.count(Inventory.id),
        func.coalesce(func.sum(stock_value), 0),
        func.coalesce(func.sum(case((monitored, 1), else_=0)), 0),
        func.coalesce(func.sum(case((low_stock, 1), else_=0)), 0),
    ).one()
    total = int(summary_rows[0] or 0)
    grouped_rows = query.with_entities(
        ChartOfAccount.id, ChartOfAccount.account_number, ChartOfAccount.account_name,
        Warehouse.location_id, Location.name,
        func.coalesce(func.sum(quantity), 0), func.coalesce(func.sum(stock_value), 0),
    ).group_by(
        ChartOfAccount.id, ChartOfAccount.account_number, ChartOfAccount.account_name,
        Warehouse.location_id, Location.name,
    ).order_by(ChartOfAccount.account_number, Warehouse.location_id).all()
    rows = query.add_entity(ChartOfAccount).add_columns(
        quantity.label("as_of_quantity"), stock_value.label("as_of_value"),
        movement_status.label("movement_class"),
        history.c.last_out, history.c.last_movement,
    ).order_by(Product.code, Warehouse.code).offset((page - 1) * page_size).limit(page_size).all()
    result = _paged([
        {
            **inventory_row(inventory, product, warehouse, account,
                            quantity=as_of_quantity, stock_value=as_of_value),
            "movement_class": velocity,
            "last_out": last_out,
            "last_movement": last_movement,
        }
        for inventory, product, warehouse, account, as_of_quantity, as_of_value,
            velocity, last_out, last_movement in rows
    ], page=page, page_size=page_size, total=total)
    result["as_of"] = as_of
    result["summary"] = {
        "stock_lines": total,
        "stock_value": summary_rows[1] or 0,
        "monitored_lines": int(summary_rows[2] or 0),
        "low_stock": int(summary_rows[3] or 0),
        "needs_reorder": int(summary_rows[3] or 0),
        "below_minimum": int(summary_rows[3] or 0),
        "movement_days": {"fast": 30, "dead": 90},
        "movement_classes": {
            label: {"stock_lines": int(movement_totals[index] or 0),
                    "stock_value": movement_totals[index + 3] or 0}
            for index, label in enumerate(("FAST", "SLOW", "DEAD"))
        },
    }
    result["totals_by_account_location"] = [
        {
            "account_id": row[0], "account_code": row[1], "account_name": row[2],
            "location_id": row[3], "location_name": row[4],
            "quantity": row[5] or 0, "stock_value": row[6] or 0,
        }
        for row in grouped_rows
    ]
    by_account = {}
    for row in result["totals_by_account_location"]:
        key = row["account_id"]
        if key not in by_account:
            by_account[key] = {
                "account_id": key, "account_code": row["account_code"],
                "account_name": row["account_name"],
                "quantity": Decimal("0"), "stock_value": Decimal("0"),
            }
        by_account[key]["quantity"] += Decimal(row["quantity"])
        by_account[key]["stock_value"] += Decimal(row["stock_value"])
    result["totals_by_account"] = sorted(
        by_account.values(), key=lambda row: row["account_code"] or ""
    )
    return result


@router.get("/accounts")
def inventory_accounts(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # Include configured inventory accounts and the hotel's inventory COA family,
    # while excluding unrelated cash, receivable, expense, and header accounts.
    mapped = db.query(Product.inventory_account_id).filter(
        Product.inventory_account_id.is_not(None)
    )
    rows = db.query(ChartOfAccount).filter(
        ChartOfAccount.is_active.is_(True),
        ChartOfAccount.is_posting.is_(True),
        ChartOfAccount.account_type == "ASSET",
        or_(
            ChartOfAccount.account_number.like("100-300-%"),
            ChartOfAccount.id.in_(mapped),
        ),
    ).order_by(ChartOfAccount.account_number).all()
    return [
        {"id": row.id, "account_number": row.account_number,
         "account_name": row.account_name}
        for row in rows
    ]


@router.get("/movements")
def list_movements(
    product_id: int | None = None,
    warehouse_id: int | None = None,
    purchase_order_id: int | None = None,
    goods_receipt_id: int | None = None,
    location_id: int | None = None,
    department_id: int | None = None,
    account_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "From date must not exceed To date")
    location_id = resolve_location_id(user, location_id)
    effective_date = _effective_movement_date()
    account_key = func.coalesce(StockMovement.inventory_account_id, Product.inventory_account_id)
    query = (
        db.query(StockMovement, Product, Warehouse)
        .join(Product, Product.id == StockMovement.product_id)
        .join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
        .outerjoin(GoodsReceipt, GoodsReceipt.id == StockMovement.goods_receipt_id)
        .outerjoin(ChartOfAccount, ChartOfAccount.id == account_key)
    )
    query = apply_warehouse_scope(query, user)
    if product_id:
        query = query.filter(StockMovement.product_id == product_id)
    if warehouse_id:
        query = query.filter(StockMovement.warehouse_id == warehouse_id)
    if purchase_order_id:
        query = query.filter(StockMovement.purchase_order_id == purchase_order_id)
    if goods_receipt_id:
        query = query.filter(StockMovement.goods_receipt_id == goods_receipt_id)
    if location_id:
        query = query.filter(StockMovement.location_id == location_id)
    if department_id:
        query = query.filter(StockMovement.department_id == department_id)
    if account_id:
        query = query.filter(account_key == account_id)
    if date_from:
        query = query.filter(effective_date >= date_from)
    if date_to:
        query = query.filter(effective_date <= date_to)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Product.code.ilike(term), Product.name.ilike(term), Warehouse.name.ilike(term)))

    in_qty = case((StockMovement.movement_type == "IN", StockMovement.quantity), else_=0)
    out_qty = case((StockMovement.movement_type == "OUT", StockMovement.quantity), else_=0)
    in_value = in_qty * func.coalesce(StockMovement.unit_cost, 0)
    out_value = out_qty * func.coalesce(StockMovement.unit_cost, 0)
    totals = query.with_entities(
        func.coalesce(func.sum(in_qty), 0), func.coalesce(func.sum(out_qty), 0),
        func.coalesce(func.sum(in_value), 0), func.coalesce(func.sum(out_value), 0),
    ).one()
    grouped = query.with_entities(
        ChartOfAccount.id, ChartOfAccount.account_number, ChartOfAccount.account_name,
        func.coalesce(func.sum(in_qty), 0), func.coalesce(func.sum(out_qty), 0),
        func.coalesce(func.sum(in_value), 0), func.coalesce(func.sum(out_value), 0),
    ).group_by(ChartOfAccount.id, ChartOfAccount.account_number, ChartOfAccount.account_name).order_by(ChartOfAccount.account_number).all()
    total = query.count()
    rows = query.add_entity(ChartOfAccount).add_columns(
        effective_date.label("effective_date")
    ).order_by(effective_date.desc(), StockMovement.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    items = [
        {
            "id": movement.id,
            "movement_number": f"SM-{movement.id:08d}",
            "movement_date": movement_date,
            "recorded_at": movement.created_at,
            "movement_type": movement.movement_type,
            "inventory_account_id": account.id if account else None,
            "inventory_account_code": account.account_number if account else None,
            "inventory_account_name": account.account_name if account else None,
            "product_id": product.id, "product_code": product.code, "product_name": product.name,
            "warehouse_id": warehouse.id, "warehouse_name": warehouse.name,
            "quantity": movement.quantity, "unit_cost": movement.unit_cost,
            "movement_value": Decimal(movement.quantity or 0) * Decimal(movement.unit_cost or 0),
            "reference_type": movement.reference_type, "reference_id": movement.reference_id,
            "goods_receipt_id": movement.goods_receipt_id,
            "goods_receipt_item_id": movement.goods_receipt_item_id,
            "receipt_number": movement.goods_receipt.receipt_number if movement.goods_receipt else None,
            "purchase_order_id": movement.purchase_order_id,
            "purchase_order_item_id": movement.purchase_order_item_id,
            "purchase_order_number": movement.purchase_order.po_number if movement.purchase_order else None,
            "business_unit_id": movement.business_unit_id,
            "location_id": movement.location_id, "department_id": movement.department_id,
            "reference_number": (
                movement.goods_receipt.receipt_number if movement.goods_receipt
                else movement.purchase_order.po_number if movement.purchase_order
                else f"{movement.reference_type}-{movement.reference_id}"
                if movement.reference_type and movement.reference_id else "-"
            ),
            "notes": movement.notes,
        }
        for movement, product, warehouse, account, movement_date in rows
    ]
    result = _paged(items, page=page, page_size=page_size, total=total)
    result["summary"] = {
        "in_qty": totals[0], "out_qty": totals[1], "net_qty": totals[0] - totals[1],
        "in_value": totals[2], "out_value": totals[3], "net_value": totals[2] - totals[3],
    }
    result["totals_by_account"] = [
        {
            "account_id": row[0], "account_code": row[1], "account_name": row[2],
            "in_qty": row[3], "out_qty": row[4], "net_qty": row[3] - row[4],
            "in_value": row[5], "out_value": row[6], "net_value": row[5] - row[6],
        }
        for row in grouped
    ]
    return result

@router.get("/{inventory_id}")
def get_inventory(
    inventory_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    user = _
    row = (
        apply_warehouse_scope(db.query(Inventory, Product, Warehouse), user)
        .join(Product, Product.id == Inventory.product_id)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .filter(Inventory.id == inventory_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Inventory record not found")
    return inventory_row(*row)

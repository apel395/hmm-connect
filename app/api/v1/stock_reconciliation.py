from datetime import date
from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.models.inventory import Inventory
from app.models.stock_movement import StockMovement
from app.models.stock_reconciliation_request import StockReconciliationRequest
from app.models.warehouse import Warehouse
from app.services.location_access import apply_warehouse_scope, enforce_warehouse_access
from app.services.audit import record_audit

router = APIRouter(prefix="/stock-reconciliation", tags=["Stock Reconciliation"])
ZERO = Decimal("0")


class AdjustmentRequestIn(BaseModel):
    fiscal_year: int = Field(ge=2026, le=2100)
    product_id: int
    warehouse_id: int
    requested_qty: Decimal = Field(gt=0)
    notes: str = Field(min_length=3, max_length=1000)


def _rows(db: Session, user, fiscal_year: int, location_id: int | None, warehouse_id: int | None):
    warehouses = apply_warehouse_scope(db.query(Warehouse), user)
    if location_id:
        warehouses = warehouses.filter(Warehouse.location_id == location_id)
    if warehouse_id:
        warehouses = warehouses.filter(Warehouse.id == warehouse_id)
    warehouse_map = {w.id: w for w in warehouses.all()}
    if not warehouse_map:
        return []
    ids = list(warehouse_map)
    inventory = {
        (item.product_id, item.warehouse_id): item
        for item in db.query(Inventory).options(joinedload(Inventory.product)).filter(Inventory.warehouse_id.in_(ids)).all()
    }
    movements = db.query(StockMovement).options(
        joinedload(StockMovement.goods_receipt), joinedload(StockMovement.product)
    ).filter(StockMovement.warehouse_id.in_(ids)).all()
    cutoff = date(fiscal_year, 1, 1)
    historical = {}
    period = {}
    excluded = {}
    product_map = {key: item.product for key, item in inventory.items()}
    for movement in movements:
        key = (movement.product_id, movement.warehouse_id)
        product_map[key] = movement.product
        receipt_in = movement.goods_receipt and movement.reference_type == "GOODS_RECEIPT" and movement.movement_type == "IN"
        moment = movement.goods_receipt.received_at if receipt_in else movement.created_at
        if moment is None:
            continue
        effective_date = moment.date()
        signed = Decimal(movement.quantity or 0) * (-1 if movement.movement_type == "OUT" else 1)
        target = historical if effective_date < cutoff else period
        target[key] = target.get(key, ZERO) + signed
        if receipt_in and effective_date < cutoff and signed > ZERO:
            excluded[key] = excluded.get(key, ZERO) + signed

    requests = {
        (request.product_id, request.warehouse_id): request
        for request in db.query(StockReconciliationRequest).filter(
            StockReconciliationRequest.fiscal_year == fiscal_year,
            StockReconciliationRequest.warehouse_id.in_(ids),
            StockReconciliationRequest.status == "PENDING",
        ).order_by(StockReconciliationRequest.id.desc()).all()
    }
    rows = []
    for index, key in enumerate(sorted(set(inventory) | set(historical) | set(period)), 1):
        product_id, wh_id = key
        product = product_map.get(key)
        warehouse = warehouse_map[wh_id]
        closing = historical.get(key, ZERO)
        current = Decimal(inventory[key].quantity or 0) if key in inventory else ZERO
        opening = current - period.get(key, ZERO)
        variance = closing - opening
        request = requests.get(key)
        rows.append({
            "id": index, "product_id": product_id,
            "product_code": product.code if product else str(product_id),
            "product_name": product.name if product else "Unknown item",
            "uom": getattr(product, "uom", None) or "",
            "warehouse_id": wh_id, "warehouse_name": warehouse.name,
            "location_id": warehouse.location_id,
            "location_name": warehouse.location.name if warehouse.location else None,
            "closing_2025_qty": closing,
            "excluded_pre2026_receiving_qty": excluded.get(key, ZERO),
            "opening_2026_qty": opening,
            "current_qty": current, "variance_qty": variance,
            "request_qty": request.requested_qty if request else None,
            "request_status": request.status if request else None,
            "status": "REQUESTED" if request else ("MATCHED" if variance == ZERO else "VARIANCE"),
        })
    return rows


@router.get("")
def listing(
    fiscal_year: int = Query(2026, ge=2026, le=2100),
    location_id: int | None = None,
    warehouse_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not has_permission(user, "finance.view"):
        raise HTTPException(403, "Finance access required")
    if status and status not in {"MATCHED", "VARIANCE", "REQUESTED"}:
        raise HTTPException(422, "Invalid stock reconciliation status")
    rows = _rows(db, user, fiscal_year, location_id, warehouse_id)
    if status:
        rows = [row for row in rows if row["status"] == status]
    if search:
        token = search.strip().lower()
        rows = [row for row in rows if token in row["product_code"].lower() or token in row["product_name"].lower()]
    total = len(rows)
    return {
        "items": rows[(page - 1) * page_size:page * page_size],
        "page": page, "page_size": page_size, "total_items": total,
        "total_pages": ceil(total / page_size) if total else 0,
        "has_next": page * page_size < total, "has_previous": page > 1,
        "summary": {
            "item_count": total,
            "opening_qty": sum((row["opening_2026_qty"] for row in rows), ZERO),
            "current_qty": sum((row["current_qty"] for row in rows), ZERO),
            "variance_qty": sum((row["variance_qty"] for row in rows), ZERO),
            "pending_requests": sum(row["request_status"] == "PENDING" for row in rows),
        },
    }


@router.post("/requests", status_code=201)
def request_adjustment(
    payload: AdjustmentRequestIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not has_permission(user, "finance.manage"):
        raise HTTPException(403, "Finance management access required")
    warehouse = db.get(Warehouse, payload.warehouse_id)
    if not warehouse:
        raise HTTPException(404, "Warehouse not found")
    enforce_warehouse_access(user, warehouse)
    if db.bind and db.bind.dialect.name == "postgresql":
        lock_id = 930000000 + payload.fiscal_year * 1000000 + payload.warehouse_id * 1000 + payload.product_id
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
    rows = _rows(db, user, payload.fiscal_year, warehouse.location_id, warehouse.id)
    row = next((item for item in rows if item["product_id"] == payload.product_id), None)
    if not row:
        raise HTTPException(404, "Stock item not found in reconciliation")
    if row["request_status"]:
        raise HTTPException(409, "An opening stock adjustment request is already pending")
    if row["variance_qty"] == ZERO:
        raise HTTPException(409, "Opening stock has no variance to reconcile")
    if payload.requested_qty > abs(row["variance_qty"]):
        raise HTTPException(422, "Requested quantity exceeds the opening stock variance")
    request = StockReconciliationRequest(
        fiscal_year=payload.fiscal_year, product_id=payload.product_id,
        warehouse_id=payload.warehouse_id, requested_qty=payload.requested_qty,
        variance_qty=row["variance_qty"], notes=payload.notes.strip(),
        status="PENDING", created_by_id=user.id,
    )
    db.add(request)
    db.flush()
    record_audit(
        db, user, "STOCK_RECONCILIATION_REQUESTED", "STOCK_RECONCILIATION_REQUEST",
        f"Requested opening stock review for item {row['product_code']}",
        entity_id=request.id,
        details={"fiscal_year": payload.fiscal_year, "warehouse_id": payload.warehouse_id,
                 "product_id": payload.product_id, "requested_qty": str(payload.requested_qty),
                 "variance_qty": str(row["variance_qty"])},
    )
    db.commit()
    return {"id": request.id, "status": request.status, "requested_qty": request.requested_qty}

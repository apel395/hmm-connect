from datetime import date
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.stock_adjustment import StockAdjustment
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.stock_adjustment import (
    StockAdjustmentCreate,
    StockAdjustmentUpdate,
)
from app.services.location_access import apply_warehouse_scope
from app.services.stock_adjustment_service import StockAdjustmentService

router = APIRouter(prefix="/stock-adjustments", tags=["Stock Adjustments"])


def _paged(items, *, page: int, page_size: int, total: int):
    total_pages = ceil(total / page_size) if total else 0
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


def serialize_adjustment(adjustment: StockAdjustment):
    created_by = adjustment.created_by
    posted_by = adjustment.posted_by
    warehouse = adjustment.warehouse
    items = [
        {
            "id": item.id,
            "product_id": item.product_id,
            "product_code": item.product.code if item.product else None,
            "product_name": item.product.name if item.product else None,
            "system_quantity": item.system_quantity,
            "adjusted_quantity": item.adjusted_quantity,
            "delta_quantity": item.delta_quantity,
            "unit_cost": item.unit_cost,
            "uom": item.uom,
            "reason": item.reason,
            "line_value": item.line_value,
        }
        for item in sorted(adjustment.items, key=lambda row: row.id)
    ]
    return {
        "id": adjustment.id,
        "adjustment_number": adjustment.adjustment_number,
        "status": adjustment.status,
        "adjustment_date": adjustment.adjustment_date,
        "warehouse_id": adjustment.warehouse_id,
        "warehouse_code": warehouse.code if warehouse else None,
        "warehouse_name": warehouse.name if warehouse else None,
        "business_unit_id": adjustment.business_unit_id,
        "location_id": adjustment.location_id,
        "department_id": adjustment.department_id,
        "reason": adjustment.reason,
        "notes": adjustment.notes,
        "created_by_id": adjustment.created_by_id,
        "created_by_name": (created_by.full_name or created_by.username) if created_by else None,
        "posted_by_id": adjustment.posted_by_id,
        "posted_by_name": (posted_by.full_name or posted_by.username) if posted_by else None,
        "posted_at": adjustment.posted_at,
        "total_adjustment_value": adjustment.total_adjustment_value,
        "items": items,
    }


@router.get("")
def list_adjustments(
    status: str | None = Query(default=None, max_length=30),
    warehouse_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = apply_warehouse_scope(db.query(StockAdjustment), user)
    if status and status.upper() != "ALL":
        query = query.filter(StockAdjustment.status == status.upper())
    if warehouse_id:
        query = query.filter(StockAdjustment.warehouse_id == warehouse_id)
    if date_from:
        query = query.filter(StockAdjustment.adjustment_date >= date_from)
    if date_to:
        query = query.filter(StockAdjustment.adjustment_date <= date_to)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.join(Warehouse, Warehouse.id == StockAdjustment.warehouse_id)
        query = query.filter(
            or_(
                StockAdjustment.adjustment_number.ilike(term),
                StockAdjustment.reason.ilike(term),
                Warehouse.name.ilike(term),
            )
        )

    status_rows = (
        apply_warehouse_scope(db.query(StockAdjustment), user)
        .with_entities(StockAdjustment.status, func.count(StockAdjustment.id))
        .group_by(StockAdjustment.status)
        .all()
    )
    status_counts = {key: int(value) for key, value in status_rows}

    total = query.count()
    rows = (
        query.order_by(StockAdjustment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [serialize_adjustment(row) for row in rows]
    result = _paged(items, page=page, page_size=page_size, total=total)
    result["summary"] = {"status_counts": status_counts}
    return result


@router.post("", status_code=201)
def create_adjustment(
    data: StockAdjustmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return serialize_adjustment(
        StockAdjustmentService.create(db, data=data, user=user)
    )


@router.get("/{adjustment_id}")
def get_adjustment(
    adjustment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    adjustment = (
        apply_warehouse_scope(db.query(StockAdjustment), user)
        .filter(StockAdjustment.id == adjustment_id)
        .first()
    )
    if not adjustment:
        raise HTTPException(status_code=404, detail="Stock Adjustment not found")
    return serialize_adjustment(adjustment)


@router.put("/{adjustment_id}")
def update_adjustment(
    adjustment_id: int,
    data: StockAdjustmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    adjustment = (
        apply_warehouse_scope(db.query(StockAdjustment), user)
        .filter(StockAdjustment.id == adjustment_id)
        .first()
    )
    StockAdjustmentService._require(user, "inventory.adjust")
    if not adjustment:
        raise HTTPException(status_code=404, detail="Stock Adjustment not found")
    return serialize_adjustment(
        StockAdjustmentService.update(db, adjustment=adjustment, data=data, user=user)
    )


@router.post("/{adjustment_id}/post")
def post_adjustment(
    adjustment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    adjustment = (
        apply_warehouse_scope(db.query(StockAdjustment), user)
        .filter(StockAdjustment.id == adjustment_id)
        .first()
    )
    if not adjustment:
        raise HTTPException(status_code=404, detail="Stock Adjustment not found")
    return serialize_adjustment(
        StockAdjustmentService.post(db, adjustment_id=adjustment_id, user=user)
    )


@router.post("/{adjustment_id}/void")
def void_adjustment(
    adjustment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return serialize_adjustment(
        StockAdjustmentService.void(db, adjustment_id=adjustment_id, user=user)
    )
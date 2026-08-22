from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import require_roles
from app.models.stock_opname import StockOpname
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.stock_opname import StockOpnameCountUpdate, StockOpnameCreate
from app.services.document_context import document_context
from app.services.location_access import apply_location_scope, enforce_location_access
from app.services.stock_opname_service import StockOpnameService

router = APIRouter(prefix="/stock-opnames", tags=["Stock Opname"])
warehouse_user = require_roles("WAREHOUSE")


def _row(opname: StockOpname):
    variance = sum(
        (Decimal(item.variance_quantity or 0) for item in opname.items), Decimal("0")
    )
    return {
        "id": opname.id,
        "opname_number": opname.opname_number,
        "status": opname.status,
        "count_date": opname.count_date,
        "warehouse_id": opname.warehouse_id,
        "warehouse_code": opname.warehouse.code if opname.warehouse else None,
        "warehouse_name": opname.warehouse.name if opname.warehouse else None,
        "business_unit_id": opname.business_unit_id,
        "business_unit_name": (
            opname.business_unit.name if opname.business_unit else None
        ),
        "location_id": opname.location_id,
        "location_name": opname.location.name if opname.location else None,
        "department_id": opname.department_id,
        "department_name": opname.department.name if opname.department else None,
        "created_by_name": opname.created_by.full_name if opname.created_by else None,
        "total_items": len(opname.items),
        "total_variance_quantity": variance,
        "submitted_at": opname.submitted_at,
        "posted_at": opname.posted_at,
    }


def _detail(db: Session, opname: StockOpname, user):
    payload = {
        **_row(opname),
        "notes": opname.notes,
        "created_at": opname.created_at,
        "updated_at": opname.updated_at,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_code": item.product.code,
                "product_name": item.product.name,
                "uom": item.uom,
                "system_quantity": item.system_quantity,
                "physical_quantity": item.physical_quantity,
                "variance_quantity": item.variance_quantity,
                "unit_cost": item.unit_cost,
                "variance_value": Decimal(item.variance_quantity or 0)
                * Decimal(item.unit_cost or 0),
            }
            for item in opname.items
        ],
    }
    payload.update(document_context(db, "STOCK_OPNAME", opname.id, opname.status, user))
    return payload


@router.get("")
def listing(
    status: str | None = None,
    search: str | None = None,
    warehouse_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = apply_location_scope(db.query(StockOpname), StockOpname, user)
    if status and status.upper() != "ALL":
        query = query.filter(StockOpname.status == status.upper())
    if warehouse_id:
        query = query.filter(StockOpname.warehouse_id == warehouse_id)
    if search and search.strip():
        query = query.filter(
            or_(
                StockOpname.opname_number.ilike(f"%{search.strip()}%"),
                StockOpname.notes.ilike(f"%{search.strip()}%"),
            )
        )
    total = query.count()
    total_pages = ceil(total / page_size) if total else 0
    items = (
        query.order_by(StockOpname.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_row(row) for row in items],
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


@router.get("/{opname_id}")
def detail(
    opname_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    opname = db.get(StockOpname, opname_id)
    if not opname:
        raise HTTPException(404, "Stock Opname not found")
    enforce_location_access(user, opname.location_id)
    return _detail(db, opname, user)


@router.post("", status_code=201)
def create(
    data: StockOpnameCreate, db: Session = Depends(get_db), user=Depends(warehouse_user)
):
    return _detail(
        db, StockOpnameService.create(db=db, data=data, current_user=user), user
    )


@router.patch("/{opname_id}/count")
def count(
    opname_id: int,
    data: StockOpnameCountUpdate,
    db: Session = Depends(get_db),
    user=Depends(warehouse_user),
):
    return _detail(
        db,
        StockOpnameService.update_counts(
            db=db, opname_id=opname_id, data=data, current_user=user
        ),
        user,
    )


@router.post("/{opname_id}/submit")
def submit(opname_id: int, db: Session = Depends(get_db), user=Depends(warehouse_user)):
    return _detail(
        db,
        StockOpnameService.submit(db=db, opname_id=opname_id, current_user=user),
        user,
    )


@router.post("/{opname_id}/approve")
def approve(
    opname_id: int,
    data: ApprovalDecisionRequest | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return _detail(
        db,
        StockOpnameService.approve(
            db=db, opname_id=opname_id, data=data, current_user=user
        ),
        user,
    )


@router.post("/{opname_id}/reject")
def reject(
    opname_id: int,
    data: ApprovalDecisionRequest | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return _detail(
        db,
        StockOpnameService.reject(
            db=db, opname_id=opname_id, data=data, current_user=user
        ),
        user,
    )


@router.post("/{opname_id}/post")
def post(opname_id: int, db: Session = Depends(get_db), user=Depends(warehouse_user)):
    return _detail(
        db, StockOpnameService.post(db=db, opname_id=opname_id, current_user=user), user
    )

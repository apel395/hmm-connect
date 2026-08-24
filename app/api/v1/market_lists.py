from datetime import date
from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import is_superuser, require_permission
from app.models.business_unit import BusinessUnit
from app.models.department import Department
from app.models.location import Location
from app.models.market_list import MarketList
from app.models.user import User
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.market_list import MarketListConvertCreate, MarketListCreate
from app.services.activity_service import AuditService
from app.services.approval import reset_approval
from app.services.document_context import document_context, print_metadata
from app.services.location_access import apply_location_scope, require_location_access, resolve_location_id
from app.services.market_list_service import MarketListService


router = APIRouter(prefix="/market-lists", tags=["Market Lists"])
market_list_view_user = require_permission("market_list.view", "REQUESTER", "PURCHASING", "GENERAL_MANAGER", "AUDITOR")
market_list_create_user = require_permission("market_list.create", "REQUESTER")
market_list_edit_user = require_permission("market_list.edit", "REQUESTER")
market_list_submit_user = require_permission("market_list.submit", "REQUESTER")
market_list_approve_user = require_permission("market_list.approve", "GENERAL_MANAGER", "PURCHASING")
market_list_convert_user = require_permission("market_list.convert", "PURCHASING")

ACTIVE_STATUSES = {"DRAFT", "PENDING_APPROVAL", "APPROVED"}
HISTORY_STATUSES = {"CONVERTED", "REJECTED", "CANCELLED", "EXPIRED"}


def _organization_context(db: Session, market_list: MarketList) -> dict:
    business_unit = db.get(BusinessUnit, market_list.business_unit_id) if market_list.business_unit_id else None
    department = db.get(Department, market_list.department_id) if market_list.department_id else None
    location = db.get(Location, market_list.location_id) if market_list.location_id else None
    return {
        "business_unit_id": market_list.business_unit_id,
        "business_unit_name": business_unit.name if business_unit else None,
        "department_id": market_list.department_id,
        "department_name": department.name if department else None,
        "location_id": market_list.location_id,
        "location_name": location.name if location else None,
    }


def _scope(query, scope: str):
    if scope == "active":
        return query.filter(MarketList.status.in_(ACTIVE_STATUSES))
    if scope == "history":
        return query.filter(MarketList.status.in_(HISTORY_STATUSES))
    return query


def _row(db: Session, market_list: MarketList, requester_name: str | None = None) -> dict:
    return {
        "id": market_list.id,
        "ml_number": market_list.ml_number,
        "status": market_list.status,
        "request_date": market_list.request_date,
        "expiry_date": market_list.expiry_date,
        "requester_name": requester_name,
        "subtotal": market_list.subtotal,
        "tax_amount": market_list.tax_amount,
        "total_amount": market_list.total_amount,
        "source_type": market_list.source_type,
        "external_reference": market_list.external_reference,
        **_organization_context(db, market_list),
    }


def _detail(db: Session, market_list: MarketList, user) -> dict:
    requester = db.get(User, market_list.requested_by_id) if market_list.requested_by_id else None
    payload = {
        **_row(db, market_list, requester.full_name if requester else None),
        "notes": market_list.notes,
        "created_at": market_list.created_at,
        "updated_at": market_list.updated_at,
        "items": [{
            "id": item.id,
            "product_id": item.product_id,
            "product_code": item.product_code,
            "product_name": item.product_name,
            "uom": item.product_uom,
            "quantity": item.quantity,
            "estimated_price": item.estimated_price,
            "total_price": item.total_price,
            "tax_category": item.product.tax_category,
            "is_taxable": item.is_taxable,
            "tax_rate": item.tax_rate,
            "tax_amount": item.tax_amount,
            "line_total": Decimal(item.total_price) + Decimal(item.tax_amount or 0),
        } for item in market_list.items],
        "generated_purchase_orders": [
            {"id": order.id, "document_number": order.po_number, "status": order.status}
            for order in market_list.purchase_orders
        ],
    }
    payload.update(document_context(db, "MARKET_LIST", market_list.id, market_list.status, user))
    return payload


@router.get("")
def list_market_lists(
    scope: str = Query(default="active", pattern="^(active|history|all)$"),
    status: str | None = Query(default=None, max_length=30),
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(market_list_view_user),
):
    scoped = _scope(apply_location_scope(db.query(MarketList), MarketList.location_id, user), scope)
    status_counts = dict(scoped.with_entities(MarketList.status, func.count(MarketList.id)).group_by(MarketList.status).all())
    this_month_prefix = date.today().strftime("%Y-%m")
    this_month = scoped.filter(func.to_char(MarketList.request_date, "YYYY-MM") == this_month_prefix).count()
    query = _scope(
        apply_location_scope(
            db.query(MarketList, User.full_name).outerjoin(
                User, User.id == MarketList.requested_by_id
            ),
            MarketList.location_id,
            user,
        ),
        scope,
    )
    if status and status.upper() != "ALL":
        query = query.filter(MarketList.status == status.upper())
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(MarketList.ml_number.ilike(term), User.full_name.ilike(term)))
    total = query.count()
    rows = query.order_by(MarketList.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    total_pages = ceil(total / page_size) if total else 0
    return {
        "items": [_row(db, item, requester) for item, requester in rows],
        "page": page, "page_size": page_size, "total_items": total, "total_pages": total_pages,
        "has_next": page < total_pages, "has_previous": page > 1,
        "summary": {"status_counts": status_counts, "this_month": this_month},
    }


@router.get("/{market_list_id}")
def get_market_list(market_list_id: int, db: Session = Depends(get_db), user=Depends(market_list_view_user)):
    market_list = db.get(MarketList, market_list_id)
    if not market_list:
        raise HTTPException(status_code=404, detail="Market List not found")
    require_location_access(market_list.location_id, user)
    return _detail(db, market_list, user)


@router.get("/{market_list_id}/print")
def print_market_list(market_list_id: int, db: Session = Depends(get_db), user=Depends(market_list_view_user)):
    return {**get_market_list(market_list_id, db, user), "document_type": "Market List", **print_metadata(user)}


@router.post("", status_code=201)
def create_market_list(data: MarketListCreate, db: Session = Depends(get_db), user=Depends(market_list_create_user)):
    data.location_id = resolve_location_id(user, data.location_id)
    market_list = MarketListService.create(db=db, data=data, current_user=user)
    return _detail(db, market_list, user)


@router.put("/{market_list_id}")
@router.patch("/{market_list_id}")
def update_market_list(market_list_id: int, data: MarketListCreate, db: Session = Depends(get_db), user=Depends(market_list_edit_user)):
    existing = db.get(MarketList, market_list_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Market List not found")
    require_location_access(existing.location_id, user)
    data.location_id = resolve_location_id(user, data.location_id)
    market_list = MarketListService.update(db=db, market_list_id=market_list_id, data=data, current_user=user)
    return _detail(db, market_list, user)


@router.post("/{market_list_id}/reopen")
def reopen_market_list(market_list_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not is_superuser(user):
        raise HTTPException(status_code=403, detail="Only an administrator can reopen a Market List")
    market_list = db.get(MarketList, market_list_id)
    if not market_list:
        raise HTTPException(status_code=404, detail="Market List not found")
    if market_list.status == "DRAFT":
        raise HTTPException(status_code=409, detail="Market List is already draft")
    active_orders = [order for order in market_list.purchase_orders if order.status != "CANCELLED"]
    if active_orders:
        numbers = ", ".join(order.po_number for order in active_orders[:5])
        raise HTTPException(status_code=409, detail=f"Market List has active downstream Purchase Order(s): {numbers}")
    previous_status = market_list.status
    reset_approval(db, "MARKET_LIST", market_list.id)
    market_list.status = "DRAFT"
    AuditService.log(
        db=db, user=user, action="REOPEN", entity_type="MARKET_LIST", entity_id=market_list.id,
        summary=f"Reopened {market_list.ml_number} for correction", document_type="ML",
        document_number=market_list.ml_number, document_status="DRAFT",
        details={"previous_status": previous_status, "admin_override": True},
    )
    db.commit(); db.refresh(market_list)
    return _detail(db, market_list, user)


@router.post("/{market_list_id}/submit")
def submit_market_list(market_list_id: int, db: Session = Depends(get_db), user=Depends(market_list_submit_user)):
    existing = db.get(MarketList, market_list_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Market List not found")
    require_location_access(existing.location_id, user)
    market_list = MarketListService.submit(db=db, market_list_id=market_list_id, current_user=user)
    return _detail(db, market_list, user)


@router.post("/{market_list_id}/approve")
def approve_market_list(market_list_id: int, data: ApprovalDecisionRequest | None = None, db: Session = Depends(get_db), user=Depends(market_list_approve_user)):
    existing = db.get(MarketList, market_list_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Market List not found")
    require_location_access(existing.location_id, user)
    market_list = MarketListService.approve(db=db, market_list_id=market_list_id, data=data, current_user=user)
    return _detail(db, market_list, user)


@router.post("/{market_list_id}/reject")
def reject_market_list(market_list_id: int, data: ApprovalDecisionRequest | None = None, db: Session = Depends(get_db), user=Depends(market_list_approve_user)):
    existing = db.get(MarketList, market_list_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Market List not found")
    require_location_access(existing.location_id, user)
    market_list = MarketListService.reject(db=db, market_list_id=market_list_id, data=data, current_user=user)
    return _detail(db, market_list, user)


@router.post("/{market_list_id}/convert-to-po")
def convert_market_list(market_list_id: int, data: MarketListConvertCreate, db: Session = Depends(get_db), user=Depends(market_list_convert_user)):
    existing = db.get(MarketList, market_list_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Market List not found")
    require_location_access(existing.location_id, user)
    return MarketListService.convert_to_purchase_order(db=db, market_list_id=market_list_id, data=data, current_user=user)

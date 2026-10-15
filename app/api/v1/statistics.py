"""Actual/budget operational statistics, isolated from financial accounting."""
from math import ceil
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.dependencies.authorization import require_permission
from app.models.chart_of_account import ChartOfAccount
from app.models.location import Location
from app.models.statistical_value import StatisticalValue
from app.schemas.statistical_value import StatisticalValueInput
from app.services.audit import record_audit
from app.services.location_access import apply_location_scope, enforce_location_access
from app.services.organization_dimensions import validate_dimensions

router = APIRouter(prefix="/statistics", tags=["Statistics"])
view, manage = require_permission("finance.view"), require_permission("finance.manage")


def serialize(row):
    return {"id": row.id, "account_id": row.account_id, "account_code": row.account.account_number,
            "account_name": row.account.account_name, "period": str(row.period), "unit": row.unit,
            "location_id": row.location_id, "location_name": row.location.name,
            "department_id": row.department_id, "department_name": row.department.name if row.department else None,
            "actual": str(row.actual) if row.actual is not None else None,
            "budget": str(row.budget) if row.budget is not None else None,
            "variance": str(row.actual-row.budget) if row.actual is not None and row.budget is not None else None,
            "version": row.version}


@router.get("")
def listing(year: int = Query(2026, ge=2026, le=9999), location_id: int | None = None,
            department_id: int | None = None, search: str | None = Query(None, max_length=100),
            page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
            db: Session = Depends(get_db), user=Depends(view)):
    from datetime import date
    if location_id:
        enforce_location_access(user, location_id)
    query = apply_location_scope(db.query(StatisticalValue).join(ChartOfAccount), StatisticalValue, user)
    query = query.filter(StatisticalValue.period >= date(year,1,1), StatisticalValue.period <= date(year,12,1))
    if location_id:
        query = query.filter(StatisticalValue.location_id == location_id)
    if department_id:
        query = query.filter(StatisticalValue.department_id == department_id)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(ChartOfAccount.account_number.ilike(term), ChartOfAccount.account_name.ilike(term)))
    total = query.count()
    rows = query.options(joinedload(StatisticalValue.account), joinedload(StatisticalValue.location), joinedload(StatisticalValue.department)).order_by(StatisticalValue.period.desc(), ChartOfAccount.account_number, StatisticalValue.id).offset((page-1)*page_size).limit(page_size).all()
    return {"items": [serialize(row) for row in rows], "total_items": total, "total_pages": ceil(total/page_size), "page": page, "page_size": page_size}


@router.put("")
def save(data: StatisticalValueInput, db: Session = Depends(get_db), user=Depends(manage)):
    enforce_location_access(user, data.location_id)
    location = db.get(Location, data.location_id)
    if not location or not location.is_active:
        raise HTTPException(422, "Choose an active location")
    validate_dimensions(db, location.business_unit_id, data.location_id, data.department_id, True)
    # Account lock serializes same-metric inserts and protects a consistent UOM.
    account = db.query(ChartOfAccount).filter_by(id=data.account_id).with_for_update().first()
    if not account or not account.is_active or account.account_type != "STATISTIC" or account.account_number == "900":
        raise HTTPException(422, "Choose an active statistical detail account under 900")
    if db.query(ChartOfAccount).filter_by(parent_account_id=account.id, is_active=True).first():
        raise HTTPException(422, "Choose a statistical leaf account")
    existing_unit = db.query(StatisticalValue.unit).filter_by(account_id=account.id).first()
    if existing_unit and existing_unit[0] != data.unit:
        raise HTTPException(422, f"This metric uses {existing_unit[0]}; use a separate account for another unit")
    row = db.query(StatisticalValue).filter_by(account_id=data.account_id, period=data.period,
        location_id=data.location_id, department_id=data.department_id).first()
    if row and row.version != data.version:
        raise HTTPException(409, "This statistic changed. Refresh before editing")
    if not row and data.version is not None:
        raise HTTPException(409, "This statistic no longer exists. Refresh before editing")
    before = serialize(row) if row else None
    if not row:
        row = StatisticalValue(account_id=data.account_id, period=data.period, location_id=data.location_id,
            department_id=data.department_id, unit=data.unit, version=0)
        db.add(row)
    row.actual, row.budget = data.actual, data.budget
    row.version += 1
    row.updated_by_id = user.id
    db.flush()
    record_audit(db, user, "STATISTIC_SAVED", "STATISTIC", f"Saved statistical actual/budget {account.account_number}",
                 entity_id=row.id, before_data=before,
                 after_data={"account_id": account.id, "period": str(data.period), "unit": data.unit,
                             "actual": str(data.actual) if data.actual is not None else None,
                             "budget": str(data.budget) if data.budget is not None else None,
                             "location_id": data.location_id, "department_id": data.department_id})
    db.commit(); db.refresh(row)
    return serialize(row)

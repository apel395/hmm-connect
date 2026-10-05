from datetime import datetime, timezone
from decimal import Decimal
from math import ceil
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.authorization import require_permission
from app.models.budget import Budget, BudgetLine
from app.schemas.budget import BudgetCreate, BudgetUpdate, RejectInput
from app.services.audit import record_audit
from app.services.budget_service import BudgetService
from app.services.location_access import assigned_location_id, enforce_location_access, resolve_location_id
from app.api.v1.profit_loss import serialize

router = APIRouter(prefix="/budgets", tags=["Budgets"])
view, manage = require_permission("finance.view"), require_permission("finance.manage")


def get_budget(db, budget_id, user):
    budget = db.query(Budget).filter_by(id=budget_id).with_for_update().first()
    if not budget:
        raise HTTPException(404, "Budget not found")
    location = assigned_location_id(user)
    if location is not None and any(line.location_id != location for line in budget.lines):
        raise HTTPException(404, "Budget not found for this location")
    return budget


def validate_access(data, user):
    for line in data.lines:
        enforce_location_access(user, line.location_id)


@router.get("")
def listing(fiscal_year: int | None = None, status: str | None = None, search: str | None = None,
            location_id: int | None = None, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500),
            db: Session = Depends(get_db), user=Depends(view)):
    location = resolve_location_id(user, location_id)
    query = db.query(Budget)
    if fiscal_year is not None:
        query = query.filter(Budget.fiscal_year == fiscal_year)
    if status:
        query = query.filter(Budget.status == status)
    if search:
        query = query.filter(Budget.name.ilike(f"%{search.strip()}%"))
    if location is not None:
        query = query.filter(Budget.lines.any(BudgetLine.location_id == location))
    total = query.count()
    items = []
    for budget in query.order_by(Budget.fiscal_year.desc(), Budget.id.desc()).offset((page-1)*page_size).limit(page_size):
        scoped_lines = [l for l in budget.lines if location is None or l.location_id == location]
        item = BudgetService(db).serialize(budget)
        item.pop("lines")
        item["total_budget"] = sum((Decimal(l.budget_amount) for l in scoped_lines), Decimal(0))
        item["line_count"] = len(scoped_lines)
        if location is not None and len(scoped_lines) != len(budget.lines):
            item["allowed_actions"] = {}
        items.append(item)
    return serialize({"items": items, "total_items": total, "page": page, "page_size": page_size, "total_pages": ceil(total/page_size)})


@router.post("")
def create(data: BudgetCreate, db: Session = Depends(get_db), user=Depends(manage)):
    validate_access(data, user)
    try:
        budget = BudgetService(db).create(data, user)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    record_audit(db, user, "BUDGET_CREATED", "BUDGET", f"Created {budget.budget_number}", entity_id=budget.id)
    db.commit()
    return serialize(BudgetService(db).serialize(budget))


@router.get("/{budget_id}")
def detail(budget_id: int, db: Session = Depends(get_db), user=Depends(view)):
    budget = db.get(Budget, budget_id)
    if not budget:
        raise HTTPException(404, "Budget not found")
    location = assigned_location_id(user)
    result = BudgetService(db).serialize(budget)
    if location is not None:
        lines = [line for line in result["lines"] if line["location_id"] == location]
        if not lines:
            raise HTTPException(404, "Budget not found for this location")
        if len(lines) != len(result["lines"]):
            result["allowed_actions"] = {}
        result["lines"] = lines
        result["total_budget"] = sum((Decimal(line["budget_amount"]) for line in lines), Decimal(0))
    return serialize(result)


@router.patch("/{budget_id}")
def update(budget_id: int, data: BudgetUpdate, db: Session = Depends(get_db), user=Depends(manage)):
    budget = get_budget(db, budget_id, user)
    if budget.status != "DRAFT":
        raise HTTPException(409, "Only draft budgets can be edited")
    values = {"name": budget.name, "fiscal_year": budget.fiscal_year, "date_from": budget.date_from,
              "date_to": budget.date_to, "currency": budget.currency, "description": budget.description,
              "lines": [{"account_id": l.account_id, "month": l.month, "business_unit_id": l.business_unit_id,
                         "location_id": l.location_id, "department_id": l.department_id,
                         "budget_amount": l.budget_amount, "notes": l.notes} for l in budget.lines]}
    values.update(data.model_dump(exclude_unset=True))
    prepared = BudgetCreate(**values)
    validate_access(prepared, user)
    try:
        BudgetService(db).validate(prepared)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    for key, value in prepared.model_dump(exclude={"lines", "fiscal_year"}).items():
        setattr(budget, key, value)
    budget.lines.clear()
    db.flush()
    budget.lines = [BudgetLine(**l.model_dump()) for l in prepared.lines]
    record_audit(db, user, "BUDGET_UPDATED", "BUDGET", f"Updated {budget.budget_number}", entity_id=budget.id)
    db.commit()
    return serialize(BudgetService(db).serialize(budget))


@router.post("/{budget_id}/{action}")
def action(budget_id: int, action: str, data: RejectInput | None = None,
           db: Session = Depends(get_db), user=Depends(manage)):
    budget = get_budget(db, budget_id, user)
    transitions = {"submit": ("DRAFT", "SUBMITTED"), "approve": ("SUBMITTED", "APPROVED"),
                   "reject": ("SUBMITTED", "DRAFT"), "lock": ("APPROVED", "LOCKED")}
    if action == "cancel":
        if budget.status not in ("DRAFT", "SUBMITTED", "APPROVED"):
            raise HTTPException(409, "This budget cannot be cancelled")
        next_status = "CANCELLED"
    elif action in transitions and budget.status == transitions[action][0]:
        next_status = transitions[action][1]
    else:
        raise HTTPException(409, "Budget action is unavailable in its current status")
    if action in ("submit", "approve", "lock") and not budget.lines:
        raise HTTPException(422, "Budget requires at least one line")
    before = budget.status
    budget.status = next_status
    now = datetime.now(timezone.utc)
    if action in ("submit", "approve", "lock", "cancel"):
        setattr(budget, {"submit": "submitted_at", "approve": "approved_at", "lock": "locked_at", "cancel": "cancelled_at"}[action], now)
    if action == "approve":
        budget.approved_by_id = user.id
    record_audit(db, user, "BUDGET_" + action.upper(), "BUDGET", f"{action} {budget.budget_number}",
                 entity_id=budget.id, before_data={"status": before},
                 after_data={"status": next_status, "reason": data.reason if data else None})
    db.commit()
    return serialize(BudgetService(db).serialize(budget))

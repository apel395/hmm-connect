import calendar
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.models.amortization import Amortization
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.schemas.amortization import AmortizationCreate, AmortizationUpdate
from app.services.document_number import next_document_number
from app.services.organization_dimensions import validate_dimensions
from app.services.organization_access import resolve_organization_access
from app.services.asset_posting import post_asset_ledger


router = APIRouter(prefix="/amortizations", tags=["Amortization"])
ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def require_finance(user):
    if not has_permission(user, "finance.manage"):
        raise HTTPException(403, "Finance access required")


def validate_account(db: Session, account_id: int, account_type: str, label: str, credit_normal: bool = False):
    account = db.get(ChartOfAccount, account_id)
    if not account or not account.is_active or not account.is_posting or account.account_type != account_type:
        raise HTTPException(422, f"{label} must be an active posting {account_type} account")
    if credit_normal and account.normal_balance != "CREDIT":
        raise HTTPException(422, f"{label} must have CREDIT normal balance")
    return account


def serialize(item: Amortization):
    monthly = (Decimal(item.original_cost) / item.useful_life_months).quantize(CENT, rounding=ROUND_HALF_UP)
    return {
        "id": item.id,
        "amortization_number": item.amortization_number,
        "name": item.name,
        "category": item.category,
        "description": item.description,
        "start_date": item.start_date,
        "original_cost": item.original_cost,
        "useful_life_months": item.useful_life_months,
        "monthly_amortization": monthly,
        "months_posted": item.months_posted,
        "accumulated_amortization": item.accumulated_amortization,
        "net_book_value": item.net_book_value,
        "status": item.status,
        "business_unit_id": item.business_unit_id,
        "location_id": item.location_id,
        "department_id": item.department_id,
        "asset_account_id": item.asset_account_id,
        "accumulated_amortization_account_id": item.accumulated_amortization_account_id,
        "amortization_expense_account_id": item.amortization_expense_account_id,
        "notes": item.notes,
        "last_posted_at": item.last_posted_at,
        "can_post_next": item.status == "ACTIVE" and item.months_posted < item.useful_life_months and Decimal(item.net_book_value) > ZERO,
    }


def posting_date(item: Amortization) -> date:
    month_index = item.start_date.month - 1 + item.months_posted
    year = item.start_date.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, calendar.monthrange(year, month)[1])


@router.get("")
def list_amortizations(db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_finance(user)
    scope=resolve_organization_access(db,user)
    query=db.query(Amortization)
    for key,value in scope.items():
        if value is not None: query=query.filter(getattr(Amortization,key)==value)
    return [serialize(item) for item in query.order_by(Amortization.id.desc()).all()]


@router.post("", status_code=201)
def create_amortization(data: AmortizationCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_finance(user)
    scope=resolve_organization_access(db,user,location_id=data.location_id,business_unit_id=data.business_unit_id,department_id=data.department_id)
    data=data.model_copy(update=scope)
    validate_dimensions(db, data.business_unit_id, data.location_id, data.department_id, required=True)
    asset=validate_account(db, data.asset_account_id, "ASSET", "Amortizable asset account")
    if asset.account_number.startswith("100-600"):
        raise HTTPException(422,"Use Fixed Assets for account 100-600")
    if data.accumulated_amortization_account_id==data.asset_account_id and not asset.account_number.startswith("100-400"):
        raise HTTPException(422,"Direct cost reduction requires account 100-400")
    validate_account(db, data.accumulated_amortization_account_id, "ASSET", "Amortization credit account", data.accumulated_amortization_account_id != data.asset_account_id)
    validate_account(db, data.amortization_expense_account_id, "EXPENSE", "Amortization expense account")
    item = Amortization(
        amortization_number=next_document_number(db, "AMR", digits=6),
        accumulated_amortization=ZERO,
        net_book_value=data.original_cost,
        months_posted=0,
        status="ACTIVE",
        created_by_id=user.id,
        **data.model_dump(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.patch("/{amortization_id}")
def update_amortization(amortization_id: int, data: AmortizationUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_finance(user)
    item = db.get(Amortization, amortization_id)
    if not item:
        raise HTTPException(404, "Amortization record not found")
    resolve_organization_access(db,user,location_id=item.location_id,business_unit_id=item.business_unit_id,department_id=item.department_id)
    values = data.model_dump(exclude_unset=True)
    business_unit_id = values.get("business_unit_id", item.business_unit_id)
    location_id = values.get("location_id", item.location_id)
    department_id = values.get("department_id", item.department_id)
    resolve_organization_access(db,user,location_id=location_id,business_unit_id=business_unit_id,department_id=department_id)
    validate_dimensions(db, business_unit_id, location_id, department_id, required=True)
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.post("/{amortization_id}/post-next")
def post_next_amortization(amortization_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_finance(user)
    item = db.query(Amortization).filter(Amortization.id == amortization_id).with_for_update().first()
    if not item:
        raise HTTPException(404, "Amortization record not found")
    resolve_organization_access(db,user,location_id=item.location_id,business_unit_id=item.business_unit_id,department_id=item.department_id)
    if item.status != "ACTIVE" or item.months_posted >= item.useful_life_months or Decimal(item.net_book_value) <= ZERO:
        raise HTTPException(409, "No remaining amortization to post")

    standard_monthly = (Decimal(item.original_cost) / item.useful_life_months).quantize(CENT, rounding=ROUND_HALF_UP)
    amount = min(standard_monthly, Decimal(item.net_book_value))
    period_date = posting_date(item)
    entry = JournalEntry(
        journal_number=next_document_number(db, "JV", digits=8),
        posting_date=period_date,
        fiscal_year=period_date.year,
        fiscal_period=period_date.month,
        status="POSTED",
        document_type="AMORTIZATION",
        document_number=item.amortization_number,
        reference_type="AMORTIZATION",
        reference_id=item.id,
        description=f"Amortization {item.amortization_number} - {item.name}",
        created_by_id=user.id,
        posted_by_id=user.id,
        business_unit_id=item.business_unit_id,
        location_id=item.location_id,
        department_id=item.department_id,
    )
    db.add(entry)
    db.flush()
    db.add_all([
        JournalLine(
            journal_entry_id=entry.id,
            line_number=1,
            account_id=item.amortization_expense_account_id,
            debit=amount,
            credit=ZERO,
            description=entry.description,
            business_unit_id=item.business_unit_id,
            location_id=item.location_id,
            department_id=item.department_id,
        ),
        JournalLine(
            journal_entry_id=entry.id,
            line_number=2,
            account_id=item.accumulated_amortization_account_id,
            debit=ZERO,
            credit=amount,
            description=entry.description,
            business_unit_id=item.business_unit_id,
            location_id=item.location_id,
            department_id=item.department_id,
        ),
    ])
    db.flush()
    post_asset_ledger(db,entry,user)
    item.months_posted += 1
    item.accumulated_amortization = Decimal(item.accumulated_amortization) + amount
    item.net_book_value = max(ZERO, Decimal(item.original_cost) - Decimal(item.accumulated_amortization))
    item.last_posted_at = datetime.now(timezone.utc)
    if item.months_posted >= item.useful_life_months or Decimal(item.net_book_value) <= ZERO:
        item.status = "FULLY_AMORTIZED"
    db.commit()
    db.refresh(item)
    return {"amortization": serialize(item), "journal_entry_id": entry.id, "journal_number": entry.journal_number, "posted_amount": amount}

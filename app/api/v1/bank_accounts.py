from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.models.bank_account import BankAccount
from app.models.chart_of_account import ChartOfAccount
from app.schemas.bank_account import BankAccountInput
from app.services.organization_dimensions import validate_dimensions
from app.services.location_access import apply_location_scope, enforce_location_access, resolve_location_id

router = APIRouter(prefix="/bank-accounts", tags=["Bank Accounts"])


def access(user):
    if not has_permission(user, "finance.manage"):
        raise HTTPException(403, "Finance access required")


def validate(db: Session, data: BankAccountInput, exclude_id: int | None = None):
    validate_dimensions(db, data.business_unit_id, data.location_id, None, required=True)
    account = db.get(ChartOfAccount, data.coa_account_id)
    if not account or not account.is_active or not account.is_posting or account.account_type != "ASSET":
        raise HTTPException(422, "Linked COA must be an active posting asset account")
    if account.account_subtype not in {"BANK", "CASH", "PETTY_CASH"}:
        raise HTTPException(422, "Linked COA must be classified as BANK, CASH, or PETTY_CASH")
    query = db.query(BankAccount).filter(BankAccount.coa_account_id == data.coa_account_id)
    if exclude_id:
        query = query.filter(BankAccount.id != exclude_id)
    if query.first():
        raise HTTPException(409, "This COA is already linked to another bank account")


def serialize(row: BankAccount):
    return {
        "id": row.id,
        "bank_name": row.bank_name,
        "account_name": row.account_name,
        "account_number": row.account_number,
        "account_holder": row.account_holder,
        "currency": row.currency,
        "business_unit_id": row.business_unit_id,
        "business_unit_name": row.business_unit.name if row.business_unit else None,
        "location_id": row.location_id,
        "location_name": row.location.name if row.location else None,
        "coa_account_id": row.coa_account_id,
        "coa_account_code": row.coa_account.account_number if row.coa_account else None,
        "coa_account_name": row.coa_account.account_name if row.coa_account else None,
        "is_active": row.is_active,
    }


@router.get("")
def listing(active_only: bool = False, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    query = apply_location_scope(db.query(BankAccount), BankAccount, user)
    if active_only:
        query = query.filter(BankAccount.is_active.is_(True))
    return [serialize(row) for row in query.order_by(BankAccount.bank_name, BankAccount.account_name).all()]


@router.post("", status_code=201)
def create(data: BankAccountInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    data.location_id = resolve_location_id(user, data.location_id)
    validate(db, data)
    row = BankAccount(**data.model_dump())
    row.currency = row.currency.upper()
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.patch("/{bank_account_id}")
def update(bank_account_id: int, data: BankAccountInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    row = db.get(BankAccount, bank_account_id)
    if not row:
        raise HTTPException(404, "Bank account not found")
    enforce_location_access(user, row.location_id)
    data.location_id = resolve_location_id(user, data.location_id)
    validate(db, data, bank_account_id)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    row.currency = row.currency.upper()
    db.commit()
    db.refresh(row)
    return serialize(row)

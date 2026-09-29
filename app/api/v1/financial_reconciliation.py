from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.services.financial_reconciliation_service import FinancialReconciliationService
from app.services.location_access import resolve_location_id

router = APIRouter(prefix="/financial-reconciliation", tags=["Financial Reconciliation"])


def _access(user):
    if not has_permission(user, "finance.view"):
        raise HTTPException(403, "Finance access required")


@router.get("")
def report(date_from: date | None = None, date_to: date | None = None,
           db: Session = Depends(get_db), user=Depends(get_current_user)):
    _access(user)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "From date must not exceed To date")
    location_id = resolve_location_id(user, None)
    return FinancialReconciliationService(db).report(
        location_id=location_id, date_from=date_from, date_to=date_to,
    )

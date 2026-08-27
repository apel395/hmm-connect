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
def report(db: Session = Depends(get_db), user=Depends(get_current_user)):
    _access(user)
    location_id = resolve_location_id(user, None)
    return FinancialReconciliationService(db).report(location_id=location_id)

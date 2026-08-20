from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role
from app.services.financial_reconciliation_service import FinancialReconciliationService

router = APIRouter(prefix="/financial-reconciliation", tags=["Financial Reconciliation"])


def _access(user):
    if not has_any_role(user, "FINANCE", "AUDITOR", "GENERAL_MANAGER"):
        raise HTTPException(403, "Finance access required")


@router.get("")
def report(db: Session = Depends(get_db), user=Depends(get_current_user)):
    _access(user)
    return FinancialReconciliationService(db).report()

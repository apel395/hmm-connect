from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.chart_of_account import ChartOfAccount
from app.schemas.chart_of_account import ChartOfAccountResponse

router = APIRouter(prefix="/chart-of-accounts", tags=["Chart of Accounts"])


@router.get("", response_model=list[ChartOfAccountResponse])
def get_chart_of_accounts(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return (
        db.query(ChartOfAccount)
        .filter(ChartOfAccount.is_active.is_(True))
        .order_by(ChartOfAccount.account_number)
        .all()
    )

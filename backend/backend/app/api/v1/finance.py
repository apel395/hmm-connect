from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.account_payable import AccountPayable
from app.models.account_receipt import AccountReceipt
from app.schemas.finance import AccountPayableResponse, AccountReceiptResponse

router = APIRouter(prefix="/finance", tags=["Finance"])


@router.get("/account-payables", response_model=list[AccountPayableResponse])
def get_account_payables(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return db.query(AccountPayable).order_by(AccountPayable.id.desc()).all()


@router.get("/account-receipts", response_model=list[AccountReceiptResponse])
def get_account_receipts(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return db.query(AccountReceipt).order_by(AccountReceipt.id.desc()).all()

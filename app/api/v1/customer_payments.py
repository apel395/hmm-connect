from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import require_permission

from app.models.account_receivable import AccountReceivable
from app.models.customer_payment import CustomerPayment

from app.schemas.customer_payment import (
    CustomerPaymentCreate,
    CustomerPaymentResponse,
)

from app.services.document_number import next_document_number
from app.services.posting_service import PostingService

router = APIRouter(
    prefix="/customer-payments",
    tags=["Customer Payments"],
)


@router.post(
    "",
    response_model=CustomerPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_customer_payment(
    data: CustomerPaymentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_permission("finance.manage")
    ),
):

    from app.services.ar_invoice_service import receive_payment
    return receive_payment(db,data,current_user)


@router.get("/options")
def customer_receipt_options(db: Session = Depends(get_db), user=Depends(require_permission("finance.view"))):
    from app.services.ar_invoice_service import bank_choices
    return {"cash_accounts":[{"id":a.id,"code":a.account_number,"name":a.account_name} for a in bank_choices(db).all()]}

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import require_roles

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
        require_roles(
            "FINANCE",
            "ADMIN",
        )
    ),
):

    receivable = (
        db.query(AccountReceivable)
        .filter(AccountReceivable.id == data.account_receivable_id)
        .with_for_update()
        .first()
    )

    if not receivable:
        raise HTTPException(
            status_code=404,
            detail="Account receivable not found.",
        )

    outstanding = Decimal(receivable.outstanding_amount or 0)

    if outstanding <= 0:
        raise HTTPException(
            status_code=409,
            detail="Account receivable is already paid.",
        )

    if data.amount > outstanding:
        raise HTTPException(
            status_code=400,
            detail="Payment exceeds outstanding balance.",
        )

    payment = CustomerPayment(
        payment_number=next_document_number(db, "CP"),
        account_receivable_id=receivable.id,
        payment_date=data.payment_date,
        amount=data.amount,
        payment_method=data.payment_method,
        reference_number=data.reference_number,
    )

    db.add(payment)
    db.flush()

    receivable.received_amount += Decimal(data.amount)
    receivable.outstanding_amount -= Decimal(data.amount)

    if receivable.outstanding_amount <= 0:
        receivable.outstanding_amount = Decimal("0")
        receivable.status = "PAID"
    elif receivable.received_amount > 0:
        receivable.status = "PARTIAL"

    PostingService.post_customer_payment(
        db=db,
        payment=payment,
        receivable=receivable,
        user=current_user,
    )

    db.commit()

    db.refresh(payment)

    return payment

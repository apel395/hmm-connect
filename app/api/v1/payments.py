from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import require_roles
from app.services.posting_service import PostingService

from app.models.account_payable import AccountPayable
from app.models.payment import Payment

from app.schemas.payment import (
    PaymentCreate,
    PaymentResponse,
)

from app.services.activity_service import AuditService

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
)


def generate_payment_number(db: Session) -> str:
    count = db.query(Payment).count() + 1
    return f"PAY-{count:06d}"


@router.get(
    "",
    response_model=list[PaymentResponse],
)
def get_payments(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return (
        db.query(Payment)
        .order_by(Payment.id.desc())
        .all()
    )


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_roles(
            "FINANCE",
            "ADMIN",
        )
    ),
):
    payable = (
        db.query(AccountPayable)
        .filter(
            AccountPayable.id == data.account_payable_id
        )
        .first()
    )

    if not payable:
        raise HTTPException(
            status_code=404,
            detail="Account payable not found",
        )

    if payable.status == "PAID":
        raise HTTPException(
            status_code=400,
            detail="Invoice already paid",
        )

    outstanding = (
        payable.outstanding_amount
        if payable.outstanding_amount is not None
        else payable.amount
    )

    if data.amount <= Decimal("0"):
        raise HTTPException(
            status_code=400,
            detail="Payment amount must be greater than zero",
        )

    if data.amount > outstanding:
        raise HTTPException(
            status_code=400,
            detail="Payment exceeds outstanding balance",
        )

    payment = Payment(
        payment_number=generate_payment_number(db),
        account_payable_id=payable.id,
        payment_date=data.payment_date,
        amount=data.amount,
        payment_method=data.payment_method,
        reference_number=data.reference_number,
        status="PAID",
        created_by_id=current_user.id,
    )

    db.add(payment)

    payable.paid_amount += data.amount
    payable.outstanding_amount = payable.amount - payable.paid_amount
    payable.last_payment_date = data.payment_date

    if payable.outstanding_amount <= Decimal("0"):

        payable.outstanding_amount = Decimal("0")

        payable.payment_status = "PAID"

        payable.status = "PAID"

    elif payable.paid_amount > 0:

        payable.payment_status = "PARTIAL"

        payable.status = "PARTIAL"

    else:

        payable.payment_status = "UNPAID"

    db.flush()

    ####################################################
    # JOURNAL ENTRY
    ####################################################

    # Debit Account Payable (2100)

    PostingService.post_supplier_payment(
    db=db,
    payment=payment,
    payable=payable,
    user=current_user,
)

    AuditService.log(
        db=db,
        user=current_user,
        action="PAY",
        entity_type="PAYMENT",
        entity_id=payment.id,
        summary=f"Payment {payment.payment_number} created",
        document_type="PAYMENT",
        document_number=payment.payment_number,
        document_status=payable.status,
        reference_document=payable.invoice_number,
        details={
            "account_payable_id": payable.id,
            "supplier_id": payable.supplier_id,
            "amount": str(payment.amount),
            "remaining_balance": str(
                payable.outstanding_amount
            ),
            "payment_method": payment.payment_method,
            "reference_number": payment.reference_number,
        },
    )

    db.commit()
    db.refresh(payment)

    return payment
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies.auth import get_current_user

from app.models.account_payable import AccountPayable
from app.models.goods_receipt import GoodsReceipt
from app.models.journal_entry import JournalEntry
from app.models.payment import Payment
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_requisition import PurchaseRequisition

router = APIRouter(
    prefix="/audit-trail",
    tags=["Audit"],
)


@router.get("/{journal_id}")
def get_audit_trail(
    journal_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    journal = (
        db.query(JournalEntry)
        .options(
            joinedload(JournalEntry.lines)
        )
        .filter(
            JournalEntry.id == journal_id
        )
        .first()
    )

    if not journal:
        raise HTTPException(
            status_code=404,
            detail="Journal not found",
        )

    result = {
        "journal": journal,
        "goods_receipt": None,
        "purchase_order": None,
        "purchase_requisition": None,
        "account_payable": None,
        "payment": None,
    }

    if journal.reference_type == "GOODS_RECEIPT":

        gr = (
            db.query(GoodsReceipt)
            .filter(
                GoodsReceipt.id == journal.reference_id
            )
            .first()
        )

        result["goods_receipt"] = gr

        if gr:

            po = (
                db.query(PurchaseOrder)
                .filter(
                    PurchaseOrder.id == gr.purchase_order_id
                )
                .first()
            )

            result["purchase_order"] = po

            if po:

                if po.purchase_requisition:

                    result["purchase_requisition"] = po.purchase_requisition

                elif po.purchase_requisitions:

                    result["purchase_requisition"] = [
                        pr.id
                        for pr in po.purchase_requisitions
                    ]

            payable = (
                db.query(AccountPayable)
                .filter(
                    AccountPayable.goods_receipt_id == gr.id
                )
                .first()
            )

            result["account_payable"] = payable

            if payable:

                payment = (
                    db.query(Payment)
                    .filter(
                        Payment.account_payable_id == payable.id
                    )
                    .order_by(
                        Payment.payment_date.desc()
                    )
                    .all()
                )

                result["payment"] = payment

    elif journal.reference_type == "PAYMENT":

        payment = (
            db.query(Payment)
            .filter(
                Payment.id == journal.reference_id
            )
            .first()
        )

        result["payment"] = payment

        if payment:

            payable = (
                db.query(AccountPayable)
                .filter(
                    AccountPayable.id == payment.account_payable_id
                )
                .first()
            )

            result["account_payable"] = payable

            if payable:

                gr = (
                    db.query(GoodsReceipt)
                    .filter(
                        GoodsReceipt.id == payable.goods_receipt_id
                    )
                    .first()
                )

                result["goods_receipt"] = gr

                if gr:

                    po = (
                        db.query(PurchaseOrder)
                        .filter(
                            PurchaseOrder.id == gr.purchase_order_id
                        )
                        .first()
                    )

                    result["purchase_order"] = po

                    if po:

                        if po.purchase_requisition:

                            result["purchase_requisition"] = po.purchase_requisition

                        elif po.purchase_requisitions:

                            result["purchase_requisition"] = [
                                pr.id
                                for pr in po.purchase_requisitions
                            ]

    return result

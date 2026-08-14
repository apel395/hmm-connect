from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user

from app.models.goods_receipt import GoodsReceipt
from app.models.payment import Payment
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_requisition import PurchaseRequisition
from app.models.journal_entry import JournalEntry

router = APIRouter(
    prefix="/document-drilldown",
    tags=["Audit"],
)


@router.get("/{journal_id}")
def document_drilldown(
    journal_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    journal = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.id == journal_id,
        )
        .first()
    )

    if not journal:
        raise HTTPException(
            status_code=404,
            detail="Journal not found",
        )

    document = None

    if journal.reference_type == "GOODS_RECEIPT":

        document = (
            db.query(GoodsReceipt)
            .filter(
                GoodsReceipt.id == journal.reference_id,
            )
            .first()
        )

    elif journal.reference_type == "PAYMENT":

        document = (
            db.query(Payment)
            .filter(
                Payment.id == journal.reference_id,
            )
            .first()
        )

    elif journal.reference_type == "PURCHASE_ORDER":

        document = (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.id == journal.reference_id,
            )
            .first()
        )

    elif journal.reference_type == "PURCHASE_REQUISITION":

        document = (
            db.query(PurchaseRequisition)
            .filter(
                PurchaseRequisition.id == journal.reference_id,
            )
            .first()
        )

    return {
        "journal": journal,
        "document": document,
    }

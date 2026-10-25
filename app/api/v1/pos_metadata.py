from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.sales_transaction import SalesTransaction
from app.models.user import User
from app.services.document_number import next_document_number
from app.services.activity_service import ActivityService
from app.services.sales_transaction_service import SalesTransactionService

router = APIRouter(prefix="/pos-metadata", tags=["Point of Sales"])


class PosMetadataIn(BaseModel):
    transaction_type: str = Field(pattern="^(POS|INVOICE)$")
    table_number: str | None = Field(default=None, max_length=30)
    queue_number: str | None = Field(default=None, max_length=50)


@router.patch("/{sale_id}")
def update_pos_metadata(
    sale_id: int,
    data: PosMetadataIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    SalesTransactionService._require(user, "pos.sell")
    transaction = (
        SalesTransactionService.scoped_query(db, user)
        .filter(SalesTransaction.id == sale_id)
        .with_for_update()
        .first()
    )
    if not transaction:
        raise HTTPException(404, "POS sale not found")
    if transaction.status != "DRAFT":
        raise HTTPException(409, "Only draft POS sales can be configured")
    if transaction.cashier_session_id:
        from app.services.pos_operations import assert_open_order
        assert_open_order(db,transaction,user)
        if data.transaction_type != transaction.transaction_type or (data.table_number or None) != transaction.table_number:
            raise HTTPException(409, 'An outlet order cannot change type or table through metadata')
    if not transaction.cashier_session_id and data.transaction_type == "POS" and not data.table_number:
        raise HTTPException(422, "Table number is required for POS sales")

    before={"transaction_type":transaction.transaction_type,"table_number":transaction.table_number,"queue_number":transaction.queue_number}
    transaction.transaction_type = data.transaction_type
    transaction.table_number = data.table_number if data.transaction_type == "POS" else None

    if data.transaction_type == "INVOICE":
        if not transaction.transaction_number.startswith("INV-"):
            transaction.transaction_number = next_document_number(db, "INV", digits=5, day=True)
        transaction.queue_number = transaction.transaction_number
    else:
        transaction.queue_number = data.queue_number or transaction.transaction_number

    ActivityService.log(db=db,user=user,action='UPDATE',entity_type='SALES_TRANSACTION',entity_id=transaction.id,summary=f'Updated order metadata {transaction.transaction_number}',before_data=before,after_data={"transaction_type":transaction.transaction_type,"table_number":transaction.table_number,"queue_number":transaction.queue_number})
    db.commit()
    db.refresh(transaction)
    return {
        "id": transaction.id,
        "transaction_number": transaction.transaction_number,
        "transaction_type": transaction.transaction_type,
        "table_number": transaction.table_number,
        "queue_number": transaction.queue_number,
    }

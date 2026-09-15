from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.sales_transaction import SalesTransaction
from app.models.user import User
from app.services.document_number import next_document_number
from app.services.location_access import apply_warehouse_scope
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
        apply_warehouse_scope(db.query(SalesTransaction), user)
        .filter(SalesTransaction.id == sale_id)
        .first()
    )
    if not transaction:
        raise HTTPException(404, "POS sale not found")
    if transaction.status != "DRAFT":
        raise HTTPException(409, "Only draft POS sales can be configured")
    if data.transaction_type == "POS" and not data.table_number:
        raise HTTPException(422, "Table number is required for POS sales")

    transaction.transaction_type = data.transaction_type
    transaction.table_number = data.table_number if data.transaction_type == "POS" else None

    if data.transaction_type == "INVOICE":
        transaction.transaction_number = next_document_number(db, "INV", digits=5, day=True)
        transaction.queue_number = transaction.transaction_number
    else:
        transaction.queue_number = data.queue_number or transaction.transaction_number

    db.commit()
    db.refresh(transaction)
    return {
        "id": transaction.id,
        "transaction_number": transaction.transaction_number,
        "transaction_type": transaction.transaction_type,
        "table_number": transaction.table_number,
        "queue_number": transaction.queue_number,
    }

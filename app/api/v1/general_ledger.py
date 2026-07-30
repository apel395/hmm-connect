from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies.auth import get_current_user

from app.models.general_ledger import GeneralLedger

router = APIRouter(
    prefix="/general-ledger",
    tags=["General Ledger"],
)


@router.get("")
def get_general_ledger(
    account_id: int | None = Query(None),
    posting_date_from: date | None = Query(None),
    posting_date_to: date | None = Query(None),
    reference_type: str | None = Query(None),
    document_number: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    query = (
        db.query(GeneralLedger)
        .options(
            joinedload(GeneralLedger.account),
            joinedload(GeneralLedger.created_by),
        )
        .order_by(
            GeneralLedger.posting_date.desc(),
            GeneralLedger.id.desc(),
        )
    )

    if account_id:
        query = query.filter(
            GeneralLedger.account_id == account_id
        )

    if posting_date_from:
        query = query.filter(
            GeneralLedger.posting_date >= posting_date_from
        )

    if posting_date_to:
        query = query.filter(
            GeneralLedger.posting_date <= posting_date_to
        )

    if reference_type:
        query = query.filter(
            GeneralLedger.reference_type == reference_type
        )

    if document_number:
        query = query.filter(
            GeneralLedger.document_number.ilike(
                f"%{document_number}%"
            )
        )

    return query.all()
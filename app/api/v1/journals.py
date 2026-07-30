from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies.auth import get_current_user

from app.models.journal_entry import JournalEntry

router = APIRouter(
    prefix="/journals",
    tags=["Journal"],
)


@router.get("")
def get_journals(
    posting_date_from: date | None = Query(None),
    posting_date_to: date | None = Query(None),
    document_type: str | None = Query(None),
    document_number: str | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    query = (
        db.query(JournalEntry)
        .options(
            joinedload(JournalEntry.lines),
            joinedload(JournalEntry.created_by),
            joinedload(JournalEntry.posted_by),
        )
        .order_by(
            JournalEntry.posting_date.desc(),
            JournalEntry.id.desc(),
        )
    )

    if posting_date_from:
        query = query.filter(
            JournalEntry.posting_date >= posting_date_from
        )

    if posting_date_to:
        query = query.filter(
            JournalEntry.posting_date <= posting_date_to
        )

    if document_type:
        query = query.filter(
            JournalEntry.document_type == document_type
        )

    if document_number:
        query = query.filter(
            JournalEntry.document_number.ilike(
                f"%{document_number}%"
            )
        )

    if status:
        query = query.filter(
            JournalEntry.status == status
        )

    return query.all()

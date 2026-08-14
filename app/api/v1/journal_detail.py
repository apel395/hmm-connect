from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies.auth import get_current_user

from app.models.journal_entry import JournalEntry

router = APIRouter(
    prefix="/journal-detail",
    tags=["Journal"],
)


@router.get("/{journal_id}")
def get_journal_detail(
    journal_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    journal = (
        db.query(JournalEntry)
        .options(
            joinedload(JournalEntry.lines).joinedload("account"),
            joinedload(JournalEntry.created_by),
            joinedload(JournalEntry.posted_by),
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

    return journal

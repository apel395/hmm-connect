from datetime import date

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.document_sequence import DocumentSequence


def next_document_number(db: Session, prefix: str, *, digits: int = 4, day: bool = False) -> str:
    """Allocate a number using a locked sequence row in the caller's transaction."""
    stamp = date.today().strftime("%Y%m%d" if day else "%Y%m")
    key = f"{prefix}:{stamp}"
    db.execute(
        insert(DocumentSequence)
        .values(sequence_key=key, current_value=0)
        .on_conflict_do_nothing(index_elements=[DocumentSequence.sequence_key])
    )
    sequence = (
        db.query(DocumentSequence)
        .filter(DocumentSequence.sequence_key == key)
        .with_for_update()
        .one()
    )
    sequence.current_value += 1
    db.flush()
    return f"{prefix}-{stamp}-{sequence.current_value:0{digits}d}"

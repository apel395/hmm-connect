"""Recognize complete DRAFT journals alongside POSTED journals in accounting reads.

An open (DRAFT) journal contributes to reports only when balanced and nonzero.
VOID entries never contribute. Closing changes statuses, not amounts.
"""
from sqlalchemy import and_, func, or_, select

from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine


def recognized_journal_filter():
    balanced_drafts = (
        select(JournalLine.journal_entry_id)
        .group_by(JournalLine.journal_entry_id)
        .having(func.sum(JournalLine.debit) == func.sum(JournalLine.credit))
        .having(func.sum(JournalLine.debit) > 0)
    )
    return or_(
        JournalEntry.status == "POSTED",
        and_(JournalEntry.status == "DRAFT", JournalEntry.id.in_(balanced_drafts)),
    )

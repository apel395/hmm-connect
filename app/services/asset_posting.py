"""Post asset-generated journal lines to GL in the same database transaction."""
from datetime import datetime, timezone
from fastapi import HTTPException
from app.models.journal_line import JournalLine
from app.services.general_ledger import GeneralLedgerService
from app.services.fiscal_period_service import FiscalPeriodService


def post_asset_ledger(db, journal, user):
    FiscalPeriodService.validate_posting_date(db=db, posting_date=journal.posting_date)
    lines = db.query(JournalLine).filter(JournalLine.journal_entry_id == journal.id).order_by(JournalLine.line_number).all()
    for line in lines:
        if not (line.location_id or journal.location_id):
            raise HTTPException(409, 'Asset journal requires a work location')
        GeneralLedgerService.post(db, account_id=line.account_id, debit=line.debit, credit=line.credit,
            reference_type=journal.reference_type, reference_id=journal.reference_id,
            reference_number=journal.journal_number, document_type=journal.document_type,
            document_number=journal.document_number, description=line.description,
            posting_date=journal.posting_date, journal_source='JOURNAL', user_id=user.id)
    journal.posted_at = datetime.now(timezone.utc)
    db.flush()

"""Transactional accounting for physical inventory events."""
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException
from app.models.general_ledger import GeneralLedger
from app.services.general_ledger import GeneralLedgerService
from app.services.fiscal_period_service import FiscalPeriodService


def post_inventory_journal(db, journal, user):
    FiscalPeriodService.validate_posting_date(db, journal.posting_date)
    if not journal.location_id:
        raise HTTPException(409, 'Inventory journal requires a work location')
    debit = sum((Decimal(line.debit or 0) for line in journal.lines), Decimal('0'))
    credit = sum((Decimal(line.credit or 0) for line in journal.lines), Decimal('0'))
    if not journal.lines or debit != credit or debit <= 0:
        raise HTTPException(409, 'Inventory source journal must have balanced positive amounts')
    if db.query(GeneralLedger).filter(GeneralLedger.reference_type == journal.reference_type,
            GeneralLedger.reference_id == journal.reference_id).first():
        raise HTTPException(409, 'Inventory event is already recorded in GL')
    db.flush()
    for line in journal.lines:
        GeneralLedgerService.post(db, account_id=line.account_id, debit=line.debit, credit=line.credit,
            posting_date=journal.posting_date, reference_type=journal.reference_type,
            reference_id=journal.reference_id, reference_number=journal.journal_number,
            document_type=journal.document_type, document_number=journal.document_number,
            journal_source='JOURNAL', description=line.description, user_id=user.id)
    journal.status = 'POSTED'
    journal.posted_by_id = user.id
    journal.posted_at = datetime.now(timezone.utc)
    db.flush()

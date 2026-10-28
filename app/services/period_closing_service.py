"""System-generated, transactional month closing; never adjusts opening input."""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting_setting import AccountingSetting
from app.models.chart_of_account import ChartOfAccount
from app.models.fiscal_period import FiscalPeriod
from app.models.fiscal_year_close import FiscalYearClose
from app.models.general_ledger import GeneralLedger
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.audit import record_audit
from app.services.document_number import next_document_number
from app.services.general_ledger import GeneralLedgerService

CLOSING_SOURCES = ("PERIOD_CLOSE", "YEAR_END")
OPENING_SOURCES = ("OPENING_BALANCE", "OPENING_BALANCE_ADJUSTMENT")
ZERO = Decimal("0")


class PeriodClosingService:
    @staticmethod
    def period(db: Session, period_id: int) -> FiscalPeriod:
        period = db.query(FiscalPeriod).filter(FiscalPeriod.id == period_id).populate_existing().with_for_update().first()
        if not period:
            raise HTTPException(404, "Fiscal period not found")
        return period

    @staticmethod
    def earnings_account(db: Session) -> ChartOfAccount:
        setting = db.query(AccountingSetting).filter_by(setting_key="CURRENT_YEAR_EARNINGS_ACCOUNT").first()
        account = db.get(ChartOfAccount, setting.account_id) if setting else None
        if not account or not account.is_active or not account.is_posting or account.account_type != "EQUITY" or account.normal_balance != "CREDIT":
            raise HTTPException(409, "Configure an active credit equity account for CURRENT_YEAR_EARNINGS_ACCOUNT")
        if db.query(ChartOfAccount.id).filter(ChartOfAccount.parent_account_id == account.id).first():
            raise HTTPException(409, "Current-year earnings must use a posting account without child accounts")
        return account

    @classmethod
    def close(cls, db: Session, period_id: int, user) -> dict:
        with db.begin_nested():
            return cls._close(db,period_id,user)

    @classmethod
    def _close(cls, db: Session, period_id: int, user) -> dict:
        period = cls.period(db, period_id)
        if period.is_closed:
            return {"message": "Fiscal period is already closed", "closing_journal_ids": period.closing_journal_ids or []}
        if not period.is_open:
            raise HTTPException(409, "Open the period before closing it")
        if period.end_date.year != period.fiscal_year or period.start_date.year != period.fiscal_year:
            raise HTTPException(409, "Fiscal period dates must belong to its fiscal year")
        # Finalize all complete drafts before calculating the closing entries.
        # Incomplete/unbalanced drafts block close; no partial posting is committed.
        drafts = (db.query(JournalEntry)
            .filter(JournalEntry.posting_date.between(period.start_date, period.end_date),
                    JournalEntry.status == "DRAFT")
            .order_by(JournalEntry.id).with_for_update().all())
        from app.api.v1.journals import post_locked_journal
        for draft in drafts:
            if draft.reference_type in CLOSING_SOURCES:
                raise HTTPException(409, "System closing journal cannot be a draft")
            debit = sum((Decimal(line.debit or 0) for line in draft.lines), ZERO)
            credit = sum((Decimal(line.credit or 0) for line in draft.lines), ZERO)
            if not draft.lines or debit != credit or debit <= ZERO:
                raise HTTPException(409, f"Complete and balance draft journal {draft.journal_number} before closing {period.period_name}")
        # Close is transactional under the period lock.
        for draft in drafts:
            post_locked_journal(db, journal=draft, user=user, system_closing=True)
        db.flush()
        # This row lock is shared with normal posting validation. Journal activity
        # is read only after all previously admitted postings have committed.
        dimensions = [func.coalesce(getattr(JournalLine, name), getattr(JournalEntry, name))
                      for name in ("business_unit_id", "location_id", "department_id")]
        rows = db.query(ChartOfAccount.id, *dimensions,
                        func.sum(JournalLine.debit - JournalLine.credit).label("net"))\
            .join(JournalLine, JournalLine.account_id == ChartOfAccount.id)\
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)\
            .filter(JournalEntry.status == "POSTED",
                    JournalEntry.posting_date.between(period.start_date, period.end_date),
                    func.coalesce(JournalEntry.reference_type, 'MANUAL').notin_(CLOSING_SOURCES + OPENING_SOURCES),
                    ChartOfAccount.account_type.in_(("REVENUE", "INCOME", "EXPENSE")))\
            .group_by(ChartOfAccount.id, *dimensions).all()
        groups = defaultdict(list)
        for account_id, unit, location, department, net in rows:
            net = Decimal(net or ZERO)
            if net == ZERO:
                continue
            if location is None:
                raise HTTPException(409, "Operating journals without a location must be corrected before period closing")
            groups[(unit, location, department)].append((account_id, net))
        earnings = cls.earnings_account(db) if groups else None
        journal_ids = []
        for index, ((unit, location, department), balances) in enumerate(sorted(groups.items(), key=lambda x: str(x[0])), 1):
            document = f"PC-{period.fiscal_year}{period.fiscal_month:02d}-{period.id}-{index}"
            journal = JournalEntry(
                journal_number=next_document_number(db, "JV", digits=8),
                posting_date=period.end_date, status="POSTED", document_type="PERIOD_CLOSE",
                document_number=document, reference_type="PERIOD_CLOSE", reference_id=period.id,
                description=f"Automatic closing {period.period_name}", created_by_id=user.id,
                posted_by_id=user.id, fiscal_year=period.fiscal_year, fiscal_period=period.fiscal_month,
                business_unit_id=unit, location_id=location, department_id=department,
            )
            db.add(journal)
            db.flush()
            # Reverse actual signed operating balances. A loss and refund use
            # positive opposite-side amounts, never a negative debit or credit.
            amounts = [(account_id, -net) for account_id, net in balances]
            result = sum((net for _, net in balances), ZERO)
            if result:
                amounts.append((earnings.id, result))
            for line_number, (account_id, net) in enumerate(amounts, 1):
                debit, credit = max(net, ZERO), max(-net, ZERO)
                db.add(JournalLine(journal_entry_id=journal.id, line_number=line_number,
                    account_id=account_id, debit=debit, credit=credit,
                    description=journal.description, business_unit_id=unit,
                    location_id=location, department_id=department))
                GeneralLedgerService.post(db=db, account_id=account_id, debit=debit, credit=credit,
                    posting_date=period.end_date, journal_source="PERIOD_CLOSE", document_type="PERIOD_CLOSE",
                    document_number=document, reference_type="PERIOD_CLOSE", reference_id=period.id,
                    reference_number=journal.journal_number, description=journal.description, user_id=user.id, system_closing=True)
            journal_ids.append(journal.id)
        period.closing_journal_ids = journal_ids
        period.is_open, period.is_closed = False, True
        period.closed_at = datetime.now(timezone.utc).date()
        record_audit(db, user, "FISCAL_PERIOD_CLOSED", "FISCAL_PERIOD",
                     f"Closed {period.period_name}", entity_id=period.id,
                     after_data={"closing_journal_ids": journal_ids})
        db.flush()
        return {"message": "Fiscal period closed", "closing_journal_ids": journal_ids}

    @classmethod
    def reopen(cls, db: Session, period_id: int, user, reason: str) -> dict:
        if len(reason.strip())<3:raise HTTPException(422,"A reopening reason is required")
        with db.begin_nested():
            return cls._reopen(db,period_id,user,reason.strip())

    @classmethod
    def _reopen(cls, db: Session, period_id: int, user, reason: str) -> dict:
        period = cls.period(db, period_id)
        if period.is_open and not period.is_closed:
            return {"message": "Fiscal period is already open", "voided_closing_journal_ids": []}
        ids = period.closing_journal_ids or []
        for journal_id in ids:
            journal = db.query(JournalEntry).filter_by(id=journal_id).with_for_update().first()
            if not journal or journal.reference_type != "PERIOD_CLOSE" or journal.reference_id != period.id or journal.status != "POSTED":
                raise HTTPException(409, "Period closing evidence changed; inspection required")
            db.query(GeneralLedger).filter(
                GeneralLedger.reference_type == "PERIOD_CLOSE", GeneralLedger.reference_id == period.id,
                GeneralLedger.reference_number == journal.journal_number,
            ).delete(synchronize_session=False)
            journal.status, journal.voided_at = "VOID", datetime.now(timezone.utc)
        annual = db.query(FiscalYearClose).filter_by(fiscal_year=period.fiscal_year).first()
        if annual:
            annual.is_closed = False
        period.closing_journal_ids = []
        period.is_open, period.is_closed, period.closed_at = True, False, None
        record_audit(db, user, "FISCAL_PERIOD_REOPENED", "FISCAL_PERIOD",
                     f"Reopened {period.period_name}: {reason}", entity_id=period.id,
                     after_data={"reason": reason, "voided_closing_journal_ids": ids})
        db.flush()
        return {"message": "Fiscal period reopened", "voided_closing_journal_ids": ids}

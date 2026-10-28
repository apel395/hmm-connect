"""One accounting read contract: posted history plus complete open-period drafts.

Reads use JournalLine, never a union with physical GeneralLedger cache rows.
Finalization changes status only from a reporting perspective.
"""
from decimal import Decimal, InvalidOperation
from sqlalchemy import and_, case, func, or_, select
from app.models.chart_of_account import ChartOfAccount
from app.models.fiscal_period import FiscalPeriod
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine

FINANCIAL_TYPES = ('ASSET','LIABILITY','EQUITY','REVENUE','INCOME','EXPENSE')
MAX_AMOUNT = Decimal('10000000000000000')


def recognized_journal_filter():
    valid_line=and_(JournalLine.debit>=0,JournalLine.credit>=0,JournalLine.debit<MAX_AMOUNT,JournalLine.credit<MAX_AMOUNT,
        or_(and_(JournalLine.debit>0,JournalLine.credit==0),and_(JournalLine.credit>0,JournalLine.debit==0)),
        ChartOfAccount.is_active.is_(True),ChartOfAccount.is_posting.is_(True),ChartOfAccount.account_type.in_(FINANCIAL_TYPES))
    balanced=(select(JournalLine.journal_entry_id).outerjoin(ChartOfAccount,ChartOfAccount.id==JournalLine.account_id)
        .group_by(JournalLine.journal_entry_id).having(func.sum(JournalLine.debit)==func.sum(JournalLine.credit))
        .having(func.sum(JournalLine.debit)>0).having(func.count(JournalLine.id)==func.sum(case((valid_line,1),else_=0))))
    # A mismatched explicit dimension is incomplete; absent line dimensions inherit the header.
    bad_dimensions=select(JournalLine.id).where(JournalLine.journal_entry_id==JournalEntry.id,
        or_(and_(JournalLine.location_id.is_not(None),JournalLine.location_id!=JournalEntry.location_id),
            and_(JournalEntry.business_unit_id.is_not(None),JournalLine.business_unit_id.is_not(None),JournalLine.business_unit_id!=JournalEntry.business_unit_id))).correlate(JournalEntry).exists()
    open_period=select(FiscalPeriod.id).where(FiscalPeriod.start_date<=JournalEntry.posting_date,FiscalPeriod.end_date>=JournalEntry.posting_date,
        FiscalPeriod.is_open.is_(True),FiscalPeriod.is_closed.is_(False)).correlate(JournalEntry).exists()
    return or_(JournalEntry.status=='POSTED',and_(JournalEntry.status=='DRAFT',JournalEntry.location_id.is_not(None),
        JournalEntry.id.in_(balanced),~bad_dimensions,open_period))


def draft_problem(journal):
    if not journal.lines:return 'Journal has no lines'
    if journal.location_id is None:return 'Choose a work location'
    debit=credit=Decimal(0)
    for line in journal.lines:
        try:d,c=Decimal(line.debit),Decimal(line.credit)
        except (TypeError,InvalidOperation):return 'Enter valid debit and credit values'
        if not d.is_finite() or not c.is_finite() or min(d,c)<0 or max(d,c)>=MAX_AMOUNT or ((d>0)==(c>0)):
            return 'Each line requires one positive debit or credit'
        account=line.account
        if not account or not account.is_active or not account.is_posting or account.account_type not in FINANCIAL_TYPES:
            return 'Choose active financial posting accounts'
        if line.location_id not in (None,journal.location_id) or (journal.business_unit_id is not None and line.business_unit_id not in (None,journal.business_unit_id)):
            return 'Line organization dimensions must match the journal header'
        debit+=d;credit+=c
    if debit!=credit or debit<=0:return 'Complete and balance the journal'
    return None


def period_state(db, posting_date):
    period=db.query(FiscalPeriod).filter(FiscalPeriod.start_date<=posting_date,FiscalPeriod.end_date>=posting_date).first() if db else None
    return period, bool(period and period.is_open and not period.is_closed)

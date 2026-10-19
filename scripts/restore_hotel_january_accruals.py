from collections import Counter
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace
from sqlalchemy import or_
from app.api.v1.journals import post_locked_journal
from app.models.chart_of_account import ChartOfAccount
from app.models.general_ledger import GeneralLedger
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.audit import record_audit

# Complete original source entries: (COA, debit, credit).
EXPECTED = {
 1430: ('MAN-202610-000080', 'ACCRUED EXPENSES - 012026 HK', [
  ('700-500-107','6105000','0'), ('200-200-125','0','6105000'),
  ('700-500-104','4500000','0'), ('200-200-124','0','4410000'),
  ('200-400-103','0','90000'), ('700-500-141','2695917','0'),
  ('200-400-103','0','53918'), ('200-200-124','0','2641999')]),
 1431: ('MAN-202610-000081', 'ACCRUED EXPENSES - 012026 FO', [
  ('700-500-107','666287','0'), ('200-200-126','0','666287')]),
 1432: ('MAN-202610-000082', 'ACCRUED EXPENSES - 012026 A&G', [
  ('700-500-140','1500000','0'), ('200-400-103','0','30000'),
  ('200-200-124','0','1470000')]),
}

def restore(db):
    # Label maintenance truthfully; do not impersonate the original input user.
    actor = SimpleNamespace(id=None, full_name='User-authorized EC2 accrual restoration', roles=[])
    journals = db.query(JournalEntry).filter(JournalEntry.id.in_(EXPECTED)).order_by(JournalEntry.id).with_for_update().all()
    if {j.id for j in journals} != set(EXPECTED):
        raise ValueError('One or more target journals are missing')
    db.query(JournalLine).filter(JournalLine.journal_entry_id.in_(EXPECTED)).order_by(JournalLine.id).with_for_update().all()
    pending=[]
    for j in journals:
        number,document,lines=EXPECTED[j.id]
        if (j.journal_number,j.document_number,j.posting_date,j.reference_type,j.location_id) != (number,document,date(2026,1,31),'MANUAL',8):
            raise ValueError(f'Journal {j.id}: identity/date/source/location changed')
        if j.status not in ('VOID','POSTED'):
            raise ValueError(f'Journal {j.id}: unexpected status {j.status}')
        signature=lambda rows: Counter((code,D(debit),D(credit)) for code,debit,credit in rows)
        actual=signature((l.account.account_number,l.debit,l.credit) for l in j.lines)
        wanted=signature(lines)
        if actual != wanted:
            raise ValueError(f'Journal {j.id}: full account/debit/credit lines differ from January source. No changes committed. Actual: {list(actual.elements())}')
        if sum(D(l.debit) for l in j.lines) != sum(D(l.credit) for l in j.lines):
            raise ValueError(f'Journal {j.id}: original entry is not balanced')
        ledger=db.query(GeneralLedger).filter(or_(GeneralLedger.reference_number==j.journal_number,GeneralLedger.document_number==j.document_number)).with_for_update().all()
        if j.status=='POSTED':
            actual_gl=signature((db.get(ChartOfAccount,g.account_id).account_number,g.debit,g.credit) for g in ledger)
            if actual_gl != wanted or any(g.posting_date!=j.posting_date or g.reference_type!=j.reference_type or g.reference_id!=j.reference_id for g in ledger):
                raise ValueError(f'Journal {j.id}: posted GL does not match')
            print('ALREADY POSTED:',j.id,j.journal_number)
        else:
            if ledger:
                raise ValueError(f'Journal {j.id}: GL rows already exist; duplicate posting refused')
            pending.append(j)
    # Refuse another complete posted copy, including a larger combined journal.
    candidates=db.query(JournalEntry).filter(JournalEntry.posting_date==date(2026,1,31),JournalEntry.status=='POSTED',JournalEntry.id.notin_(EXPECTED)).with_for_update().all()
    for j in pending:
        wanted=Counter((l.account_id,D(l.debit),D(l.credit)) for l in j.lines)
        for other in candidates:
            if other.location_id!=8:continue
            actual=Counter((l.account_id,D(l.debit),D(l.credit)) for l in other.lines)
            if not (wanted-actual):
                raise ValueError(f'Journal {j.id}: same full entry already posted in {other.id}')
    for j in pending:
        before={'status':j.status,'voided_at':str(j.voided_at) if j.voided_at else None}
        j.status='DRAFT';j.voided_at=None
        post_locked_journal(db,journal=j,user=actor)
        record_audit(db,actor,'JOURNAL_RESTORED_FROM_VOID','JOURNAL_ENTRY',f'Restored original January accrual {j.journal_number} by user instruction',entity_id=j.id,before_data=before,after_data={'status':'POSTED'},reference_document=j.document_number)
        db.flush()
        ledger=db.query(GeneralLedger).filter(GeneralLedger.reference_number==j.journal_number,GeneralLedger.reference_type==j.reference_type,GeneralLedger.reference_id==j.reference_id).all()
        signature=lambda rows: Counter((account,D(debit),D(credit)) for account,debit,credit in rows)
        if signature((g.account_id,g.debit,g.credit) for g in ledger)!=signature((l.account_id,l.debit,l.credit) for l in j.lines):
            raise ValueError(f'Journal {j.id}: GL verification failed')
        print('POSTED:',j.id,j.journal_number)
    return len(pending)

if __name__=='__main__':
    from app.core.database import SessionLocal
    parser=argparse.ArgumentParser(description='Restore only the three verified January Hotel accrual journals.')
    parser.add_argument('--apply',action='store_true',help='Commit the verified journals; default rolls back.')
    args=parser.parse_args()
    db=SessionLocal()
    try:
        with db.begin():
            count=restore(db)
            if not args.apply: db.rollback()
        if args.apply:
            print(f'COMMITTED: {count} journals posted. Original dates, accounts, tax and amounts preserved.')
        else:
            print('DRY RUN: all changes rolled back. Use --apply to commit.')
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

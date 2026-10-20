"""User-authorized Dana Proyek remapping; preserves source amounts and bank lines."""
from pathlib import Path
import argparse
from collections import Counter
from datetime import date
from decimal import Decimal
import sys
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import func
from app.models.chart_of_account import ChartOfAccount
from app.models.general_ledger import GeneralLedger
from app.models.import_batch import ImportRow
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.location import Location
from app.services.accounting_unpost import unpost_journal
from app.api.v1.journals import post_locked_journal
from app.services.audit import record_audit
from app.services.hotel_pl_attribution import SOURCE_HASH

OLD='100-210-102'
NEW='750-100-104'
BANK='100-110-120'
# Original source row, original account, debit, credit. No direction changes.
JOURNALS={
 4417:('MAN-202610-003067','1153653',date(2026,1,30),[
  (24372,OLD,'487529220','0'),(24373,BANK,'0','487529220'),
  (24374,BANK,'0','100387408'),(24375,OLD,'100387408','0'),
  (24376,OLD,'39823524','0'),(24377,OLD,'51100000','0'),
  (24378,BANK,'0','51100000'),(24379,BANK,'0','39823524')]),
 4660:('MAN-202610-003310','1153977',date(2026,1,28),[
  (26447,BANK,'700000000','0'),(26448,OLD,'0','700000000')]),
}
ZERO=Decimal(0)


def net_profit(db):
    """Independent posted journal net, before and after, without report aliases."""
    location=func.coalesce(JournalLine.location_id,JournalEntry.location_id)
    return Decimal(db.query(func.coalesce(func.sum(JournalLine.credit-JournalLine.debit),0)).join(
        JournalEntry,JournalEntry.id==JournalLine.journal_entry_id).join(
        ChartOfAccount,ChartOfAccount.id==JournalLine.account_id).outerjoin(
        Location,Location.id==location).filter(
        JournalEntry.status=='POSTED',JournalEntry.posting_date.between(date(2026,1,1),date(2026,1,31)),
        location==8,func.coalesce(JournalLine.business_unit_id,JournalEntry.business_unit_id,Location.business_unit_id)==1,
        ChartOfAccount.account_type.in_(('REVENUE','INCOME','EXPENSE')),
        func.coalesce(JournalEntry.reference_type,'').notin_(('OPENING_BALANCE','OPENING_BALANCE_ADJUSTMENT','PERIOD_CLOSE','YEAR_END'))).scalar())


def gl_signature(rows):
    return Counter((r.account_id,Decimal(r.debit),Decimal(r.credit)) for r in rows)


def remap(db):
    actor=SimpleNamespace(id=None,full_name='User-authorized EC2 January mapping correction',roles=[])
    accounts={a.account_number:a for a in db.query(ChartOfAccount).filter(ChartOfAccount.account_number.in_((OLD,NEW,BANK))).all()}
    if set(accounts)!={OLD,NEW,BANK}:raise ValueError('Required registered COA is missing')
    if accounts[OLD].account_type!='ASSET' or accounts[NEW].account_type!='EXPENSE' or not accounts[NEW].is_active or not accounts[NEW].is_posting:
        raise ValueError('Required COA type or posting eligibility changed')
    journals=db.query(JournalEntry).filter(JournalEntry.id.in_(JOURNALS)).order_by(JournalEntry.id).with_for_update().all()
    if {j.id for j in journals}!=set(JOURNALS):raise ValueError('Target journal missing')
    db.query(JournalLine).filter(JournalLine.journal_entry_id.in_(JOURNALS)).with_for_update().all()
    pending=[]
    for journal in journals:
        number,register,posting_date,manifest=JOURNALS[journal.id]
        if (journal.journal_number,journal.external_reference,journal.posting_date,journal.status,journal.reference_type,journal.source_type,journal.location_id,journal.business_unit_id)!=(number,'HOTEL-JAN2026-REG-'+register,posting_date,'POSTED','MANUAL','JOURNAL_IMPORT',8,1):
            raise ValueError(f'Journal {journal.id}: identity, scope or status changed')
        lines=sorted(journal.lines,key=lambda l:l.line_number or 0)
        if [l.line_number for l in lines]!=list(range(1,len(manifest)+1)):raise ValueError(f'Journal {journal.id}: line order/count changed')
        evidence=db.query(ImportRow).filter(ImportRow.entity_type=='JOURNAL_ENTRY',ImportRow.entity_id==journal.id,ImportRow.import_batch_id==journal.import_batch_id,ImportRow.status=='IMPORTED').with_for_update().all()
        by_row={r.row_number:r for r in evidence}
        if len(by_row)!=len(evidence) or set(by_row)!={r[0] for r in manifest}:raise ValueError(f'Journal {journal.id}: import evidence changed')
        changes=[];states=set()
        for line,(source_row,code,debit,credit) in zip(lines,manifest):
            row=by_row[source_row];raw=row.raw_data_json or {};normalized=row.normalized_data_json or {}
            wanted=(Decimal(debit),Decimal(credit))
            if (Decimal(line.debit),Decimal(line.credit))!=wanted or (Decimal(str(raw.get('debit'))),Decimal(str(raw.get('credit'))))!=wanted:
                raise ValueError(f'Journal {journal.id} row {source_row}: source amounts changed')
            if raw.get('source_sha256')!=SOURCE_HASH or raw.get('register')!=register or raw.get('description','').strip().upper()!='DANA PROYEK':
                raise ValueError(f'Journal {journal.id} row {source_row}: source identity changed')
            if normalized.get('account_id')!=line.account_id or (Decimal(str(normalized.get('debit'))),Decimal(str(normalized.get('credit'))))!=wanted:
                raise ValueError(f'Journal {journal.id} row {source_row}: normalized mapping does not match')
            if line.location_id!=8 or line.business_unit_id!=1:raise ValueError(f'Journal {journal.id}: line scope changed')
            if code==OLD:
                if raw.get('legacy_code')!='591007' or normalized.get('legacy_code')!='591007' or line.account_id not in (accounts[OLD].id,accounts[NEW].id):
                    raise ValueError(f'Journal {journal.id} row {source_row}: Dana Proyek mapping changed')
                states.add(line.account_id)
                changes.append((line,row))
            elif line.account_id!=accounts[BANK].id:raise ValueError(f'Journal {journal.id}: bank counterpart changed')
        if len(states)!=1:raise ValueError(f'Journal {journal.id}: partially remapped lines need inspection')
        ledger=db.query(GeneralLedger).filter(GeneralLedger.reference_number==journal.journal_number).with_for_update().all()
        if gl_signature(ledger)!=gl_signature(lines) or any(g.reference_type!=journal.reference_type or g.reference_id!=journal.reference_id or g.posting_date!=journal.posting_date for g in ledger):
            raise ValueError(f'Journal {journal.id}: GL does not match original posted entry')
        if states=={accounts[NEW].id}:print('ALREADY MAPPED:',journal.id)
        else:pending.append((journal,changes))
    before=net_profit(db)
    expected_delta=sum((Decimal(line.credit)-Decimal(line.debit) for _,changes in pending for line,_ in changes),ZERO)
    for journal,changes in pending:
        audit_before=[{'line_id':line.id,'account_id':line.account_id,'source_row':row.row_number,'normalized_mapping':row.normalized_data_json} for line,row in changes]
        unpost_journal(db,journal=journal,user=actor,commit=False)
        for line,row in changes:
            original=dict(row.normalized_data_json)
            line.account_id=accounts[NEW].id
            normalized=dict(original)
            normalized.setdefault('original_account_id',original['account_id'])
            normalized.update(account_id=accounts[NEW].id,account_code=NEW,mapping_revision='USER_APPROVED_DANA_PROYEK_TO_BOD_20261020')
            row.normalized_data_json=normalized
        db.flush()
        post_locked_journal(db,journal=journal,user=actor)
        record_audit(db,actor,'JOURNAL_ACCOUNT_MAPPING_CORRECTED','JOURNAL_ENTRY',f'Remapped January Dana Proyek from {OLD} to {NEW} by user instruction',entity_id=journal.id,before_data={'lines':audit_before},after_data={'account_id':accounts[NEW].id,'account_code':NEW,'amounts_and_bank_lines_unchanged':True})
        db.flush()
        ledger=db.query(GeneralLedger).filter(GeneralLedger.reference_number==journal.journal_number,GeneralLedger.reference_type==journal.reference_type,GeneralLedger.reference_id==journal.reference_id).all()
        if gl_signature(ledger)!=gl_signature(journal.lines):raise ValueError('Corrected GL failed verification')
        print('REMAPPED AND REPOSTED:',journal.id,journal.journal_number)
    after=net_profit(db)
    if after-before!=expected_delta:raise ValueError(f'Unexpected NOP change: {after-before}; expected {expected_delta}')
    return {'journals_changed':len(pending),'lines_changed':sum(len(c) for _,c in pending),'NOP_before':str(before),'NOP_after':str(after),'NOP_change':str(after-before),'bank_interest_journals_changed':False}


def main():
    import json
    from app.core.database import SessionLocal
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args();db=SessionLocal()
    try:
        with db.begin():
            result=remap(db)
            if not args.apply:db.rollback()
        print(json.dumps(result,indent=2))
        print('COMMITTED. Bank receipts, source amounts and opening balances preserved.' if args.apply else 'DRY RUN: all changes rolled back. Use --apply to commit.')
    except Exception:
        db.rollback();raise
    finally:db.close()


if __name__=='__main__':main()

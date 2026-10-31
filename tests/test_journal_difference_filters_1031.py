from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.api.v1 import journals
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.chart_of_account import ChartOfAccount
from app.models.department import Department
from test_journal_scope_and_copy import data, ADMIN


def listing(db, **filters):
    params=dict(page=1,page_size=1,search=None,status=None,date_from=None,date_to=None,
        reference_type=None,account_id=None,supplier_id=None,location_id=None,business_unit_id=None,
        department_id=None,balance_state='ALL',difference_amount=None,db=db,user=ADMIN)
    params.update(filters)
    return journals.listing(**params)


def prepare(data):
    db,hotel,project,hloc,ploc=data
    account=db.query(ChartOfAccount).first()
    db.query(JournalLine).delete();db.query(JournalEntry).delete();db.flush()
    other=ChartOfAccount(account_number='100-FILTER',account_name='Cash',account_type='ASSET',normal_balance='DEBIT',is_posting=True,is_active=True)
    department=Department(code='FILTER',name='Accounting',business_unit_id=hotel.id)
    db.add_all([other,department]);db.flush()
    for number,debit,credit,status,location,unit,day in [
        ('PLUS',45001,1,'POSTED',hloc,hotel,1),('MINUS',1,45001,'POSTED',hloc,hotel,2),
        ('BALANCED',100,100,'DRAFT',hloc,hotel,3),('VOID',90000,1,'VOID',ploc,project,4)]:
        row=JournalEntry(journal_number=number,posting_date=date(2026,1,day),status=status,
            reference_type='MANUAL',reference_id=0,location_id=location.id,business_unit_id=unit.id)
        row.lines=[JournalLine(account_id=account.id,debit=debit,credit=0,department_id=department.id),
                   JournalLine(account_id=other.id,debit=0,credit=credit)]
        db.add(row)
    db.commit()
    return db,hotel,project,hloc,ploc,account,other,department


def test_absolute_difference_both_signs_and_filtered_totals_before_pagination(data):
    db,*_=prepare(data)
    result=listing(db,balance_state='UNBALANCED',difference_amount=Decimal('45000'))
    assert result['total_items']==2 and len(result['items'])==1
    assert result['summary']==dict(total_debit=Decimal('45002'),total_credit=Decimal('45002'),difference=Decimal('0'))
    assert abs(result['items'][0]['difference'])==45000
    second=listing(db,page=2,balance_state='UNBALANCED',difference_amount=Decimal('45000'))
    assert second['items'][0]['id']!=result['items'][0]['id']
    assert second['summary']==result['summary']


def test_balanced_filter_and_combined_account_department_date_status_scope(data):
    db,hotel,_,hloc,_,account,_,department=prepare(data)
    result=listing(db,balance_state='BALANCED')
    assert result['total_items']==1 and result['items'][0]['journal_number']=='BALANCED'
    result=listing(db,balance_state='UNBALANCED',difference_amount=Decimal('45000'),
        status='POSTED',business_unit_id=hotel.id,location_id=hloc.id,account_id=account.id,
        department_id=department.id,date_from=date(2026,1,2),date_to=date(2026,1,2),reference_type='MANUAL')
    assert result['total_items']==1 and result['items'][0]['journal_number']=='MINUS'
    # Account/department are journal membership filters, not partial line totals.
    assert result['summary']['total_debit']==1 and result['summary']['total_credit']==45001


def test_difference_filter_preserves_location_access_and_does_not_write(data):
    db,_,_,hloc,*_=prepare(data)
    before=[(j.id,j.status,[(l.debit,l.credit) for l in j.lines]) for j in db.query(JournalEntry).all()]
    user=SimpleNamespace(id=2,roles=[],default_location_id=hloc.id,location_id=hloc.id)
    result=listing(db,user=user,balance_state='UNBALANCED',page_size=100)
    assert {j['journal_number'] for j in result['items']}=={'PLUS','MINUS'}
    assert before==[(j.id,j.status,[(l.debit,l.credit) for l in j.lines]) for j in db.query(JournalEntry).all()]
    assert listing(db,difference_amount=Decimal('999999'))['summary']['difference']==0


def test_invalid_date_range_or_difference_is_rejected(data):
    db,*_=data
    for args in [dict(difference_amount=Decimal('-1')),dict(date_from=date(2026,2,1),date_to=date(2026,1,1))]:
        with pytest.raises(HTTPException) as error:listing(db,**args)
        assert error.value.status_code==422

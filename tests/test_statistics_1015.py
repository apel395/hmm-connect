from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_stock_opname_functional import stock_db
from app.api.v1.statistics import save, listing
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.general_ledger import GeneralLedger
from app.models.statistical_value import StatisticalValue
from app.schemas.statistical_value import StatisticalValueInput
from app.schemas.chart_of_account import ChartOfAccountCreate, ChartOfAccountUpdate
from app.services.chart_of_account_service import ChartOfAccountService
from app.services.general_ledger import GeneralLedgerService


def metric(db):
    service=ChartOfAccountService(db)
    header=service.create(ChartOfAccountCreate(account_code='900',account_name='Statistik',account_type='STATISTIC'))
    child=service.create(ChartOfAccountCreate(account_code='900-100',account_name='Rooms Sold',account_type='STATISTIC',parent_account_id=header.id))
    db.commit()
    return child


def payload(account, user, **kwargs):
    return StatisticalValueInput(account_id=account.id,period=date(2026,10,1),location_id=user.location_id,
        department_id=user.default_department_id,unit='room',actual=Decimal('0'),budget=Decimal('120'),**kwargs)


def test_statistics_save_zero_budget_version_and_no_financial_effect(stock_db):
    db, _, user, *_=stock_db
    account=metric(db)
    assert account.is_posting is False
    data=payload(account,user)
    result=save(data,db,user)
    assert result['actual']=='0.0000' and result['variance']=='-120.0000'
    assert db.query(JournalEntry).count()==db.query(GeneralLedger).count()==0
    data.version=result['version'];data.actual=Decimal('100')
    assert save(data,db,user)['variance']=='-20.0000'
    with pytest.raises(HTTPException) as conflict:save(data,db,user)
    assert conflict.value.status_code==409
    db.rollback()
    assert db.query(StatisticalValue).count()==1
    data.version=2; data.actual=None
    assert save(data,db,user)['actual'] is None
    with pytest.raises(HTTPException) as blocked:
        GeneralLedgerService.post(db,account_id=account.id,debit=10,reference_type='MANUAL',reference_id=1,reference_number='TEST',description='No',user_id=user.id)
    assert blocked.value.status_code==422
    assert db.query(GeneralLedger).count()==0


def test_statistics_scope_unit_and_900_validation(stock_db):
    db, _, user, *_=stock_db
    account=metric(db);data=payload(account,user);result=save(data,db,user)
    data.unit='PORTION';data.period=date(2026,11,1)
    with pytest.raises(HTTPException) as unit:save(data,db,user)
    assert unit.value.status_code==422
    db.rollback()
    data.unit='ROOM';data.location_id=999
    with pytest.raises(HTTPException) as access:save(data,db,user)
    assert access.value.status_code==404
    result=listing(year=2026,location_id=None,department_id=None,search=None,page=1,page_size=50,db=db,user=user)
    assert result['total_items']==1
    service=ChartOfAccountService(db)
    with pytest.raises(HTTPException):service.update(account.id,ChartOfAccountUpdate(account_type='ASSET'))
    with pytest.raises(HTTPException):service.create(ChartOfAccountCreate(account_code='900-200',account_name='Bad',account_type='ASSET'))
    with pytest.raises(HTTPException):service.create(ChartOfAccountCreate(account_code='800-200',account_name='Bad statistic',account_type='STATISTIC',parent_account_id=account.parent_account_id))
    assert db.query(StatisticalValue).count()==1


def test_statistical_input_does_not_silently_round_or_default():
    for changes in ({'actual':None,'budget':None},{'actual':'1.00001'},{'unit':' '},{'period':date(2025,12,1)},{'period':date(2026,10,2)}):
        values=dict(account_id=1,period=date(2026,10,1),location_id=1,unit='ROOM',actual='1',budget=None)
        values.update(changes)
        with pytest.raises(ValidationError):StatisticalValueInput(**values)


def test_migration_creates_header_and_nullable_department_unique_key(stock_db):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy.exc import IntegrityError
    db, _, user, *_ = stock_db
    bind=db.connection()
    StatisticalValue.__table__.drop(bind)
    path=Path(__file__).resolve().parents[1]/'alembic/versions/20261015_statistics.py'
    spec=importlib.util.spec_from_file_location('stat_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with Operations.context(MigrationContext.configure(bind)):
        module.upgrade()
    header=db.query(ChartOfAccount).filter_by(account_number='900').one()
    assert header.account_type=='STATISTIC' and not header.is_posting
    account=ChartOfAccountService(db).create(ChartOfAccountCreate(account_code='900-100',account_name='Guest Count',account_type='STATISTIC',parent_account_id=header.id))
    common=dict(account_id=account.id,period=date(2026,10,1),location_id=user.location_id,department_id=None,unit='GUEST',actual=10,version=1,updated_by_id=user.id)
    db.add(StatisticalValue(**common));db.flush()
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(StatisticalValue(**common));db.flush()

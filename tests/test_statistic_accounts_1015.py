from test_stock_opname_functional import stock_db
from fastapi import HTTPException
import pytest
from app.schemas.chart_of_account import ChartOfAccountCreate, ChartOfAccountUpdate
from app.services.chart_of_account_service import ChartOfAccountService
from app.services.general_ledger import GeneralLedgerService


def test_statistic_accounts_are_not_financial_posting_accounts(stock_db):
    db, _, user, *_ = stock_db
    service=ChartOfAccountService(db)
    header=service.create(ChartOfAccountCreate(account_code='900',account_name='Statistik',account_type='STATISTIC'))
    header.is_system=True
    child=service.create(ChartOfAccountCreate(account_code='900-100',account_name='Room Nights',account_type='STATISTIC',parent_account_id=header.id,is_posting=True))
    assert not child.is_posting and child.normal_balance=='DEBIT'
    assert service.update(header.id,ChartOfAccountUpdate(account_name='Statistics')).account_name=='Statistics'
    with pytest.raises(HTTPException):service.update(child.id,ChartOfAccountUpdate(account_type='ASSET'))
    with pytest.raises(HTTPException):service.create(ChartOfAccountCreate(account_code='900-200',account_name='Invalid',account_type='ASSET'))
    with pytest.raises(HTTPException) as rejected:
        GeneralLedgerService.post(db,account_id=child.id,debit=1,reference_type='MANUAL',reference_id=1,reference_number='TEST',description='Cannot post',user_id=user.id)
    assert rejected.value.status_code==422

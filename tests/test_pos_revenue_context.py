from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from app.api.v1.sales import pos_revenue_accounts
from app.models.accounting_setting import AccountingSetting
from app.models.chart_of_account import ChartOfAccount
from app.models.item_department import ItemDepartment
from app.models.journal_line import JournalLine
from app.models.sales_transaction import SalesTransaction
from app.schemas.sales_transaction import SalesTransactionCreate, SalesTransactionPost
from app.services.sales_transaction_service import SalesTransactionService as Service
from test_pos_sell_catalog_1021 import products
from test_finance_delivery_1007 import db, ADMIN


def accounts(s):
    rows=[]
    for code,kind,normal,posting in [('400-110-100','REVENUE','CREDIT',True),('400-100-100','REVENUE','CREDIT',True),('760-100-100','REVENUE','CREDIT',True),('400-110','REVENUE','CREDIT',False),('700-TEST','EXPENSE','DEBIT',True)]:
        r=ChartOfAccount(account_number=code,account_name=code,account_type=kind,normal_balance=normal,is_posting=posting,is_active=True)
        s.add(r);rows.append(r)
    s.commit();return rows


def test_chosen_revenue_posts_without_global_mapping_and_master_sets_context(db,monkeypatch):
    s,unit,loc,dept,base=db
    rev,*_=accounts(s)
    p,_,_=products(s);p.sales_location_id=loc.id;p.sales_business_unit_id=unit.id;p.service_charge_rate=0
    s.add(ItemDepartment(product_id=p.id,department_id=dept.id))
    s.add(AccountingSetting(setting_key='POS_CASH_ACCOUNT',account_id=base[2].id));s.commit()
    monkeypatch.setattr('app.services.sales_transaction_service.ActivityService.log',lambda **kw:None)
    tx=Service.create(s,data=SalesTransactionCreate(revenue_account_id=rev.id,sale_date=date(2026,1,5),items=[dict(product_id=p.id,quantity=2)]),user=ADMIN)
    assert (tx.location_id,tx.department_id,tx.business_unit_id)==(loc.id,dept.id,unit.id)
    assert tx.revenue_account_id==rev.id
    from app.api.v1.pos_metadata import PosMetadataIn, update_pos_metadata
    numbers=[]
    monkeypatch.setattr('app.api.v1.pos_metadata.next_document_number',lambda *args,**kwargs: numbers.append(1) or 'INV-TEST-1')
    metadata=PosMetadataIn(transaction_type='INVOICE')
    update_pos_metadata(tx.id,metadata,s,ADMIN)
    update_pos_metadata(tx.id,metadata,s,ADMIN)
    assert tx.transaction_number=='INV-TEST-1' and len(numbers)==1
    tx.transaction_type='POS';s.commit()
    tx=Service.post(s,transaction_id=tx.id,data=SalesTransactionPost(payment_received=200),user=ADMIN)
    assert s.query(JournalLine).filter_by(account_id=rev.id).one().credit==D(200)
    assert len(pos_revenue_accounts(loc.id,s,ADMIN))==2 # canonical catering account + legacy posting 400


def test_wrong_unit_nonoperating_header_and_expense_choices_are_rejected(db,monkeypatch):
    s,unit,loc,dept,_=db
    rev,hotel,other,header,expense=accounts(s)
    p,_,_=products(s);p.sales_location_id=loc.id;s.commit()
    monkeypatch.setattr('app.services.sales_transaction_service.ActivityService.log',lambda **kw:None)
    for invalid in (hotel,other,header,expense):
        with pytest.raises(HTTPException):
            Service.create(s,data=SalesTransactionCreate(revenue_account_id=invalid.id,items=[dict(product_id=p.id,quantity=1)]),user=ADMIN)
    assert s.query(SalesTransaction).count()==0
    choices=pos_revenue_accounts(loc.id,s,ADMIN)
    assert rev.id in {r['id'] for r in choices}
    assert not {hotel.id,other.id,header.id,expense.id}&{r['id'] for r in choices}
    limited=SimpleNamespace(**{**vars(ADMIN),'roles':[],'default_location_id':999})
    with patch.object(Service,'_require'),pytest.raises(HTTPException): pos_revenue_accounts(loc.id,s,limited)


def test_filters_cannot_retag_menu_master_context(db,monkeypatch):
    s,unit,loc,dept,_=db
    p,_,_=products(s);p.sales_location_id=loc.id
    s.add(ItemDepartment(product_id=p.id,department_id=dept.id));s.commit()
    monkeypatch.setattr('app.services.sales_transaction_service.ActivityService.log',lambda **kw:None)
    for override in ({'location_id':999},{'department_id':999},{'business_unit_id':999}):
        with pytest.raises(HTTPException):
            Service.create(s,data=SalesTransactionCreate(**override,items=[dict(product_id=p.id,quantity=1)]),user=ADMIN)
    assert s.query(SalesTransaction).count()==0

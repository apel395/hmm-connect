from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from app.api.v1.sales import list_pos_products, sale_options, list_sales, get_sale
from app.models.product import Product
from app.models.inventory import Inventory
from app.models.stock_movement import StockMovement
from app.models.sales_transaction import SalesTransaction
from app.models.journal_line import JournalLine
from app.models.general_ledger import GeneralLedger
from app.models.item_department import ItemDepartment
from app.schemas.sales_transaction import SalesTransactionCreate, SalesTransactionPost
from app.services.sales_transaction_service import SalesTransactionService as Service
from test_finance_delivery_1007 import db, ADMIN


def products(s):
    result=[]
    for i, kind, catalog in [(1,'SELL','CATERING'),(2,'BUY','CATERING'),(3,'SELL','HOTEL')]:
        p=Product(code=f'TEST-{i}',name=f'Menu {i}',group_code='5' if kind=='SELL' else '1',group_name='FOOD',subgroup_code='',subgroup_name='',uom='PORSI',usage_uom='PORSI',conversion=1,item_type=kind,inventory_treatment='NON_STOCK' if kind=='SELL' else 'STOCK',catalog_type=catalog,selling_price=100,service_charge_rate=5,is_taxable=False)
        s.add(p);result.append(p)
    s.commit();return result


def menu(s,loc,user=ADMIN,dept=None):
    return list_pos_products(location_id=loc,department_id=dept,search=None,group_name=None,page=1,page_size=100,db=s,user=user)


def test_catalog_uses_sell_menus_without_stock_and_enforces_department(db):
    s,unit,location,department,_=db
    p,buy,hotel=products(s)
    assert [r['product_id'] for r in menu(s,location.id)['items']]==[p.id]
    assert menu(s,location.id)['items'][0]['sale_available']
    s.add(ItemDepartment(product_id=p.id,department_id=department.id));s.commit()
    assert not menu(s,location.id)['items']
    assert menu(s,location.id,dept=department.id)['items'][0]['product_id']==p.id
    options=sale_options(s,ADMIN)
    assert options['locations'][0]['id']==location.id
    assert options['departments'][0]['id']==department.id


def test_location_only_sale_posts_revenue_without_inventory_or_cogs(db,monkeypatch):
    s,unit,location,department,accounts=db
    p,_,_=products(s)
    monkeypatch.setattr('app.services.sales_transaction_service.ActivityService.log',lambda **kw:None)
    def setting(self,key,label):
        return accounts[0] if key=='POS_SALES_REVENUE_ACCOUNT' else accounts[2]
    monkeypatch.setattr('app.services.sales_transaction_service.DirectCoaService.setting_account',setting)
    tx=Service.create(s,data=SalesTransactionCreate(location_id=location.id,department_id=department.id,sale_date=date(2026,1,5),transaction_type='INVOICE',items=[dict(product_id=p.id,quantity=2)]),user=ADMIN)
    assert tx.warehouse_id is None and tx.total_amount==D('210')
    tx=Service.post(s,transaction_id=tx.id,data=SalesTransactionPost(payment_received=210),user=ADMIN)
    assert tx.status=='POSTED' and tx.lines[0].unit_cost==0
    lines=s.query(JournalLine).all()
    assert sum(r.debit for r in lines)==sum(r.credit for r in lines)==D('210')
    assert {r.account_id for r in lines}=={accounts[0].id,accounts[2].id}
    assert s.query(GeneralLedger).count()==2
    assert s.query(Inventory).count()==s.query(StockMovement).count()==0
    scoped=SimpleNamespace(**{**vars(ADMIN),'roles':[],'default_location_id':location.id})
    with patch.object(Service,'_require'):
        assert get_sale(tx.id,s,scoped)['location_name']==location.name
    other=SimpleNamespace(**{**vars(scoped),'default_location_id':999})
    with patch.object(Service,'_require'),pytest.raises(HTTPException):
        get_sale(tx.id,s,other)


def test_rejects_buy_wrong_catalog_zero_price_and_cross_location(db,monkeypatch):
    s,unit,location,department,_=db
    p,buy,hotel=products(s)
    monkeypatch.setattr('app.services.sales_transaction_service.ActivityService.log',lambda **kw:None)
    for item in (buy,hotel):
        with pytest.raises(HTTPException):
            Service.create(s,data=SalesTransactionCreate(location_id=location.id,items=[dict(product_id=item.id,quantity=1)]),user=ADMIN)
    assert s.query(SalesTransaction).count()==0
    p.selling_price=0;s.commit()
    with pytest.raises(HTTPException):
        Service.create(s,data=SalesTransactionCreate(location_id=location.id,items=[dict(product_id=p.id,quantity=1)]),user=ADMIN)
    scoped=SimpleNamespace(**{**vars(ADMIN),'roles':[],'default_location_id':999})
    with patch.object(Service,'_require'),pytest.raises(HTTPException):
        menu(s,location.id,scoped)


def test_unit_and_department_access_filter_options_and_menu(db):
    s,unit,location,department,_=db
    products(s)
    unit_user=SimpleNamespace(**{**vars(ADMIN),'roles':[],'default_business_unit_id':999})
    dept_user=SimpleNamespace(**{**vars(ADMIN),'roles':[SimpleNamespace(name='DEPARTMENT')],'default_location_id':location.id,'default_department_id':999})
    with patch.object(Service,'_require'):
        assert sale_options(s,unit_user)['locations']==[]
        assert sale_options(s,dept_user)['departments']==[]
        with pytest.raises(HTTPException):
            menu(s,location.id,unit_user)
        with pytest.raises(HTTPException):
            menu(s,location.id,dept_user,department.id)

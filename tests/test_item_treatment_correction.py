from datetime import date, datetime, timezone
from decimal import Decimal as D
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models import Base
from app.models.chart_of_account import ChartOfAccount
from app.models.fiscal_period import FiscalPeriod
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.product import Product
from app.models.warehouse import Warehouse
from app.models.inventory import Inventory
from app.models.stock_movement import StockMovement
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.general_ledger import GeneralLedger
from app.models.opening_balance import OpeningBalance
from app.api.v1.products import update_product
from app.schemas.product import ProductUpdate
from app.services.item_treatment_policy import food_treatment

ADMIN=SimpleNamespace(id=None,full_name='Test operator',roles=[SimpleNamespace(name='SYSTEM_ADMINISTRATOR')])


@pytest.fixture
def data(monkeypatch):
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine,autoflush=False) as db:
        inv=ChartOfAccount(account_number='100-300-100',account_name='Inventory',account_type='ASSET',normal_balance='DEBIT',is_posting=True,is_active=True)
        expense=ChartOfAccount(account_number='500-100-100',account_name='Food cost',account_type='EXPENSE',normal_balance='DEBIT',is_posting=True,is_active=True)
        ap=ChartOfAccount(account_number='200-100-999',account_name='Suspense',account_type='LIABILITY',normal_balance='CREDIT',is_posting=True,is_active=True)
        db.add_all([inv,expense,ap]);db.flush()
        p=Product(code='1-500001',name='Tomato',group_code='1',group_name='FOOD',subgroup_code='1-5',subgroup_name='VEGETABLES',uom='KG',usage_uom='KG',conversion=1,inventory_treatment='STOCK',inventory_account_id=inv.id,cogs_account_id=expense.id)
        wh=Warehouse(code='WH',name='Warehouse',is_active=True);db.add_all([p,wh]);db.flush()
        receipt=GoodsReceipt(receipt_number='GR-TEST',status='POSTED',received_at=datetime(2026,1,8,tzinfo=timezone.utc),destination_type='WAREHOUSE',warehouse_id=wh.id,subtotal=50,tax_amount=0,total_amount=50)
        item=GoodsReceiptItem(product_id=p.id,quantity=5,unit_cost=10,is_taxable=False,tax_rate=0,tax_amount=0);receipt.items=[item];db.add(receipt);db.flush()
        journal=JournalEntry(journal_number='GR-J',posting_date=date(2026,1,8),status='POSTED',reference_type='GOODS_RECEIPT',reference_id=receipt.id,document_number=receipt.receipt_number)
        journal.lines=[JournalLine(account_id=inv.id,debit=50,credit=0),JournalLine(account_id=ap.id,debit=0,credit=50)];db.add(journal);db.flush()
        for n,(acc,debit,credit) in enumerate([(inv.id,50,0),(ap.id,0,50)]):
            db.add(GeneralLedger(journal_number=f'GL-{n}',posting_date=journal.posting_date,account_id=acc,debit=debit,credit=credit,reference_type='GOODS_RECEIPT',reference_id=receipt.id,reference_number=journal.journal_number))
        db.add_all([Inventory(product_id=p.id,warehouse_id=wh.id,quantity=5,average_cost=10),StockMovement(product_id=p.id,warehouse_id=wh.id,goods_receipt_id=receipt.id,goods_receipt_item_id=item.id,journal_entry_id=journal.id,inventory_account_id=inv.id,movement_type='IN',quantity=5,unit_cost=10,reference_type='GOODS_RECEIPT',reference_id=receipt.id),FiscalPeriod(period_name='2026',fiscal_year=2026,fiscal_month=1,start_date=date(2026,1,1),end_date=date(2026,12,31),is_open=True,is_closed=False,allow_backdated_entries=True)])
        db.commit()
        seq=iter(range(100,200));monkeypatch.setattr('app.services.general_ledger.GeneralLedgerService.generate_number',lambda _db:f'GL-{next(seq)}')
        yield db,p,expense,receipt,journal,inv,ap
    engine.dispose()


def change(db,p,expense):
    return update_product(p.id,ProductUpdate(inventory_treatment='DIRECT_USE',purchase_account_id=expense.id,correct_existing_stock=True,stock_correction_reason='These items never entered warehouse'),db,ADMIN)


def test_master_change_repairs_source_without_fake_out_and_is_idempotent(data):
    db,p,expense,receipt,journal,inv,ap=data
    change(db,p,expense)
    assert p.inventory_treatment=='DIRECT_USE' and p.inventory_account_id is None
    assert db.query(Inventory).count()==db.query(StockMovement).count()==0
    assert receipt.destination_type=='DIRECT_USE' and receipt.warehouse_id is None
    assert receipt.items[0].destination_type=='DIRECT_USE' and receipt.items[0].expense_account_id==expense.id
    assert receipt.total_amount==50 and receipt.subtotal==50 and receipt.tax_amount==0
    assert db.query(JournalEntry).count()==1 and journal.status=='POSTED'
    assert {(l.account_id,l.debit,l.credit) for l in db.query(JournalLine)}=={(expense.id,D(50),D(0)),(ap.id,D(0),D(50))}
    assert {(g.account_id,g.debit,g.credit) for g in db.query(GeneralLedger)}=={(expense.id,D(50),D(0)),(ap.id,D(0),D(50))}
    assert db.query(OpeningBalance).count()==0
    change(db,p,expense)
    assert db.query(JournalEntry).count()==1 and db.query(GeneralLedger).count()==2


@pytest.mark.parametrize('block',['out','exception','cost','closed','ledger','permission','unconfirmed'])
def test_unsafe_correction_rolls_back_everything(data,block):
    db,p,expense,receipt,journal,inv,ap=data
    user=ADMIN;kwargs=dict(correct_existing_stock=True,stock_correction_reason='Correct false stock')
    if block=='out':db.query(StockMovement).one().movement_type='OUT'
    if block=='exception':receipt.items[0].destination_override_reason='Imported warehouse exception'
    if block=='cost':db.query(Inventory).one().average_cost=11
    if block=='closed':db.query(FiscalPeriod).one().is_closed=True
    if block=='ledger':db.query(GeneralLedger).filter_by(account_id=inv.id).one().debit=49
    if block=='permission':user=SimpleNamespace(id=None,roles=[])
    if block=='unconfirmed':kwargs['correct_existing_stock']=False
    db.commit()
    with pytest.raises(HTTPException):
        update_product(p.id,ProductUpdate(inventory_treatment='DIRECT_USE',purchase_account_id=expense.id,**kwargs),db,user)
    db.rollback()
    assert db.get(Product,p.id).inventory_treatment=='STOCK'
    assert db.query(Inventory).count()==db.query(StockMovement).count()==1
    assert db.get(GoodsReceipt,receipt.id).destination_type=='WAREHOUSE'
    assert db.query(JournalEntry).count()==1


def test_family_defaults_and_warehouse_exceptions():
    for family in ['VEGETABLES','FRUIT','HERB','FISH','POULTRY','MEAT','SNACK']:
        assert food_treatment(family,'Fresh item')=='DIRECT_USE'
    assert food_treatment('MEAT','BEEF TENDERLOIN')=='STOCK'
    assert food_treatment('FISH','FROZEN SALMON')=='STOCK'
    assert food_treatment('GROCERIES','Rice') is None


def test_mixed_receipt_keeps_other_item_stock_and_inventory_debit(data):
    db,p,expense,receipt,journal,inv,ap=data
    other=Product(code='OTHER',name='Stored Rice',group_code='1',group_name='FOOD',subgroup_code='1-8',subgroup_name='GROCERIES',uom='KG',usage_uom='KG',inventory_treatment='STOCK',inventory_account_id=inv.id)
    db.add(other);db.flush()
    receipt.items.append(GoodsReceiptItem(product_id=other.id,quantity=5,unit_cost=10,is_taxable=False,tax_rate=0,tax_amount=0))
    db.add(Inventory(product_id=other.id,warehouse_id=receipt.warehouse_id,quantity=5,average_cost=10))
    receipt.subtotal=receipt.total_amount=D(100)
    db.query(JournalLine).filter_by(journal_entry_id=journal.id,account_id=inv.id).one().debit=D(100)
    db.query(JournalLine).filter_by(journal_entry_id=journal.id,account_id=ap.id).one().credit=D(100)
    db.query(GeneralLedger).filter_by(account_id=inv.id).one().debit=D(100)
    db.query(GeneralLedger).filter_by(account_id=ap.id).one().credit=D(100)
    db.commit()
    change(db,p,expense)
    assert receipt.destination_type=='MIXED' and receipt.warehouse_id is not None
    assert next(i for i in receipt.items if i.product_id==other.id).destination_type=='WAREHOUSE'
    assert db.query(Inventory).one().product_id==other.id
    assert {(l.account_id,l.debit,l.credit) for l in db.query(JournalLine)}=={(inv.id,D(50),D(0)),(expense.id,D(50),D(0)),(ap.id,D(0),D(100))}


def test_failure_on_second_receipt_rolls_back_first_receipt_correction(data):
    db,p,expense,receipt,journal,inv,ap=data
    old=GoodsReceipt(receipt_number='GR-OLD',status='POSTED',received_at=datetime(2025,12,1,tzinfo=timezone.utc),destination_type='WAREHOUSE',warehouse_id=receipt.warehouse_id,subtotal=50,tax_amount=0,total_amount=50)
    item=GoodsReceiptItem(product_id=p.id,quantity=5,unit_cost=10,is_taxable=False,tax_rate=0,tax_amount=0);old.items=[item];db.add(old);db.flush()
    db.add(StockMovement(product_id=p.id,warehouse_id=receipt.warehouse_id,goods_receipt_id=old.id,goods_receipt_item_id=item.id,inventory_account_id=inv.id,movement_type='IN',quantity=5,unit_cost=10,reference_type='GOODS_RECEIPT',reference_id=old.id))
    db.query(Inventory).one().quantity=D(10);db.commit()
    with pytest.raises(HTTPException):change(db,p,expense)
    db.rollback()
    assert db.get(Product,p.id).inventory_treatment=='STOCK'
    assert db.query(Inventory).one().quantity==D(10)
    assert db.get(GoodsReceipt,receipt.id).destination_type=='WAREHOUSE'
    assert db.query(StockMovement).count()==2
    assert {(g.account_id,g.debit,g.credit) for g in db.query(GeneralLedger)}=={(inv.id,D(50),D(0)),(ap.id,D(0),D(50))}


def test_provisional_receiving_tax_is_preserved_with_no_ap_or_tax_posting(data):
    db,p,expense,receipt,journal,inv,ap=data
    receipt.items[0].is_taxable=True;receipt.items[0].tax_rate=D(10)
    db.commit()
    assert receipt.tax_amount==5 and receipt.total_amount==55
    change(db,p,expense)
    assert receipt.items[0].is_taxable and receipt.items[0].tax_rate==10 and receipt.items[0].tax_amount==5
    assert receipt.tax_amount==5 and receipt.total_amount==55
    assert db.query(GeneralLedger).filter_by(account_id=ap.id).one().credit==50

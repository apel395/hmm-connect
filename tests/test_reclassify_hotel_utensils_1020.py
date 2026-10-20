from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine,insert
from sqlalchemy.orm import Session
from app.models import Base
from app.models.product import Product
from app.models.item_group import ItemGroup
from app.models.item_subgroup import ItemSubgroup
from app.models.chart_of_account import ChartOfAccount
from app.models.fixed_asset import FixedAsset
from app.models.inventory import Inventory
from app.models.journal_entry import JournalEntry
from app.models.general_ledger import GeneralLedger
from app.models.audit_log import AuditLog
from scripts.reclassify_hotel_utensils_1020 import TARGETS,repair

@pytest.fixture
def db():
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        for aid,code,kind in [(1,'100-300-700','ASSET'),(2,'700-500-119','EXPENSE'),(3,'100-900-101','ASSET'),(4,'100-900-102','ASSET')]:
            db.add(ChartOfAccount(id=aid,account_number=code,account_name=code,account_type=kind,normal_balance='DEBIT',is_posting=True,is_active=True))
        db.add(ItemGroup(id=1,code='3',name='MATERIAL',item_type='BUY',is_active=True))
        db.add(ItemSubgroup(id=1,code='3-4',name='STATIONARY',group_id=1,is_active=True));db.flush()
        # Persist the exact pre-policy state without invoking today's asset guard.
        for pid,code,name,aid,coa in TARGETS:
            account_id=3 if coa=='100-900-101' else 4
            db.execute(insert(Product).values(id=pid,code=code,name=name,group_code='4',group_name='ASSET',subgroup_code='4-2',subgroup_name='FURNITURE',uom='PCS',usage_uom='PCS',item_type='BUY',catalog_type='HOTEL',inventory_treatment='FIXED_ASSET',asset_account_id=account_id,is_active=True,tax_category='REVIEW_REQUIRED',tax_rate=11,cost_price=25000))
            db.execute(insert(FixedAsset).values(id=aid,asset_number=f'FA-ITEM-{pid:08d}',asset_name=name,product_id=pid,asset_account_id=account_id,status='PENDING_REGISTRATION',source_type='ITEM_MASTER',acquisition_cost=None,acquisition_date=None,net_book_value=None))
        db.commit();yield db
    engine.dispose()


def test_repair_preserves_item_ids_prices_tax_and_accounting_and_is_idempotent(db):
    before={p.id:(p.name,p.cost_price,p.tax_category,p.tax_rate) for p in db.query(Product)}
    report=repair(db);db.commit()
    assert report['changed_items']==report['removed_empty_assets']==13
    assert db.query(FixedAsset).count()==0
    assert db.query(Product).count()==13
    assert {p.inventory_treatment for p in db.query(Product)}=={'STOCK'}
    assert {p.group_name for p in db.query(Product)}=={'MATERIAL'}
    assert {p.subgroup_name for p in db.query(Product)}=={'UTENSILS'}
    assert all(p.code.startswith('3-5') and p.inventory_account_id==1 and p.cogs_account_id==2 and p.asset_account_id is None for p in db.query(Product))
    assert before=={p.id:(p.name,p.cost_price,p.tax_category,p.tax_rate) for p in db.query(Product)}
    assert db.query(Inventory).count()==db.query(JournalEntry).count()==db.query(GeneralLedger).count()==0
    assert db.query(AuditLog).count()==14
    repeated=repair(db)
    assert repeated['already_applied']==13 and repeated['changed_items']==0
    assert db.query(AuditLog).count()==14


def test_preview_rolls_back_items_empty_assets_subgroup_and_audit(db):
    repair(db);db.rollback()
    assert db.query(FixedAsset).count()==13
    assert {p.inventory_treatment for p in db.query(Product)}=={'FIXED_ASSET'}
    assert db.query(ItemSubgroup).count()==1
    assert db.query(AuditLog).count()==0


def test_partial_valuation_blocks_entire_batch_before_changes(db):
    last=db.get(FixedAsset,TARGETS[-1][3]);last.acquisition_cost=Decimal('50000');db.commit()
    with pytest.raises(ValueError,match='valued'):repair(db)
    db.rollback()
    assert db.query(FixedAsset).count()==13 and db.query(AuditLog).count()==0
    assert {p.group_name for p in db.query(Product)}=={'ASSET'}


def test_missing_target_account_and_changed_identity_are_refused(db):
    expense=db.get(ChartOfAccount,2);expense.is_active=False;db.commit()
    with pytest.raises(ValueError,match='700-500-119'):repair(db)
    db.rollback()
    db.execute(Product.__table__.update().where(Product.id==TARGETS[0][0]).values(name='Changed by user'));db.commit()
    with pytest.raises(ValueError,match='inspected'):repair(db)
    assert db.query(FixedAsset).count()==13 and db.query(AuditLog).count()==0


@pytest.mark.parametrize('history',['inventory','receipt'])
def test_stock_or_receiving_activity_aborts_without_partial_reclassification(db,history):
    pid=TARGETS[-1][0]
    if history=='inventory':
        db.execute(insert(Inventory).values(product_id=pid,warehouse_id=123,quantity=1,average_cost=50))
    else:
        from app.models.goods_receipt import GoodsReceiptItem
        db.execute(insert(GoodsReceiptItem).values(product_id=pid,goods_receipt_id=123,quantity=1,unit_cost=50))
    db.commit()
    with pytest.raises(ValueError):repair(db)
    db.rollback()
    assert db.query(FixedAsset).count()==13
    assert db.query(AuditLog).count()==0
    assert {p.inventory_treatment for p in db.query(Product)}=={'FIXED_ASSET'}

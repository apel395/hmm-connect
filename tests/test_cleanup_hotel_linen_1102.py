from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session
from app.models import Base
from app.models.product import Product
from app.models.item_group import ItemGroup
from app.models.item_subgroup import ItemSubgroup
from app.models.chart_of_account import ChartOfAccount
from app.models.fixed_asset import FixedAsset, FixedAssetFiscalProfile, FixedAssetMovement, FixedAssetDepreciationSchedule
from app.models.inventory import Inventory
from app.models.stock_movement import StockMovement
from app.models.goods_receipt import GoodsReceiptItem
from app.models.journal_entry import JournalEntry
from app.models.general_ledger import GeneralLedger
from app.models.audit_log import AuditLog
from scripts.cleanup_hotel_linen_assets_1102 import cleanup, TARGETS


@pytest.fixture
def db():
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        db.add_all([ChartOfAccount(id=224,account_number='100-900-100',account_name='Operating Equipment - Linen',account_type='ASSET',normal_balance='DEBIT',is_posting=True,is_active=True),
                    ChartOfAccount(id=70,account_number='700-500-119',account_name='Supplies expense',account_type='EXPENSE',normal_balance='DEBIT',is_posting=True,is_active=True)])
        db.add(ItemGroup(id=18,code='3',name='MATERIAL',item_type='BUY',is_active=True))
        db.add(ItemSubgroup(id=80,code='3-9',name='UTENSILS',group_id=18,is_active=True));db.flush()
        for index,(pid,aid) in enumerate(TARGETS):
            db.execute(insert(Product).values(id=pid,code=f'4-2{index+1:05d}',name=f'LINEN - Synthetic towel {index+1}',group_code='4',group_name='ASSET',subgroup_code='4-2',subgroup_name='FURNITURE',
                uom='DOZ' if index==0 else 'PCS',usage_uom='PCS',conversion=12 if index==0 else 1,item_type='BUY',catalog_type='HOTEL',is_active=True,
                inventory_treatment='FIXED_ASSET',asset_account_id=224,inventory_account_id=None,purchase_account_id=70 if index==0 else None,cogs_account_id=None,
                cost_price=25000,tax_category='REVIEW_REQUIRED',tax_rate=11,is_taxable=True))
            db.execute(insert(FixedAsset).values(id=aid,asset_number=f'FA-ITEM-{pid:08d}',asset_name=f'LINEN - Synthetic towel {index+1}',product_id=pid,asset_account_id=224,
                status='PENDING_REGISTRATION',source_type='ITEM_MASTER',acquisition_cost=None,acquisition_date=None,net_book_value=None))
        db.commit();yield db
    engine.dispose()


def test_cleanup_all_35_preserves_units_tax_cost_links_and_supports_noop_after_real_use(db):
    before={p.id:(p.name,p.uom,p.usage_uom,p.conversion,p.cost_price,p.tax_category,p.tax_rate,p.is_taxable,p.purchase_account_id,p.cogs_account_id) for p in db.query(Product)}
    report=cleanup(db);db.commit()
    assert report['changed_items']==report['removed_empty_assets']==35
    assert db.query(FixedAsset).count()==0 and db.query(Product).count()==35
    assert {p.group_name for p in db.query(Product)}=={'MATERIAL'}
    assert {p.subgroup_name for p in db.query(Product)}=={'LINEN'}
    assert {p.inventory_treatment for p in db.query(Product)}=={'STOCK'}
    assert {p.inventory_account_id for p in db.query(Product)}=={224}
    assert {p.asset_account_id for p in db.query(Product)}=={None}
    assert len({p.code for p in db.query(Product)})==35
    assert all(p.code.startswith('3-10') for p in db.query(Product))
    assert before=={p.id:(p.name,p.uom,p.usage_uom,p.conversion,p.cost_price,p.tax_category,p.tax_rate,p.is_taxable,p.purchase_account_id,p.cogs_account_id) for p in db.query(Product)}
    assert db.query(Inventory).count()==db.query(StockMovement).count()==db.query(JournalEntry).count()==db.query(GeneralLedger).count()==0
    assert db.query(AuditLog).filter_by(action='LINEN_RECLASSIFIED').count()==35
    for log in db.query(AuditLog).filter_by(action='LINEN_RECLASSIFIED'):
        assert log.details['removed_unvalued_asset']['acquisition_cost'] is None
        assert log.before_data['asset_account_id']==224 and log.after_data['inventory_account_id']==224
    count=db.query(AuditLog).count()
    # Subsequent legitimate warehouse use must not turn an idempotent rerun into a repair.
    db.execute(insert(Inventory).values(product_id=TARGETS[0][0],warehouse_id=11,quantity=12,average_cost=25000));db.commit()
    again=cleanup(db);db.commit()
    assert again['already_applied']==35 and again['changed_items']==0
    assert db.query(AuditLog).count()==count
    assert db.query(Inventory).one().quantity==12


def test_preview_rolls_back_master_subgroup_asset_deletion_and_audit(db):
    report=cleanup(db)
    assert report['changed_items']==35
    db.rollback()
    assert db.query(FixedAsset).count()==35
    assert {p.inventory_treatment for p in db.query(Product)}=={'FIXED_ASSET'}
    assert db.query(ItemSubgroup).count()==1 and db.query(AuditLog).count()==0


@pytest.mark.parametrize('evidence',['value','stock','receipt','fiscal','movement','schedule','journal'])
def test_valued_or_linked_targets_abort_entire_batch_before_changes(db,evidence):
    pid,aid=TARGETS[-1]
    if evidence=='value': db.get(FixedAsset,aid).acquisition_cost=Decimal('10000')
    elif evidence=='stock': db.execute(insert(Inventory).values(product_id=pid,warehouse_id=11,quantity=1,average_cost=500))
    elif evidence=='receipt': db.execute(insert(GoodsReceiptItem).values(product_id=pid,goods_receipt_id=1,quantity=1,unit_cost=500))
    elif evidence=='fiscal': db.execute(insert(FixedAssetFiscalProfile).values(fixed_asset_id=aid,group_code='GROUP_1',method='STRAIGHT_LINE',fiscal_cost=500,start_date=date(2026,1,1),reference='',version=1,updated_by_id=1))
    elif evidence=='movement': db.execute(insert(FixedAssetMovement).values(fixed_asset_id=aid,movement_type='ACQUISITION',movement_date=date(2026,1,1),created_by_id=1))
    elif evidence=='schedule': db.execute(insert(FixedAssetDepreciationSchedule).values(fixed_asset_id=aid,period_year=2026,period_month=1,period_start=date(2026,1,1),period_end=date(2026,1,31),opening_book_value=500,depreciation_amount=10,accumulated_depreciation=10,closing_book_value=490))
    elif evidence=='journal': db.add(JournalEntry(journal_number='LINEN-REF',posting_date=date(2026,1,1),reference_type='FIXED_ASSET_CAPITALIZATION',reference_id=aid,status='DRAFT'))
    db.commit()
    with pytest.raises(ValueError,match='stopped before changes'):cleanup(db)
    db.rollback()
    assert db.query(FixedAsset).count()==35
    assert {p.group_name for p in db.query(Product)}=={'ASSET'}
    assert db.query(ItemSubgroup).count()==1 and db.query(AuditLog).count()==0


def test_audit_failure_rolls_back_whole_cleanup(db,monkeypatch):
    import scripts.cleanup_hotel_linen_assets_1102 as script
    def fail(*a,**k):raise RuntimeError('Audit unavailable')
    monkeypatch.setattr(script,'record_audit',fail)
    with pytest.raises(RuntimeError):cleanup(db)
    db.rollback()
    assert db.query(FixedAsset).count()==35 and db.query(AuditLog).count()==0


def test_existing_linen_subgroup_reused_without_touching_other_assets(db):
    db.add(ItemSubgroup(code='3-10',name='LINEN',group_id=18,is_active=True))
    db.execute(insert(FixedAsset).values(id=99,asset_number='VALUED-OTHER',asset_name='Computer',asset_account_id=999,status='ACTIVE',acquisition_date=date(2026,1,1),acquisition_cost=5500000,net_book_value=5500000,business_unit_id=1,created_by_id=1))
    db.commit()
    cleanup(db);db.commit()
    assert db.query(ItemSubgroup).count()==2
    assert db.query(FixedAsset).one().id==99 and db.query(FixedAsset).one().acquisition_cost==5500000


def test_changed_repaired_classification_is_not_silently_repaired_again(db):
    cleanup(db);db.commit()
    p=db.get(Product,TARGETS[0][0]);p.inventory_account_id=None;db.commit()
    with pytest.raises(ValueError,match='previously cleaned'):cleanup(db)
    db.rollback()
    assert db.get(Product,TARGETS[0][0]).inventory_account_id is None

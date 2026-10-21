from datetime import date
from app.models.product import Product
from app.models.department import Department
from app.models.location_department import LocationDepartment
from app.models.supplier import Supplier
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_requisition import PurchaseRequisition
from app.models.market_list import MarketList
from app.models.goods_receipt import GoodsReceipt
from app.models.stock_movement import StockMovement
from app.models.journal_entry import JournalEntry
from app.models.general_ledger import GeneralLedger
from app.models.audit_log import AuditLog
from app.services.purchasing_retention import cleanup
from scripts.test_purchasing_age_documents import create_batch, exercise_batch, inspect_batch
from test_organization_and_asset_delivery import db
import pytest

DAY=date(2026,10,21)


def master_data(db):
    db.add(Supplier(id=1,code='SUP',name='Existing Supplier'))
    db.add(Department(id=6,code='FB',name='Food and Beverage',business_unit_id=1))
    db.add(LocationDepartment(location_id=1,department_id=6))
    for code,subgroup,market in [('ORD','GROCERIES',False),('MARKET','VEGETABLES',True)]:
        db.add(Product(code=code,name=code,group_code='1',group_name='FOOD',subgroup_code='1-8' if not market else '1-5',subgroup_name=subgroup,uom='KG',usage_uom='KG',item_type='BUY',catalog_type='HOTEL',inventory_treatment='STOCK' if not market else 'DIRECT_USE',is_market_item=market))
    db.commit()


def test_nine_unlinked_drafts_follow_calendar_policy_without_accounting(db):
    master_data(db)
    rows=create_batch(db,as_of=DAY,location_id=1);db.commit()
    assert len(rows)==9 and {r['status'] for r in rows}=={'DRAFT'}
    assert {r['date'] for r in rows}=={'2026-03-21','2026-06-21','2026-08-21'}
    assert db.query(Product).count()==2
    assert all(po.department_id==6 for po in db.query(PurchaseOrder))
    assert db.query(PurchaseOrder).count()==db.query(PurchaseRequisition).count()==db.query(MarketList).count()==3
    # A real old document is deliberately present to prove the demo is scoped.
    real_pr=PurchaseRequisition(pr_number='REAL-DO-NOT-DELETE',request_date=date(2026,3,1),status='DRAFT')
    real_po=PurchaseOrder(po_number='REAL-DO-NOT-ARCHIVE',supplier_id=1,order_date=date(2026,3,1),status='DRAFT')
    db.add_all([real_pr,real_po]);db.commit()
    preview=exercise_batch(db,as_of=DAY,location_id=1)
    assert preview['retention']['counts']=={'PO_TO_TRASH':1,'PR_DELETE':2,'PROTECTED':0}
    assert {r['status'] for r in preview['after']}=={'DRAFT'}
    result=exercise_batch(db,as_of=DAY,location_id=1,apply=True);db.commit()
    statuses={(r['kind'],r['months_old']):r['status'] for r in result['after']}
    assert statuses=={('PR',7):'REMOVED',('PR',4):'REMOVED',('PR',2):'DRAFT',('PO',7):'ARCHIVED',('PO',4):'DRAFT',('PO',2):'DRAFT',('ML',7):'DRAFT',('ML',4):'DRAFT',('ML',2):'DRAFT'}
    assert db.get(PurchaseRequisition,real_pr.id) and db.get(PurchaseOrder,real_po.id).status=='DRAFT'
    assert len(create_batch(db,as_of=DAY,location_id=1))==9
    assert db.query(AuditLog).filter_by(action='AGE_TEST_CREATED').count()==9
    assert exercise_batch(db,as_of=DAY,location_id=1,apply=True)['retention']['counts']=={'PO_TO_TRASH':0,'PR_DELETE':0,'PROTECTED':0}
    for model in (GoodsReceipt,StockMovement,JournalEntry,GeneralLedger): assert db.query(model).count()==0


def test_seed_preview_rolls_back_and_edited_marker_refuses_writes(db):
    master_data(db)
    create_batch(db,as_of=DAY,location_id=1);db.rollback()
    assert db.query(PurchaseOrder).count()==db.query(PurchaseRequisition).count()==db.query(MarketList).count()==0
    create_batch(db,as_of=DAY,location_id=1);db.commit()
    db.query(PurchaseOrder).first().notes='Changed by user';db.commit()
    with pytest.raises(ValueError,match='identity or fixture data changed'):
        exercise_batch(db,as_of=DAY,location_id=1,apply=True)
    assert db.query(PurchaseRequisition).count()==3


def test_empty_target_never_runs_global_cleanup_and_pre_2026_fixtures_are_refused(db):
    master_data(db)
    db.add(PurchaseRequisition(pr_number='REAL',request_date=date(2026,1,1)));db.commit()
    assert cleanup(db,as_of=DAY,apply=True,only_ids={})['counts']=={'PO_TO_TRASH':0,'PR_DELETE':0,'PROTECTED':0}
    assert db.query(PurchaseRequisition).count()==1
    with pytest.raises(ValueError,match='2026 or later'):
        create_batch(db,as_of=date(2026,7,1),location_id=1)

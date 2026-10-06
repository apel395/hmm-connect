from datetime import date
from decimal import Decimal
from pathlib import Path
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from seed_resiping_receiving_drafts import plan_receiving,save_drafts


def source():
    line={'row':5,'item':'Ingredient','product_id':1,'quantity':Decimal(2),'unit_price':Decimal(100),
          'net':Decimal(200),'tax':Decimal(0),'raw_tax':None,'raw_received_date':'2 JAN 26',
          'received_date':date(2026,1,2),'treatment':'STOCK','warehouse_id':8,'errors':[]}
    inv={'key':'INV-000001','supplier':'Supplier','location':'Rumbai','supplier_id':1,'location_id':6,
         'department_id':1,'status':'REVIEW','errors':['INVOICE_NUMBER_IS_TEMPLATE_SEQUENCE_REVIEW'],'lines':[line]}
    return {'source_sha256':'source','invoices':[inv]}


def test_selective_plan_rejects_2025_unknown_year_units_and_unmatched_supplier():
    report=source();inv=report['invoices'][0]
    inv['lines'] += [{**inv['lines'][0],'row':6,'received_date':date(2025,12,31)},
                     {**inv['lines'][0],'row':7,'received_date':None},
                     {**inv['lines'][0],'row':8,'errors':['UNIT_OR_CONVERSION_REVIEW']}]
    plan=plan_receiving(report,[{'id':6,'business_unit_id':2}])
    assert len(plan['groups'])==1 and len(plan['groups'][0]['lines'])==1
    assert len(plan['skipped'])==3
    inv['supplier_id']=None
    assert not plan_receiving(report,[])['groups']


def test_direct_use_has_no_warehouse_and_closed_period_is_skipped():
    report=source();inv=report['invoices'][0];inv['lines'][0]['treatment']='DIRECT_USE'
    assert plan_receiving(report,[])['groups'][0]['warehouse_id'] is None
    inv['errors'].append('ACCOUNTING_PERIOD_NOT_OPEN:2026-01-02')
    assert not plan_receiving(report,[])['groups']


def test_apply_creates_only_drafts_is_idempotent_and_refuses_edited_rows():
    from app.models import Base
    from app.models.goods_receipt import GoodsReceipt
    from app.models.inventory import Inventory
    from app.models.stock_movement import StockMovement
    from app.models.journal_entry import JournalEntry
    from app.models.supplier_invoice import SupplierInvoice
    from app.models.audit_log import AuditLog
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    plan=plan_receiving(source(),[{'id':6,'business_unit_id':2}])
    with Session(engine) as db:
        assert save_drafts(db,plan)=={'new_drafts':1,'new_rows':1}
        assert db.query(GoodsReceipt).count()==0
        assert save_drafts(db,plan,True)=={'new_drafts':1,'new_rows':1}
        db.commit()
        assert save_drafts(db,plan,True)=={'already_seeded':1}
        receipt=db.query(GoodsReceipt).one()
        assert receipt.status=='DRAFT' and receipt.received_at.date()==date(2026,1,2)
        assert receipt.total_amount==200 and receipt.location_id==6
        assert db.query(AuditLog).count()==1
        for model in (Inventory,StockMovement,JournalEntry,SupplierInvoice):assert db.query(model).count()==0
        receipt.items[0].quantity=3;db.flush()
        with pytest.raises(ValueError,match='changed'):save_drafts(db,plan,True)

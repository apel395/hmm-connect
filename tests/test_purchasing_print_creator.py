from datetime import datetime, timezone
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.purchase_order import PurchaseOrder
from app.models.goods_receipt import GoodsReceipt
from app.models.supplier import Supplier
from app.services.document_context import document_context
from app.services.document_print_tracking import record_print
from test_organization_and_asset_delivery import db, ADMIN


def test_po_uses_recorded_creator_and_preview_does_not_count(db):
    created=datetime(2026,10,14,3,0,tzinfo=timezone.utc)
    db.add(User(id=1,username='creator',email='creator@test.invalid',full_name='Creator Current Name',password_hash='test'))
    db.add(Supplier(id=1,code='SUP',name='Supplier'));db.flush()
    db.add(PurchaseOrder(id=1,po_number='PO-TEST',supplier_id=1,location_id=1,created_by_id=1,created_at=created,status='DRAFT'))
    db.add(AuditLog(entity_type='PURCHASE_ORDER',entity_id=1,action='CREATE',summary='Created',actor_name='Creator Recorded Name',created_at=created))
    db.commit()
    for _ in range(2):
        info=document_context(db,'PURCHASE_ORDER',1,'DRAFT',ADMIN)
        assert info['created_by_name']=='Creator Recorded Name'
        assert info['created_at'].hour==3
    assert db.query(AuditLog).filter_by(action='PRINT').count()==0
    assert record_print(db,ADMIN,'PURCHASE_ORDER',1,'first')['print_count']==1
    assert record_print(db,ADMIN,'PURCHASE_ORDER',1,'first')['print_count']==1
    assert record_print(db,ADMIN,'PURCHASE_ORDER',1,'second')['print_count']==2


def test_receiving_uses_creation_event_time_not_receiving_date(db):
    created=datetime(2026,10,14,3,0,tzinfo=timezone.utc)
    db.add(GoodsReceipt(id=1,receipt_number='GR-TEST',location_id=1,received_at=datetime(2026,1,1,tzinfo=timezone.utc),status='DRAFT'))
    db.add(AuditLog(entity_type='GOODS_RECEIPT',entity_id=1,action='RESIPING_RECEIVING_DRAFT_CREATED',summary='Imported draft',actor_name='Inputter',created_at=created))
    db.commit()
    info=document_context(db,'GOODS_RECEIPT',1,'DRAFT',ADMIN)
    assert info['created_by_name']=='Inputter'
    assert info['created_at'].month==10 and info['created_at'].hour==3


def test_other_document_context_does_not_overwrite_source_creation_time(db):
    info=document_context(db,'SUPPLIER_INVOICE',99,'DRAFT',ADMIN)
    assert 'created_at' not in info and 'created_by_name' not in info

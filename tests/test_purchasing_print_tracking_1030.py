from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.supplier import Supplier
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_requisition import PurchaseRequisition
from app.models.market_list import MarketList
from app.models.goods_receipt import GoodsReceipt
from app.models.journal_entry import JournalEntry
from app.models.general_ledger import GeneralLedger
from app.models.inventory import Inventory
from app.services.document_print_tracking import record_print, print_context, print_history, REPORTS
from test_organization_and_asset_delivery import db

ACTOR=SimpleNamespace(id=1,full_name='Print operator',username='print-op',roles=[SimpleNamespace(name='SYSTEM_ADMINISTRATOR')])


@pytest.fixture
def documents(db):
    db.add_all([User(id=1,username='print-op',email='print@example.test',full_name=ACTOR.full_name,password_hash='test'),Supplier(id=1,code='SUP',name='Print supplier')]);db.flush()
    rows={
        'PURCHASE_REQUISITION':PurchaseRequisition(pr_number='PR-PRINT',requested_by_id=1,location_id=1,request_date=date(2026,10,30)),
        'MARKET_LIST':MarketList(ml_number='ML-PRINT',location_id=1,request_date=date(2026,10,30)),
        'PURCHASE_ORDER':PurchaseOrder(po_number='PO-PRINT',supplier_id=1,location_id=1),
        'GOODS_RECEIPT':GoodsReceipt(receipt_number='RR-PRINT',supplier_id=1,location_id=1,received_at=datetime(2026,10,30,tzinfo=timezone.utc)),
    }
    db.add_all(rows.values());db.commit()
    return rows


@pytest.mark.parametrize('kind',['PURCHASE_REQUISITION','MARKET_LIST','PURCHASE_ORDER','GOODS_RECEIPT'])
def test_preview_print_and_pdf_are_separate_with_stable_retry(db,documents,kind):
    document=documents[kind]
    first=print_context(db,ACTOR,kind,document.id)['print_tracking']
    assert first['print_count']==first['pdf_download_count']==0
    assert print_context(db,ACTOR,kind,document.id)=={'print_tracking':first}
    assert db.query(AuditLog).count()==0
    one=record_print(db,ACTOR,kind,document.id,'first',expected_revision=first['revision_hash'])
    assert one['print_count']==1 and one['revision_number']==1 and not one['physical_print_confirmed']
    pdf=record_print(db,ACTOR,kind,document.id,'pdf',action='PDF_DOWNLOAD',expected_revision=first['revision_hash'])
    assert pdf['print_count']==1 and pdf['pdf_download_count']==1
    two=record_print(db,ACTOR,kind,document.id,'second')
    assert two['print_count']==2 and two['reprint_number']==1
    # Retry the first request after other requests: return its original stamp.
    assert record_print(db,ACTOR,kind,document.id,'first')['print_count']==1
    assert db.query(AuditLog).count()==3
    history=print_history(db,ACTOR,kind,document.id)
    assert history['print_count']==2 and history['pdf_download_count']==1
    assert {event['actor_name'] for event in history['events']}=={ACTOR.full_name}
    assert all(event['occurred_at'] for event in history['events'])
    assert not db.query(JournalEntry).count() and not db.query(GeneralLedger).count() and not db.query(Inventory).count()


def test_changed_document_rejects_stale_preview_and_records_new_revision(db,documents):
    kind='PURCHASE_ORDER';doc=documents[kind]
    revision=print_context(db,ACTOR,kind,doc.id)['print_tracking']['revision_hash']
    record_print(db,ACTOR,kind,doc.id,'original',expected_revision=revision)
    doc.notes='Approved correction';db.commit()
    with pytest.raises(HTTPException,match='Document changed'):
        record_print(db,ACTOR,kind,doc.id,'stale',expected_revision=revision)
    db.rollback()
    assert db.query(AuditLog).count()==1
    revision2=print_context(db,ACTOR,kind,doc.id)['print_tracking']['revision_hash']
    assert revision2!=revision
    revised=record_print(db,ACTOR,kind,doc.id,'revised',expected_revision=revision2)
    assert revised['revision_number']==2 and revised['print_count']==2
    assert record_print(db,ACTOR,kind,doc.id,'original')['revision_hash']==revision


def test_permission_location_and_request_collision_are_enforced(db,documents):
    doc=documents['PURCHASE_ORDER'];user=SimpleNamespace(id=2,full_name='Other',roles=[SimpleNamespace(name='STAFF',permissions=[])],location_id=2)
    for fn in (lambda:print_history(db,user,'PURCHASE_ORDER',doc.id),lambda:record_print(db,user,'PURCHASE_ORDER',doc.id,'no-access')):
        with pytest.raises(HTTPException) as error:fn()
        assert error.value.status_code==403
    user.roles[0].permissions=[SimpleNamespace(code='po.view')]
    with pytest.raises(HTTPException) as error:print_history(db,user,'PURCHASE_ORDER',doc.id)
    assert error.value.status_code==404
    record_print(db,ACTOR,'PURCHASE_ORDER',doc.id,'same')
    with pytest.raises(HTTPException,match='already used'):
        record_print(db,ACTOR,'PURCHASE_ORDER',doc.id,'same',action='PDF_DOWNLOAD')
    assert db.query(AuditLog).count()==1


@pytest.mark.parametrize('kind',list(REPORTS))
def test_all_purchasing_reports_track_attempts_without_documents(db,documents,kind):
    result=record_print(db,ACTOR,kind,0,'report',snapshot_hash='a'*64)
    assert result['print_count']==1 and result['rendered_snapshot_hash']=='a'*64
    assert record_print(db,ACTOR,kind,0,'report',snapshot_hash='a'*64)['print_count']==1
    assert print_history(db,ACTOR,kind,0)['print_count']==1

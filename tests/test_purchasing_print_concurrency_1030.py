import pytest
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from app.models.audit_log import AuditLog
from app.services.document_print_tracking import record_print
from test_journal_postgres_concurrency_1028 import pg, race, TEST_URL

pytestmark=pytest.mark.skipif(not TEST_URL,reason='Dedicated PostgreSQL concurrency database not configured')


@pytest.mark.parametrize('same_request',[True,False])
@pytest.mark.parametrize('report',[True,False])
def test_print_sequence_serializes_and_deduplicates(pg,same_request,report):
    if report:
        kind,document_id='EXPECTED_RECEIVING',0
    else:
        with pg.factory() as db:
            supplier=Supplier(code='PRINT-SUP',name='Print supplier');db.add(supplier);db.flush()
            po=PurchaseOrder(po_number='PO-PRINT',supplier_id=supplier.id,location_id=pg.location_id)
            db.add(po);db.commit();document_id=po.id
        kind='PURCHASE_ORDER'
    first,second=race(pg,
        lambda db:record_print(db,pg.user,kind,document_id,'first',snapshot_hash='a'*64,commit=False),
        lambda db:record_print(db,pg.user,kind,document_id,'first' if same_request else 'second',snapshot_hash='a'*64))
    assert first['print_count']==1
    assert second['print_count']==(1 if same_request else 2)
    with pg.factory() as db:
        assert db.query(AuditLog).filter_by(entity_type=kind,action='PRINT').count()==(1 if same_request else 2)

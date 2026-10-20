from datetime import date, datetime, timezone
import pytest
from fastapi import HTTPException
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_requisition import PurchaseRequisition
from app.models.supplier import Supplier
from app.models.audit_log import AuditLog
from app.services.purchasing_retention import cleanup, months_before
from app.services.purchasing_exceptions import archive_document
from test_organization_and_asset_delivery import db, ADMIN


def orders(db):
    db.add(Supplier(id=1,code='SUP',name='Supplier'));db.flush()
    old=PurchaseOrder(id=1,po_number='OLD',supplier_id=1,location_id=1,order_date=date(2026,3,1),status='DRAFT')
    boundary=PurchaseOrder(id=2,po_number='BOUNDARY',supplier_id=1,location_id=1,order_date=date(2026,4,20),status='DRAFT')
    request=PurchaseRequisition(id=1,pr_number='OLD-PR',location_id=1,request_date=date(2026,6,1),status='DRAFT')
    db.add_all([old,boundary,request]);db.commit()
    return old,boundary,request


def test_calendar_cutoffs_and_preview_has_no_writes(db):
    old,_,pr=orders(db)
    assert months_before(date(2026,8,31),6)==date(2026,2,28)
    result=cleanup(db,as_of=date(2026,10,20))
    assert result['counts']=={'PO_TO_TRASH':1,'PR_DELETE':1,'PROTECTED':0}
    assert old.status=='DRAFT' and db.get(PurchaseRequisition,pr.id)
    assert db.query(AuditLog).count()==0


def test_apply_archives_po_deletes_only_unlinked_pr_and_is_idempotent(db):
    old,boundary,pr=orders(db)
    result=cleanup(db,as_of=date(2026,10,20),apply=True);db.commit()
    assert result['counts']['PR_DELETE']==1
    assert old.status=='ARCHIVED' and boundary.status=='DRAFT'
    assert db.get(PurchaseRequisition,pr.id) is None
    assert {a.action for a in db.query(AuditLog)}=={'ARCHIVE','DELETE'}
    assert cleanup(db,as_of=date(2026,10,20),apply=True)['counts']=={'PO_TO_TRASH':0,'PR_DELETE':0,'PROTECTED':0}
    archive_document(db,ADMIN,'PURCHASE_ORDER',old.id,'Still required',restore=True)
    assert old.status=='DRAFT'
    assert cleanup(db,as_of=date(2026,10,20),apply=True)['counts']['PO_TO_TRASH']==0


def test_linked_pr_and_completed_po_are_retained(db):
    old,_,pr=orders(db)
    old.purchase_requisition_id=pr.id;old.status='RECEIVED';db.commit()
    result=cleanup(db,as_of=date(2026,10,20),apply=True);db.commit()
    assert result['counts']['PROTECTED']==1
    assert db.get(PurchaseRequisition,pr.id) and old.status=='RECEIVED'


def test_received_quantity_prevents_po_archive(db):
    from app.models.product import Product
    from app.models.purchase_order_item import PurchaseOrderItem
    old,_,_=orders(db)
    p=Product(code='TEST',name='Test',group_code='1',group_name='FOOD',subgroup_code='1-1',subgroup_name='MEAT',uom='KG',usage_uom='KG')
    db.add(p);db.flush()
    db.add(PurchaseOrderItem(purchase_order_id=old.id,product_id=p.id,quantity=1,received_quantity=1,unit_price=10,total_price=10));db.commit()
    result=cleanup(db,as_of=date(2026,10,20),apply=True)
    assert result['counts']['PO_TO_TRASH']==0 and old.status=='DRAFT'
    assert any(r['reason']=='RECEIVED_QUANTITY' for r in result['items'])


def test_pending_approval_is_cancelled_and_restore_requires_fresh_approval(db):
    from app.models.approval_workflow import ApprovalWorkflow
    from app.models.approval_request import ApprovalRequest,ApprovalRequestStep
    old,_,_=orders(db)
    workflow=ApprovalWorkflow(code='PO',name='PO',entity_type='PURCHASE_ORDER')
    db.add(workflow);db.flush()
    request=ApprovalRequest(workflow_id=workflow.id,entity_type='PURCHASE_ORDER',entity_id=old.id,status='PENDING',current_step_order=1,created_by_id=1)
    request.steps=[ApprovalRequestStep(step_order=1,name='Approve',approver_role_name='PURCHASING',status='PENDING')]
    db.add(request);old.status='PENDING_APPROVAL';db.commit()
    cleanup(db,as_of=date(2026,10,20),apply=True);db.commit()
    assert request.status=='CANCELLED' and request.current_step_order is None
    assert request.steps[0].status=='CANCELLED'
    archive_document(db,ADMIN,'PURCHASE_ORDER',old.id,'Needed again',restore=True)
    assert old.status=='DRAFT'
    assert db.query(ApprovalRequest).count()==0
    audit=db.query(AuditLog).filter_by(action='ARCHIVE').one()
    assert audit.details['approval']['status']=='PENDING'
    assert db.query(AuditLog).filter_by(action='APPROVAL_RESET').one()


def test_restore_refuses_source_quantity_already_ordered_elsewhere(db):
    from app.models.product import Product
    from app.models.purchase_order_item import PurchaseOrderItem
    from app.models.purchase_requisition_item import PurchaseRequisitionItem
    from app.services.purchasing_retention import validate_po_restore
    old,boundary,pr=orders(db)
    product=Product(code='SUPPLIES',name='Office supplies',group_code='3',group_name='MATERIAL',subgroup_code='3-4',subgroup_name='STATIONARY',uom='PCS',usage_uom='PCS')
    db.add(product);db.flush()
    source=PurchaseRequisitionItem(purchase_requisition_id=pr.id,product_id=product.id,quantity=5,estimated_price=10,total_price=50)
    db.add(source);db.flush()
    for po in (old,boundary):
        db.add(PurchaseOrderItem(purchase_order_id=po.id,purchase_requisition_item_id=source.id,product_id=product.id,quantity=5,unit_price=10,total_price=50))
    old.status='ARCHIVED';db.commit()
    with pytest.raises(HTTPException):validate_po_restore(db,old)
    boundary.status='CANCELLED';db.commit()
    validate_po_restore(db,old)

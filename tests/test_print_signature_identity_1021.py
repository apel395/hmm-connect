from copy import deepcopy
from datetime import datetime, timezone
import pytest
from app.models.user import User
from app.models.supplier import Supplier
from app.models.purchase_order import PurchaseOrder
from app.models.approval_workflow import ApprovalWorkflow
from app.models.approval_request import ApprovalRequest, ApprovalRequestStep
from app.services import print_signatures
from app.services.document_context import document_context
from test_organization_and_asset_delivery import db, ADMIN

WHEN=datetime(2026,10,21,1,30,tzinfo=timezone.utc)


@pytest.fixture
def signing_db(db,monkeypatch):
    # Test assets are inert placeholders; real signature bytes are not test output.
    monkeypatch.setattr(print_signatures,'_SIGNATURES',{'STORE':{'name':'Store Owner','label':'Store','svg':'<svg/>'}})
    db.add_all([User(id=1,username='owner',email='owner@test.invalid',full_name='Store Owner',password_hash='test'),User(id=2,username='other',email='other@test.invalid',full_name='Another Approver',password_hash='test')])
    db.commit()
    return db


def payload(**step_changes):
    return {'location_name':'Batam','approval_history':[{'level':1,'name':'Store Approval','approver_role':'STORE','status':'APPROVED','approver_id':1,'approver_name':'Store Owner','decided_at':WHEN,**step_changes}]}


def test_signature_requires_actual_owner_and_preserves_approval_metadata(signing_db):
    data=payload(approver_name='  STORE  Owner ')
    record=data['approval_history'][0]
    print_signatures.add_private_print_signatures(data,db=signing_db)
    assert record['signature_image'].startswith('data:image/svg+xml;')
    assert record['signature_name']=='  STORE  Owner '
    assert record['approver_name']=='  STORE  Owner ' and record['decided_at']==WHEN
    assert record['name']=='Store Approval'


@pytest.mark.parametrize('changes',[
    {'approver_name':'Another Approver','approver_id':2},
    {'approver_name':'Store Owner','approver_id':2},
    {'approver_name':None}, {'approver_id':None}, {'decided_at':None},
    {'status':'PENDING'}, {'status':'REJECTED'}, {'status':'WAITING'},
    {'approver_name':'Store'}, {'name':'Finance','approver_role':'FINANCE'},
])
def test_role_alone_or_incomplete_approval_never_attaches_someone_elses_signature(signing_db,changes):
    data=payload(**changes)
    original=deepcopy(data)
    print_signatures.add_private_print_signatures(data,db=signing_db)
    assert data==original


def test_duplicate_names_missing_database_and_other_locations_have_blank_signature_space(signing_db):
    db=signing_db
    data=payload()
    assert 'signature_image' not in print_signatures.add_private_print_signatures(data)['approval_history'][0]
    for location in ('Hotel','Not Batam','Batam elsewhere',None):
        data={**payload(),'location_name':location}
        assert 'signature_image' not in print_signatures.add_private_print_signatures(data,db=db)['approval_history'][0]
    db.add(User(id=3,username='duplicate',email='duplicate@test.invalid',full_name='Store Owner',password_hash='test'));db.commit()
    assert 'signature_image' not in print_signatures.add_private_print_signatures(payload(),db=db)['approval_history'][0]


def test_reused_payload_clears_stale_signature_after_rejection_or_location_change(signing_db):
    data=payload()
    print_signatures.add_private_print_signatures(data,db=signing_db)
    data['approval_history'][0]['status']='REJECTED'
    print_signatures.add_private_print_signatures(data,db=signing_db)
    assert not any(key.startswith('signature_') for key in data['approval_history'][0])
    data=payload()
    print_signatures.add_private_print_signatures(data,db=signing_db)
    data['location_name']='Hotel'
    print_signatures.add_private_print_signatures(data,db=signing_db)
    assert not any(key.startswith('signature_') for key in data['approval_history'][0])


def test_document_context_links_actual_approver_identity_and_time(signing_db):
    db=signing_db
    from app.models.location import Location
    db.get(Location,1).name='Batam'
    db.add(Supplier(id=1,code='SUP',name='Supplier'));db.flush()
    db.add(PurchaseOrder(id=1,po_number='PO-IDENTITY',supplier_id=1,location_id=1,created_by_id=2,status='APPROVED'))
    workflow=ApprovalWorkflow(id=1,code='PRINT-IDENTITY',name='Print identity',entity_type='PURCHASE_ORDER')
    db.add(workflow);db.flush()
    request=ApprovalRequest(id=1,workflow_id=1,entity_type='PURCHASE_ORDER',entity_id=1,status='APPROVED',created_by_id=2)
    request.steps=[ApprovalRequestStep(id=1,step_order=1,name='Store Approval',approver_role_name='STORE',status='APPROVED',approved_by_id=1,decided_at=WHEN)]
    db.add(request);db.commit()
    result=document_context(db,'PURCHASE_ORDER',1,'APPROVED',ADMIN)
    record=result['approval_history'][0]
    assert record['approver_id']==1 and record['approver_name']=='Store Owner'
    assert record['decided_at'].hour==1 and 'signature_image' in record
    request.steps[0].approved_by_id=2;db.commit();db.expire_all()
    result=document_context(db,'PURCHASE_ORDER',1,'APPROVED',ADMIN)
    assert result['approval_history'][0]['approver_name']=='Another Approver'
    assert 'signature_image' not in result['approval_history'][0]

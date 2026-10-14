"""Unfinished purchasing documents and reversible archive of failed documents."""
from fastapi import HTTPException
from sqlalchemy import func
from app.models.purchase_requisition import PurchaseRequisition
from app.models.purchase_order import PurchaseOrder
from app.models.market_list import MarketList
from app.models.goods_receipt import GoodsReceipt
from app.models.journal_entry import JournalEntry
from app.models.supplier_invoice import SupplierInvoiceLine
from app.models.audit_log import AuditLog
from app.models.approval_request import ApprovalRequest
from app.services.approval import get_request
from app.services.activity_service import ActivityService
from app.services.location_access import apply_location_scope, enforce_location_access
from app.dependencies.authorization import has_permission
from app.services.organization_access import resolve_organization_access, effective_business_unit

SOURCES = {
    'PURCHASE_REQUISITION':(PurchaseRequisition,'pr_number','request_date','pr.view','pr.manage','purchase-requisitions',{'ORDERED','CLOSED','COMPLETED'}),
    'MARKET_LIST':(MarketList,'ml_number','request_date','market_list.view','market_list.manage','market-lists',{'CONVERTED','CLOSED','COMPLETED'}),
    'PURCHASE_ORDER':(PurchaseOrder,'po_number','order_date','po.view','po.manage','purchase-orders',{'RECEIVED','CLOSED','COMPLETED'}),
    'GOODS_RECEIPT':(GoodsReceipt,'receipt_number','received_at','receiving.view','receiving.manage','receiving',{'POSTED','RETURNED'}),
}


def unfinished_documents(db,user,date_from=None,date_to=None,archived=False,business_unit_id=None):
    scope=resolve_organization_access(db,user,business_unit_id=business_unit_id)
    result=[]
    for kind,(model,number,date_field,view,manage,path,complete) in SOURCES.items():
        if not has_permission(user, view):
            continue
        query=apply_location_scope(db.query(model), model, user)
        if scope["business_unit_id"] is not None:
            query=query.filter(effective_business_unit(model.business_unit_id,model.location_id)==scope["business_unit_id"])
        if scope["department_id"] is not None and hasattr(model,"department_id"):
            query=query.filter(model.department_id==scope["department_id"])
        query=query.filter(model.status=='ARCHIVED') if archived else query.filter(model.status.notin_([*complete,'ARCHIVED']))
        day=func.date(getattr(model,date_field))
        if date_from: query=query.filter(day>=date_from)
        if date_to: query=query.filter(day<=date_to)
        documents=query.order_by(getattr(model,date_field),model.id).all()
        requests=db.query(ApprovalRequest).filter(ApprovalRequest.entity_type==kind,ApprovalRequest.entity_id.in_([d.id for d in documents])).order_by(ApprovalRequest.id).all() if documents else []
        approval_by_document={r.entity_id:r for r in requests}
        for document in documents:
            request=approval_by_document.get(document.id)
            failed=document.status in {'REJECTED','CANCELLED','VOID'} or bool(request and request.status=='REJECTED')
            result.append(dict(entity_type=kind,id=document.id,number=getattr(document,number),
                date=getattr(document,date_field),status=document.status,location_id=document.location_id,
                url=f'/{path}/{document.id}',can_archive=failed and has_permission(user,manage),
                can_restore=archived and has_permission(user,manage)))
    return result


def archive_document(db,user,kind,document_id,reason,restore=False):
    if kind not in SOURCES:
        raise HTTPException(422,'Unsupported purchasing document')
    model,number,_,_,manage,_,_=SOURCES[kind]
    if not has_permission(user,manage):
        raise HTTPException(403,'Purchasing management permission required')
    document=db.query(model).filter_by(id=document_id).with_for_update().first()
    if not document: raise HTTPException(404,'Document not found')
    enforce_location_access(user,document.location_id)
    if not reason or len(reason.strip())<3:
        raise HTTPException(422,'A reason is required')
    old=document.status
    if restore:
        if old!='ARCHIVED': raise HTTPException(409,'Document is not archived')
        evidence=db.query(AuditLog).filter_by(entity_type=kind,entity_id=document_id,action='ARCHIVE').order_by(AuditLog.id.desc()).first()
        previous=(evidence.details or {}).get('previous_status') if evidence else None
        if not previous: raise HTTPException(409,'Archive history is missing')
        document.status=previous
    else:
        request=get_request(db,kind,document_id)
        if old not in {'REJECTED','CANCELLED','VOID'} and not (old=='DRAFT' and request and request.status=='REJECTED'):
            raise HTTPException(409,'Only failed or cancelled documents can be archived')
        dependencies=[]
        if kind=='PURCHASE_REQUISITION': dependencies=list(document.purchase_orders)+list(document.legacy_purchase_orders)
        if kind=='MARKET_LIST': dependencies=list(document.purchase_orders)+db.query(GoodsReceipt).filter_by(market_list_id=document_id).all()
        if kind=='PURCHASE_ORDER': dependencies=list(document.goods_receipts)
        if kind=='GOODS_RECEIPT':
            if db.query(JournalEntry).filter_by(reference_type=kind,reference_id=document_id).first():
                raise HTTPException(409,'Receiving has accounting evidence; resolve the source first')
            if db.query(SupplierInvoiceLine).filter(SupplierInvoiceLine.goods_receipt_item_id.in_([i.id for i in document.items])).first():
                raise HTTPException(409,'Receiving has supplier invoice links')
        if dependencies:
            raise HTTPException(409,'Document has downstream source links and cannot be archived')
        document.status='ARCHIVED'
    ActivityService.log(db=db,user=user,action='RESTORE' if restore else 'ARCHIVE',entity_type=kind,
        entity_id=document_id,summary=f'{"Restored" if restore else "Archived"} {getattr(document,number)}',
        document_number=getattr(document,number),document_status=document.status,
        details={'previous_status':old,'reason':reason.strip()})
    db.commit()
    return {'id':document_id,'status':document.status}

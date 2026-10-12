"""Count issued print requests; opening a preview does not issue a copy."""
from fastapi import HTTPException
from sqlalchemy import func
from app.models.audit_log import AuditLog
from app.models.store_request import StoreRequest
from app.models.stock_opname import StockOpname
from app.services.purchasing_exceptions import SOURCES
from app.services.activity_service import ActivityService
from app.dependencies.authorization import has_permission
from app.services.location_access import enforce_location_access


def record_print(db,user,kind,document_id,request_id):
    sources={**SOURCES,'STORE_REQUEST':(StoreRequest,'sr_number',None,'store_request.view'),
             'STOCK_OPNAME':(StockOpname,'opname_number',None,'stock_opname.view')}
    source=sources.get(kind)
    if not source: raise HTTPException(422,'Unsupported print document')
    model,number,_,view,*_=source
    if not has_permission(user,view): raise HTTPException(403,'Document view permission required')
    document=db.query(model).filter_by(id=document_id).with_for_update().first()
    if not document: raise HTTPException(404,'Document not found')
    enforce_location_access(user,document.location_id)
    events=db.query(AuditLog).filter_by(entity_type=kind,entity_id=document_id)
    exists=events.filter(AuditLog.action=='PRINT',AuditLog.details['request_id'].as_string()==request_id).first()
    if not exists:
        ActivityService.log(db=db,user=user,action='PRINT',entity_type=kind,entity_id=document_id,
            summary=f'Issued print copy {getattr(document,number)}',document_number=getattr(document,number),
            document_status=document.status,details={'request_id':request_id})
        db.flush()
    count=events.filter(AuditLog.action=='PRINT').count()
    corrections=events.filter(AuditLog.action.in_(['COST_CORRECTION','CORRECTION','UNPOST'])).count()
    db.commit()
    return {'print_count':count,'reprint_number':max(0,count-1),'correction_count':corrections}

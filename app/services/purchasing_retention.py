"""Age cleanup of abandoned purchasing documents; never remove source evidence."""
from calendar import monthrange
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select
from app.models.purchase_order import PurchaseOrder, purchase_order_requisition_table
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_requisition import PurchaseRequisition
from app.models.purchase_requisition_item import PurchaseRequisitionItem
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.models.stock_movement import StockMovement
from app.models.fixed_asset import FixedAsset
from app.models.account_payable import AccountPayable
from app.models.journal_entry import JournalEntry
from app.models.approval_request import ApprovalRequest
from app.models.audit_log import AuditLog
from app.services.activity_service import ActivityService
from app.services.organization_access import resolve_organization_access, effective_business_unit
from app.dependencies.authorization import has_permission

CLOSED = {'CLOSED','COMPLETED','RECEIVED','ORDERED'}


def today():
    return datetime.now(ZoneInfo('Asia/Jakarta')).date()


def months_before(day, months):
    value=day.year*12+day.month-1-months
    year,month=divmod(value,12);month+=1
    return date(year,month,min(day.day,monthrange(year,month)[1]))


def _exists(db, model, *conditions):
    return db.query(model).filter(*conditions).first() is not None


def dependencies(db, kind, document):
    if kind=='PURCHASE_REQUISITION':
        items=select(PurchaseRequisitionItem.id).where(PurchaseRequisitionItem.purchase_requisition_id==document.id)
        linked=(_exists(db,PurchaseOrder,PurchaseOrder.purchase_requisition_id==document.id)
            or db.execute(select(purchase_order_requisition_table.c.purchase_order_id).where(purchase_order_requisition_table.c.purchase_requisition_id==document.id)).first()
            or _exists(db,PurchaseOrderItem,PurchaseOrderItem.purchase_requisition_item_id.in_(items)))
        if linked:return 'LINKED_PURCHASE_ORDER'
    else:
        items=select(PurchaseOrderItem.id).where(PurchaseOrderItem.purchase_order_id==document.id)
        checks=[(GoodsReceipt,GoodsReceipt.purchase_order_id==document.id),
            (GoodsReceiptItem,GoodsReceiptItem.purchase_order_item_id.in_(items)),
            (SupplierInvoice,SupplierInvoice.purchase_order_id==document.id),
            (SupplierInvoiceLine,SupplierInvoiceLine.purchase_order_item_id.in_(items)),
            (StockMovement,StockMovement.purchase_order_id==document.id),
            (StockMovement,StockMovement.purchase_order_item_id.in_(items)),
            (FixedAsset,FixedAsset.purchase_order_id==document.id),
            (AccountPayable,AccountPayable.purchase_order_id==document.id)]
        if any(_exists(db,model,condition) for model,condition in checks):return 'LINKED_SOURCE_DOCUMENT'
        if _exists(db,PurchaseOrderItem,PurchaseOrderItem.purchase_order_id==document.id,PurchaseOrderItem.received_quantity>0):return 'RECEIVED_QUANTITY'
    if _exists(db,JournalEntry,JournalEntry.reference_type==kind,JournalEntry.reference_id==document.id):return 'ACCOUNTING_EVIDENCE'
    return None


def approval_snapshot(request):
    if not request:return None
    return {'status':request.status,'workflow_id':request.workflow_id,'current_step_order':request.current_step_order,
        'steps':[{'order':s.step_order,'status':s.status,'approved_by_id':s.approved_by_id,'decided_at':s.decided_at.isoformat() if s.decided_at else None} for s in request.steps]}


def cleanup(db, *, as_of=None, apply=False, user=None):
    day=as_of or today()
    if apply and day>today():raise HTTPException(422,'Cleanup date must not be in the future')
    if user and not all(has_permission(user,p) for p in ('po.manage','pr.manage')):
        raise HTTPException(403,'PO and PR management permission required')
    scope=resolve_organization_access(db,user) if user else None
    result={'mode':'APPLY' if apply else 'DRY_RUN','as_of':str(day),'counts':{'PO_TO_TRASH':0,'PR_DELETE':0,'PROTECTED':0},'items':[]}
    for kind,model,field,number,months in [('PURCHASE_ORDER',PurchaseOrder,'order_date','po_number',6),('PURCHASE_REQUISITION',PurchaseRequisition,'request_date','pr_number',3)]:
        cutoff=months_before(day,months);last_id=0
        while True:
            q=db.query(model).filter(model.id>last_id,getattr(model,field)<cutoff,model.status.notin_(CLOSED|({'ARCHIVED'} if kind=='PURCHASE_ORDER' else set())))
            if scope:
                for key in ('location_id','department_id','business_unit_id'):
                    value=scope[key]
                    if value is not None:
                        column=effective_business_unit(model.business_unit_id,model.location_id) if key=='business_unit_id' else getattr(model,key)
                        q=q.filter(column==value)
            if apply:q=q.with_for_update(skip_locked=True)
            documents=q.order_by(model.id).limit(250).all()
            if not documents:break
            for document in documents:
                last_id=document.id
                if kind=='PURCHASE_ORDER':
                    restored=db.query(AuditLog).filter_by(entity_type=kind,entity_id=document.id,action='RESTORE').order_by(AuditLog.id.desc()).first()
                    if restored and restored.created_at and restored.created_at.replace(tzinfo=restored.created_at.tzinfo or timezone.utc).astimezone(ZoneInfo('Asia/Jakarta')).date()>=cutoff:continue
                reason=dependencies(db,kind,document)
                action='PROTECTED' if reason else 'PO_TO_TRASH' if kind=='PURCHASE_ORDER' else 'PR_DELETE'
                result['counts'][action]+=1
                result['items'].append({'entity_type':kind,'id':document.id,'number':getattr(document,number),'date':str(getattr(document,field)),'action':action,'reason':reason})
                if not apply or reason:continue
                old=document.status
                request=db.query(ApprovalRequest).filter_by(entity_type=kind,entity_id=document.id).with_for_update().first()
                details={'policy':'PURCHASING_AGE','location_id':document.location_id,'department_id':document.department_id,'business_unit_id':document.business_unit_id,'previous_status':old,'cutoff':str(cutoff),'as_of':str(day),'approval':approval_snapshot(request)}
                if kind=='PURCHASE_ORDER':
                    document.status='ARCHIVED'
                    if request:
                        request.status='CANCELLED';request.current_step_order=None;request.completed_at=datetime.now(timezone.utc)
                        for step in request.steps:
                            if step.status in ('PENDING','WAITING'):step.status='CANCELLED'
                    audit_action='ARCHIVE'
                else:
                    details['items']=[{'product_id':i.product_id,'quantity':str(i.quantity),'estimated_price':str(i.estimated_price)} for i in document.items]
                    if request:db.delete(request)
                    from app.models.import_batch import ImportRow
                    for imported in db.query(ImportRow).filter_by(entity_type=kind,entity_id=document.id):
                        imported.status='DELETED'
                        imported.normalized_data_json={**(imported.normalized_data_json or {}),'deleted_by_retention':str(day)}
                    db.delete(document);audit_action='DELETE'
                ActivityService.log(db=db,user=user,action=audit_action,entity_type=kind,entity_id=document.id,
                    summary=f'Age cleanup: {getattr(document,number)}',document_number=getattr(document,number),document_status=document.status,
                    details=details)
            if apply:db.flush()
    return result


def validate_po_restore(db,document):
    """Archiving releases source quantities; restoring must reserve them again."""
    from app.models.market_list import MarketListItem
    sources={}
    for item in db.query(PurchaseOrderItem).filter_by(purchase_order_id=document.id).all():
        for field,model in (('purchase_requisition_item_id',PurchaseRequisitionItem),('market_list_item_id',MarketListItem)):
            source_id=getattr(item,field)
            if source_id:
                key=(field,source_id)
                sources[key]=sources.get(key,0)+item.quantity
    for (field,source_id),requested in sorted(sources.items()):
        model=PurchaseRequisitionItem if field=='purchase_requisition_item_id' else MarketListItem
        source=db.query(model).filter(model.id==source_id).with_for_update().first()
        used=db.query(PurchaseOrderItem).join(PurchaseOrder).filter(getattr(PurchaseOrderItem,field)==source_id,
            PurchaseOrder.id!=document.id,PurchaseOrder.status.notin_(('CANCELLED','ARCHIVED','REJECTED','VOID'))).all()
        allocated=sum(i.quantity for i in used)
        if field=='market_list_item_id':
            allocated+=sum(i.quantity for i in db.query(GoodsReceiptItem).join(GoodsReceipt).filter(
                GoodsReceiptItem.market_list_item_id==source_id,GoodsReceipt.purchase_order_id.is_(None),
                GoodsReceipt.status.notin_(('CANCELLED','ARCHIVED','REJECTED','VOID'))))
        if not source or requested+allocated>source.quantity:
            raise HTTPException(409,'Source quantities are already committed; resolve other orders/receiving before restoring this PO')

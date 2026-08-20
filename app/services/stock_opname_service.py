from datetime import date, datetime, timezone
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.stock_opname import StockOpname, StockOpnameItem
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.stock_opname import StockOpnameCountUpdate, StockOpnameCreate
from app.services.activity_service import AuditService
from app.services.approval import approve_current_step, get_request, reject_current_step, start_approval
from app.services.document_number import next_document_number
from app.services.organization_dimensions import validate_dimensions
ZERO=Decimal("0")
class StockOpnameService:
 @staticmethod
 def _get(db:Session,opname_id:int,*,lock:bool=False)->StockOpname:
  q=db.query(StockOpname).filter(StockOpname.id==opname_id);q=q.with_for_update() if lock else q;row=q.first()
  if not row:raise HTTPException(404,"Stock Opname not found")
  return row
 @staticmethod
 def create(db:Session,*,data:StockOpnameCreate,current_user:User)->StockOpname:
  wh=db.get(Warehouse,data.warehouse_id)
  if not wh or not wh.is_active:raise HTTPException(404,"Active warehouse not found")
  bu=data.business_unit_id or current_user.default_business_unit_id;loc=data.location_id or current_user.default_location_id or current_user.location_id;dep=data.department_id or current_user.default_department_id or current_user.department_id;validate_dimensions(db,bu,loc,dep,True)
  if db.query(StockOpname).filter(StockOpname.warehouse_id==wh.id,StockOpname.status.in_(["DRAFT","PENDING_APPROVAL","APPROVED"])).first():raise HTTPException(409,"Warehouse already has an active Stock Opname")
  op=StockOpname(opname_number=next_document_number(db,"SO"),status="DRAFT",count_date=data.count_date or date.today(),warehouse_id=wh.id,business_unit_id=bu,location_id=loc,department_id=dep,created_by_id=current_user.id,notes=data.notes)
  for inv in db.query(Inventory).filter(Inventory.warehouse_id==wh.id).order_by(Inventory.product_id).all():
   product=db.get(Product,inv.product_id)
   if product and product.is_active:op.items.append(StockOpnameItem(product_id=product.id,system_quantity=Decimal(inv.quantity or 0),unit_cost=Decimal(inv.average_cost or 0),uom=product.uom))
  db.add(op);db.flush();AuditService.log(db=db,user=current_user,action="CREATE",entity_type="STOCK_OPNAME",entity_id=op.id,summary=f"Created {op.opname_number}",document_type="SO",document_number=op.opname_number,document_status=op.status);db.commit();db.refresh(op);return op
 @staticmethod
 def update_counts(db:Session,*,opname_id:int,data:StockOpnameCountUpdate,current_user:User)->StockOpname:
  op=StockOpnameService._get(db,opname_id,lock=True)
  if op.status!="DRAFT":raise HTTPException(409,"Only draft Stock Opname can be counted")
  by_id={i.id:i for i in op.items};seen=set()
  for incoming in data.items:
   if incoming.item_id in seen:raise HTTPException(409,f"Duplicate Stock Opname item {incoming.item_id}")
   seen.add(incoming.item_id);item=by_id.get(incoming.item_id)
   if not item:raise HTTPException(404,f"Stock Opname item {incoming.item_id} not found")
   physical=Decimal(incoming.physical_quantity);item.physical_quantity=physical;item.variance_quantity=physical-Decimal(item.system_quantity)
  if data.notes is not None:op.notes=data.notes
  AuditService.log(db=db,user=current_user,action="COUNT",entity_type="STOCK_OPNAME",entity_id=op.id,summary=f"Updated physical count {op.opname_number}",document_type="SO",document_number=op.opname_number,document_status=op.status);db.commit();db.refresh(op);return op
 @staticmethod
 def submit(db:Session,*,opname_id:int,current_user:User)->StockOpname:
  op=StockOpnameService._get(db,opname_id,lock=True)
  if op.status!="DRAFT":raise HTTPException(409,"Only draft Stock Opname can be submitted")
  if not op.items:raise HTTPException(409,"Stock Opname has no inventory snapshot")
  missing=[i.product.code for i in op.items if i.physical_quantity is None]
  if missing:raise HTTPException(409,"Physical count is incomplete: "+", ".join(missing[:10]))
  start_approval(db,entity_type="STOCK_OPNAME",entity_id=op.id,workflow_code="SO_APPROVAL",user=current_user);op.status="PENDING_APPROVAL";op.submitted_at=datetime.now(timezone.utc);AuditService.log(db=db,user=current_user,action="SUBMIT",entity_type="STOCK_OPNAME",entity_id=op.id,summary=f"Submitted {op.opname_number}",document_type="SO",document_number=op.opname_number,document_status=op.status);db.commit();db.refresh(op);return op
 @staticmethod
 def approve(db:Session,*,opname_id:int,data:ApprovalDecisionRequest|None,current_user:User)->StockOpname:
  op=StockOpnameService._get(db,opname_id,lock=True)
  if op.status!="PENDING_APPROVAL":raise HTTPException(409,"Stock Opname does not have pending approval")
  req=get_request(db,"STOCK_OPNAME",op.id,for_update=True)
  if not req:raise HTTPException(500,"Approval workflow not found")
  approve_current_step(db,request=req,user=current_user,comment=data.comment if data else None);db.flush();db.refresh(req)
  if req.status=="APPROVED":op.status="APPROVED"
  db.commit();db.refresh(op);return op
 @staticmethod
 def reject(db:Session,*,opname_id:int,data:ApprovalDecisionRequest|None,current_user:User)->StockOpname:
  op=StockOpnameService._get(db,opname_id,lock=True)
  if op.status!="PENDING_APPROVAL":raise HTTPException(409,"Stock Opname does not have pending approval")
  req=get_request(db,"STOCK_OPNAME",op.id,for_update=True)
  if not req:raise HTTPException(500,"Approval workflow not found")
  reject_current_step(db,request=req,user=current_user,comment=data.comment if data else None);op.status="REJECTED";db.commit();db.refresh(op);return op
 @staticmethod
 def post(db:Session,*,opname_id:int,current_user:User)->StockOpname:
  op=StockOpnameService._get(db,opname_id,lock=True)
  if op.status!="APPROVED":raise HTTPException(409,"Only approved Stock Opname can be posted")
  if op.posted_at is not None:raise HTTPException(409,"Stock Opname is already posted")
  prepared=[]
  for item in sorted(op.items,key=lambda r:(r.product_id,r.id)):
   if item.physical_quantity is None:raise HTTPException(409,"Stock Opname contains an incomplete physical count")
   inv=db.query(Inventory).filter(Inventory.warehouse_id==op.warehouse_id,Inventory.product_id==item.product_id).with_for_update().first()
   if not inv:raise HTTPException(409,f"Inventory row for {item.product.code} no longer exists")
   if Decimal(inv.quantity or 0)!=Decimal(item.system_quantity):raise HTTPException(409,f"Stock changed after snapshot for {item.product.code}; create a new Stock Opname")
   prepared.append((item,inv))
  for item,inv in prepared:
   physical=Decimal(item.physical_quantity);variance=physical-Decimal(item.system_quantity);item.variance_quantity=variance;inv.quantity=physical
   if variance!=ZERO:db.add(StockMovement(product_id=item.product_id,warehouse_id=op.warehouse_id,business_unit_id=op.business_unit_id,location_id=op.location_id,department_id=op.department_id,movement_type="IN" if variance>0 else "OUT",quantity=variance if variance>0 else -abs(variance),unit_cost=Decimal(item.unit_cost or 0),reference_type="STOCK_OPNAME",reference_id=op.id,notes=f"Stock Opname adjustment {op.opname_number}"))
  op.status="POSTED";op.posted_at=datetime.now(timezone.utc);op.posted_by_id=current_user.id;AuditService.log(db=db,user=current_user,action="POST",entity_type="STOCK_OPNAME",entity_id=op.id,summary=f"Posted {op.opname_number}",document_type="SO",document_number=op.opname_number,document_status=op.status);db.commit();db.refresh(op);return op

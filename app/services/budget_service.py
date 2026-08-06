from datetime import date
from decimal import Decimal
from math import ceil
from sqlalchemy import func,or_
from sqlalchemy.orm import Session,joinedload
from app.models.budget import Budget,BudgetLine
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.purchase_requisition import PurchaseRequisition
from app.models.purchase_order import PurchaseOrder
from app.models.supplier_invoice import SupplierInvoice,SupplierInvoiceLine
from app.services.document_number import next_document_number
from app.models.business_unit import BusinessUnit
from app.services.organization_dimensions import validate_dimensions
ZERO=Decimal("0.00")
class BudgetService:
 def __init__(self,db:Session):self.db=db
 def get(self,id):
  x=self.db.query(Budget).options(joinedload(Budget.lines).joinedload(BudgetLine.account),joinedload(Budget.lines).joinedload(BudgetLine.department),joinedload(Budget.lines).joinedload(BudgetLine.location)).filter(Budget.id==id).first()
  if not x:raise ValueError("Budget not found")
  return x
 def validate(self,data):
  if data.date_from>data.date_to or data.fiscal_year!=data.date_from.year or data.fiscal_year!=data.date_to.year:raise ValueError("Budget period must fall within its fiscal year")
  if not data.lines:raise ValueError("At least one budget line is required")
  seen=set()
  for l in data.lines:
   a=self.db.get(ChartOfAccount,l.account_id)
   if not a or not a.is_active or not a.is_posting:raise ValueError("Budget lines require active posting accounts")
   bu=self.db.get(BusinessUnit,l.business_unit_id)
   if not bu or not bu.is_active:raise ValueError("Budget lines require an active Business Unit")
   validate_dimensions(self.db,l.business_unit_id,l.location_id,l.department_id,required=True)
   if not data.date_from.month<=l.month<=data.date_to.month:raise ValueError("Budget line month is outside the budget period")
   key=(l.account_id,l.department_id,l.location_id,l.month,l.business_unit_id)
   if key in seen:raise ValueError("Duplicate budget line dimensions")
   seen.add(key)
 def create(self,data,user):self.validate(data);x=Budget(budget_number=next_document_number(self.db,"BUD"),created_by_id=user.id,**data.model_dump(exclude={"lines"}));x.lines=[BudgetLine(**l.model_dump()) for l in data.lines];self.db.add(x);self.db.flush();return x
 @staticmethod
 def actions(x):return {"can_edit":x.status=="DRAFT","can_submit":x.status=="DRAFT" and bool(x.lines),"can_approve":x.status=="SUBMITTED","can_reject":x.status=="SUBMITTED","can_lock":x.status=="APPROVED","can_cancel":x.status in ("DRAFT","SUBMITTED","APPROVED"),"can_print":True}
 def serialize(self,x):return {"id":x.id,"budget_number":x.budget_number,"name":x.name,"fiscal_year":x.fiscal_year,"date_from":x.date_from,"date_to":x.date_to,"status":x.status,"currency":x.currency,"description":x.description,"total_budget":sum((Decimal(l.budget_amount) for l in x.lines),ZERO),"created_by":x.created_by.full_name if x.created_by else None,"approved_by":x.approved_by.full_name if x.approved_by else None,"submitted_at":x.submitted_at,"approved_at":x.approved_at,"locked_at":x.locked_at,"cancelled_at":x.cancelled_at,"allowed_actions":self.actions(x),"lines":[{"id":l.id,"account_id":l.account_id,"account_code":l.account.account_number,"account_name":l.account.account_name,"department_id":l.department_id,"department_name":l.department.name if l.department else None,"location_id":l.location_id,"location_name":l.location.name if l.location else None,"business_unit_id":l.business_unit_id,"business_unit_code":l.business_unit_master.code if l.business_unit_master else None,"business_unit_name":l.business_unit_master.name if l.business_unit_master else None,"month":l.month,"budget_amount":l.budget_amount,"notes":l.notes} for l in x.lines]}
class BudgetVsActualService:
 def __init__(self,db):self.db=db
 def report(self,budget_id=None,fiscal_year=None,date_from=None,date_to=None,account_id=None,account_type=None,department_id=None,location_id=None,group_by="ACCOUNT",include_zero=False,search=None,page=1,page_size=50,business_unit_id=None):
  bq=self.db.query(Budget).filter(Budget.status.in_(["APPROVED","LOCKED"]));
  if budget_id:bq=bq.filter(Budget.id==budget_id)
  if fiscal_year:bq=bq.filter(Budget.fiscal_year==fiscal_year)
  budgets=bq.all();start=date_from or min((b.date_from for b in budgets),default=date.today().replace(month=1,day=1));end=date_to or max((b.date_to for b in budgets),default=date.today())
  groups={}
  for b in budgets:
   for l in b.lines:
    if account_id and l.account_id!=account_id:continue
    if account_type and l.account.account_type!=account_type:continue
    if department_id and l.department_id!=department_id:continue
    if location_id and l.location_id!=location_id:continue
    if business_unit_id and l.business_unit_id!=business_unit_id:continue
    if not start.month<=l.month<=end.month:continue
    key=l.account_id if group_by=="ACCOUNT" else l.business_unit_id if group_by=="BUSINESS_UNIT" else l.department_id if group_by=="DEPARTMENT" else l.location_id if group_by=="LOCATION" else l.month
    label=f"{l.account.account_number} — {l.account.account_name}" if group_by=="ACCOUNT" else (l.business_unit_master.name if l.business_unit_master else "Unassigned") if group_by=="BUSINESS_UNIT" else (l.department.name if l.department else "Unassigned") if group_by=="DEPARTMENT" else (l.location.name if l.location else "Unassigned") if group_by=="LOCATION" else f"{b.fiscal_year}-{l.month:02d}"
    g=groups.setdefault(key,{"group_key":key,"group_label":label,"account_id":l.account_id if group_by=="ACCOUNT" else None,"business_unit_id":l.business_unit_id if group_by=="BUSINESS_UNIT" else None,"department_id":l.department_id if group_by=="DEPARTMENT" else None,"location_id":l.location_id if group_by=="LOCATION" else None,"month":l.month if group_by=="MONTH" else None,"budget_amount":ZERO,"planned_pr":ZERO,"committed_po":ZERO,"payable_invoice":ZERO,"actual_amount":ZERO,"locked":b.status=="LOCKED"});g["budget_amount"]+=Decimal(l.budget_amount)
  for g in groups.values():
   aq=self.db.query(func.coalesce(func.sum(JournalLine.debit-JournalLine.credit),0)).join(JournalEntry).join(ChartOfAccount,ChartOfAccount.id==JournalLine.account_id).filter(JournalEntry.status=="POSTED",JournalEntry.posting_date>=start,JournalEntry.posting_date<=end,ChartOfAccount.account_type=="EXPENSE")
   if group_by=="ACCOUNT":aq=aq.filter(JournalLine.account_id==g["account_id"])
   if group_by=="BUSINESS_UNIT":aq=aq.filter(JournalLine.business_unit_id==g["business_unit_id"])
   if group_by=="DEPARTMENT":aq=aq.filter(JournalLine.department_id==g["department_id"])
   if group_by=="LOCATION":aq=aq.filter(JournalLine.location_id==g["location_id"])
   if group_by=="MONTH":aq=aq.filter(func.extract("month",JournalEntry.posting_date)==g["month"])
   if business_unit_id:aq=aq.filter(JournalLine.business_unit_id==business_unit_id)
   g["actual_amount"]=Decimal(aq.scalar())
   iq=self.db.query(func.coalesce(func.sum(SupplierInvoiceLine.line_amount*SupplierInvoice.balance_amount/func.nullif(SupplierInvoice.total_amount,0)),0)).join(SupplierInvoice).filter(SupplierInvoice.status!="VOID",SupplierInvoice.balance_amount>0,SupplierInvoice.invoice_date>=start,SupplierInvoice.invoice_date<=end)
   if group_by=="ACCOUNT":iq=iq.filter(SupplierInvoiceLine.account_id==g["account_id"])
   if group_by=="BUSINESS_UNIT":iq=iq.filter(SupplierInvoice.business_unit_id==g["business_unit_id"])
   if group_by=="DEPARTMENT":iq=iq.filter(func.coalesce(SupplierInvoiceLine.department_id,SupplierInvoice.department_id)==g["department_id"])
   if group_by=="LOCATION":iq=iq.filter(SupplierInvoice.location_id==g["location_id"])
   if group_by=="MONTH":iq=iq.filter(func.extract("month",SupplierInvoice.invoice_date)==g["month"])
   if business_unit_id:iq=iq.filter(SupplierInvoice.business_unit_id==business_unit_id)
   g["payable_invoice"]=Decimal(iq.scalar())
   if group_by!="ACCOUNT":
    pr=self.db.query(func.coalesce(func.sum(PurchaseRequisition.total_amount),0)).filter(PurchaseRequisition.status.in_(["SUBMITTED","PENDING_APPROVAL","APPROVED"]),PurchaseRequisition.request_date>=start,PurchaseRequisition.request_date<=end,~or_(PurchaseRequisition.purchase_orders.any(PurchaseOrder.status!="CANCELLED"),PurchaseRequisition.legacy_purchase_orders.any(PurchaseOrder.status!="CANCELLED")))
    po=self.db.query(func.coalesce(func.sum(PurchaseOrder.total_amount),0)).filter(PurchaseOrder.status.in_(["APPROVED","PARTIALLY_RECEIVED","RECEIVED"]),PurchaseOrder.order_date>=start,PurchaseOrder.order_date<=end)
    if group_by=="DEPARTMENT":pr=pr.filter(PurchaseRequisition.department_id==g["department_id"]);po=po.filter(PurchaseOrder.department_id==g["department_id"])
    if group_by=="BUSINESS_UNIT":pr=pr.filter(PurchaseRequisition.business_unit_id==g["business_unit_id"]);po=po.filter(PurchaseOrder.business_unit_id==g["business_unit_id"])
    if group_by=="LOCATION":pr=pr.filter(PurchaseRequisition.location_id==g["location_id"]);po=po.filter(PurchaseOrder.location_id==g["location_id"])
    if group_by=="MONTH":pr=pr.filter(func.extract("month",PurchaseRequisition.request_date)==g["month"]);po=po.filter(func.extract("month",PurchaseOrder.order_date)==g["month"])
    if business_unit_id:pr=pr.filter(PurchaseRequisition.business_unit_id==business_unit_id);po=po.filter(PurchaseOrder.business_unit_id==business_unit_id)
    g["planned_pr"]=Decimal(pr.scalar());g["committed_po"]=Decimal(po.scalar())
   b,a,c=g["budget_amount"],g["actual_amount"],g["committed_po"];g["remaining_budget"]=b-a;g["available_after_commitments"]=b-a-c;g["variance_amount"]=a-b;g["variance_percentage"]=(a-b)/b*100 if b else None;g["utilization_percentage"]=a/b*100 if b else None;g["status"]="LOCKED" if g["locked"] else "NO_BUDGET" if not b else "OVER_BUDGET" if a>b else "NEAR_LIMIT" if a/b>=Decimal("0.8") else "WITHIN_BUDGET"
  rows=list(groups.values());
  if search:rows=[x for x in rows if search.lower() in x["group_label"].lower()]
  if not include_zero:rows=[x for x in rows if any(x[k]!=ZERO for k in ("budget_amount","actual_amount","committed_po","payable_invoice"))]
  total=len(rows);summary={k:sum((x[k] for x in rows),ZERO) for k in ("budget_amount","planned_pr","committed_po","payable_invoice","actual_amount","remaining_budget","available_after_commitments")};summary.update({"near_limit_count":sum(x["status"]=="NEAR_LIMIT" for x in rows),"over_budget_count":sum(x["status"]=="OVER_BUDGET" for x in rows)});return {"items":rows[(page-1)*page_size:page*page_size],"summary":summary,"page":page,"page_size":page_size,"total_items":total,"total_pages":ceil(total/page_size) if total else 0,"limitations":["PR and PO lack account-level expense linkage; planned and committed values are available for department, location, and month grouping."]}

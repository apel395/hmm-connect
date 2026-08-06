from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.approval_request import ApprovalRequest, ApprovalRequestStep
from app.models.bank_reconciliation import BankReconciliation
from app.models.budget import Budget, BudgetLine
from app.models.fixed_asset import FixedAsset, FixedAssetDepreciationSchedule, FixedAssetDepreciationRun
from app.models.chart_of_account import ChartOfAccount
from app.models.goods_receipt import GoodsReceipt
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.payment import Payment
from app.models.purchase_order import PurchaseOrder, purchase_order_requisition_table
from app.models.purchase_requisition import PurchaseRequisition
from app.models.supplier_invoice import SupplierInvoice
from app.services.cash_flow_service import CashFlowService, ZERO
from app.services.financial_statement_service import FinancialStatementService
from app.services.trial_balance_service import TrialBalanceService
from app.services.budget_service import BudgetVsActualService


class FinanceDashboardService:
    def __init__(self,db:Session,user):self.db=db;self.user=user
    @staticmethod
    def interval(date_from,date_to):
        days=(date_to-date_from).days+1
        return "DAILY" if days<=31 else "WEEKLY" if days<=120 else "MONTHLY"
    @staticmethod
    def period_key(value,interval):
        return value.isoformat() if interval=="DAILY" else f"{value.isocalendar().year}-W{value.isocalendar().week:02d}" if interval=="WEEKLY" else value.strftime("%Y-%m")
    @staticmethod
    def status_counts(query,column):return {status:int(count) for status,count in query.with_entities(column,func.count()).group_by(column).all()}
    def _cash(self,date_from,date_to,account_id,location_id,department_id,business_unit_id=None):
        svc=CashFlowService(self.db);accounts=svc.accounts_summary(date_from,date_to,location_id,business_unit_id)
        if account_id:accounts=[row for row in accounts if row["account_id"]==account_id]
        allowed={row["account_id"] for row in accounts};summary=svc.summary(date_from,date_to,account_id,None,location_id,department_id,business_unit_id)
        totals={"CASH":ZERO,"BANK":ZERO,"PETTY_CASH":ZERO}
        for row in accounts:totals[row["account_subtype"]]+=row["closing_balance"]
        serialized=[{"account_id":row["account_id"],"account_code":row["account_code"],"account_name":row["account_name"],"account_subtype":row["account_subtype"],"opening_balance":row["opening_balance"],"period_inflow":row["total_inflow"],"period_outflow":row["total_outflow"],"current_balance":row["closing_balance"],"last_transaction_date":row["last_transaction_date"],"currency":"IDR"} for row in accounts]
        return {"accounts":serialized,"total_cash":totals["CASH"],"total_bank":totals["BANK"],"total_petty_cash":totals["PETTY_CASH"],"total_liquid_cash":sum(totals.values(),ZERO)},summary,svc,allowed
    def _ap(self,as_of):
        q=self.db.query(SupplierInvoice).options(joinedload(SupplierInvoice.supplier)).filter(SupplierInvoice.status!="VOID",SupplierInvoice.balance_amount>0)
        invoices=q.all();buckets={"total_outstanding_ap":ZERO,"overdue_ap":ZERO,"due_today":ZERO,"due_next_7_days":ZERO,"due_next_30_days":ZERO}
        urgent=[]
        for inv in invoices:
            amount=Decimal(inv.balance_amount);buckets["total_outstanding_ap"]+=amount
            if inv.due_date:
                if inv.due_date<as_of:buckets["overdue_ap"]+=amount
                elif inv.due_date==as_of:buckets["due_today"]+=amount
                elif inv.due_date<=as_of+timedelta(days=7):buckets["due_next_7_days"]+=amount
                elif inv.due_date<=as_of+timedelta(days=30):buckets["due_next_30_days"]+=amount
            if inv.due_date and inv.due_date<=as_of+timedelta(days=7):urgent.append({"invoice_id":inv.id,"internal_invoice_number":inv.internal_invoice_number,"supplier_invoice_number":inv.supplier_invoice_number,"supplier":inv.supplier.name,"due_date":inv.due_date,"outstanding_balance":amount,"days_overdue":max((as_of-inv.due_date).days,0),"status":inv.payment_status})
        urgent.sort(key=lambda row:(row["due_date"],-row["outstanding_balance"]))
        buckets.update({"unpaid_invoice_count":sum(inv.payment_status=="UNPAID" for inv in invoices),"partially_paid_invoice_count":sum(inv.payment_status=="PARTIALLY_PAID" for inv in invoices),"overdue_invoice_count":sum(bool(inv.due_date and inv.due_date<as_of) for inv in invoices),"urgent_invoices":urgent[:10]})
        return buckets,invoices
    def _purchasing(self,location_id,department_id,business_unit_id=None):
        prq=self.db.query(PurchaseRequisition);poq=self.db.query(PurchaseOrder);grq=self.db.query(GoodsReceipt)
        if location_id:prq=prq.filter(PurchaseRequisition.location_id==location_id);poq=poq.filter(PurchaseOrder.location_id==location_id)
        if department_id:prq=prq.filter(PurchaseRequisition.department_id==department_id);poq=poq.filter(PurchaseOrder.department_id==department_id)
        if business_unit_id:prq=prq.filter(PurchaseRequisition.business_unit_id==business_unit_id);poq=poq.filter(PurchaseOrder.business_unit_id==business_unit_id);grq=grq.filter(GoodsReceipt.business_unit_id==business_unit_id)
        pr_counts=self.status_counts(prq,PurchaseRequisition.status);po_counts=self.status_counts(poq,PurchaseOrder.status);gr_counts=self.status_counts(grq,GoodsReceipt.status)
        active_po=or_(PurchaseRequisition.purchase_orders.any(PurchaseOrder.status!="CANCELLED"),PurchaseRequisition.legacy_purchase_orders.any(PurchaseOrder.status!="CANCELLED"))
        unconverted=prq.filter(PurchaseRequisition.status.in_(["SUBMITTED","PENDING_APPROVAL","APPROVED"]),~active_po)
        planned=Decimal(unconverted.with_entities(func.coalesce(func.sum(PurchaseRequisition.total_amount),0)).scalar())
        invoiced=self.db.query(SupplierInvoice.purchase_order_id.label("po_id"),func.sum(SupplierInvoice.total_amount).label("amount")).filter(SupplierInvoice.status!="VOID",SupplierInvoice.purchase_order_id.isnot(None)).group_by(SupplierInvoice.purchase_order_id).subquery()
        commitment_q=poq.outerjoin(invoiced,invoiced.c.po_id==PurchaseOrder.id).filter(PurchaseOrder.status.in_(["APPROVED","PARTIALLY_RECEIVED","RECEIVED"]),PurchaseOrder.status!="CANCELLED",PurchaseOrder.total_amount>func.coalesce(invoiced.c.amount,0))
        committed=Decimal(commitment_q.with_entities(func.coalesce(func.sum(PurchaseOrder.total_amount-func.coalesce(invoiced.c.amount,0)),0)).scalar())
        waiting_receipt=poq.filter(PurchaseOrder.status.in_(["APPROVED","PARTIALLY_RECEIVED"])).count()
        return {"purchase_requisitions":{"draft":pr_counts.get("DRAFT",0),"submitted":pr_counts.get("SUBMITTED",0),"waiting_approval":pr_counts.get("PENDING_APPROVAL",0),"approved":pr_counts.get("APPROVED",0),"rejected":pr_counts.get("REJECTED",0),"not_converted_to_po":unconverted.count(),"planned_value":planned},"purchase_orders":{"draft":po_counts.get("DRAFT",0),"waiting_approval":po_counts.get("PENDING_APPROVAL",0),"approved":po_counts.get("APPROVED",0),"partially_received":po_counts.get("PARTIALLY_RECEIVED",0),"received":po_counts.get("RECEIVED",0),"not_fully_invoiced":commitment_q.count(),"committed_value":committed},"goods_receipts":{"waiting_receipt":waiting_receipt,"pending_posting":gr_counts.get("DRAFT",0),"posted":gr_counts.get("POSTED",0),"warehouse":grq.filter(GoodsReceipt.destination_type=="WAREHOUSE").count(),"direct_use":grq.filter(GoodsReceipt.destination_type=="DIRECT_USE").count()}},commitment_q,unconverted
    def _approvals(self):
        roles={role.name for role in self.user.roles};q=self.db.query(ApprovalRequestStep).options(joinedload(ApprovalRequestStep.request).joinedload(ApprovalRequest.created_by)).join(ApprovalRequest).filter(ApprovalRequest.status=="PENDING",ApprovalRequestStep.status=="PENDING")
        if "ADMIN" not in roles:q=q.filter(ApprovalRequestStep.approver_role_name.in_(roles))
        steps=[]
        for step in q.order_by(ApprovalRequest.created_at).limit(20):
            if step.department_name and (not self.user.department or self.user.department.name!=step.department_name):continue
            if step.location_name and (not self.user.location or self.user.location.name!=step.location_name):continue
            req=step.request;document_number=str(req.entity_id);amount=ZERO;party=req.created_by.full_name if req.created_by else None;route="/"
            if req.entity_type=="PURCHASE_REQUISITION":
                entity=self.db.get(PurchaseRequisition,req.entity_id)
                if entity:document_number=entity.pr_number;amount=Decimal(entity.total_amount);route=f"/purchase-requisitions/{entity.id}"
            elif req.entity_type=="PURCHASE_ORDER":
                entity=self.db.get(PurchaseOrder,req.entity_id)
                if entity:document_number=entity.po_number;amount=Decimal(entity.total_amount);party=entity.supplier.name;route=f"/purchase-orders/{entity.id}"
            elif req.entity_type=="PAYMENT":route=f"/payments/{req.entity_id}"
            steps.append({"document_type":req.entity_type,"entity_id":req.entity_id,"document_number":document_number,"date":req.created_at.date(),"requester_or_supplier":party,"amount":amount,"current_approval_level":step.name,"route":route})
        counts=defaultdict(int)
        for row in steps:counts[row["document_type"]]+=1
        return {"total_pending_for_me":len(steps),"counts_by_document_type":dict(counts),"items":steps[:10]}
    def _timeline(self,date_from,date_to,interval,cash_svc,ap_invoices,commitment_q,unconverted):
        cash=defaultdict(lambda:{"inflow":ZERO,"outflow":ZERO});opening=cash_svc.opening(date_from)
        for movement in cash_svc.movements(date_from,date_to):
            if movement["direction"]=="TRANSFER":continue
            point=cash[self.period_key(movement["date"],interval)];point["inflow"]+=movement["inflow"];point["outflow"]+=movement["outflow"]
        balance=opening;cash_points=[]
        for period,values in sorted(cash.items()):balance+=values["inflow"]-values["outflow"];cash_points.append({"period":period,**values,"net":values["inflow"]-values["outflow"],"closing_balance":balance})
        ap=defaultdict(lambda:{"due_amount":ZERO,"overdue_amount":ZERO})
        for inv in ap_invoices:
            if inv.due_date and date_from<=inv.due_date<=date_to:
                p=ap[self.period_key(inv.due_date,interval)];p["due_amount"]+=Decimal(inv.balance_amount)
                if inv.due_date<date.today():p["overdue_amount"]+=Decimal(inv.balance_amount)
        profit=defaultdict(lambda:{"revenue":ZERO,"expense":ZERO})
        rows=self.db.query(JournalEntry.posting_date,ChartOfAccount.account_type,func.sum(JournalLine.debit),func.sum(JournalLine.credit)).select_from(JournalEntry).join(JournalLine,JournalLine.journal_entry_id==JournalEntry.id).join(ChartOfAccount,ChartOfAccount.id==JournalLine.account_id).filter(JournalEntry.status=="POSTED",JournalEntry.posting_date>=date_from,JournalEntry.posting_date<=date_to,ChartOfAccount.account_type.in_(["REVENUE","EXPENSE"])).group_by(JournalEntry.posting_date,ChartOfAccount.account_type).all()
        for d,kind,debit,credit in rows:
            point=profit[self.period_key(d,interval)];point["revenue" if kind=="REVENUE" else "expense"]+=Decimal(credit)-Decimal(debit) if kind=="REVENUE" else Decimal(debit)-Decimal(credit)
        purchase=defaultdict(lambda:{"planned_pr":ZERO,"committed_po":ZERO,"payable_invoices":ZERO,"actual_payments":ZERO})
        for pr in unconverted.all():
            if date_from<=pr.request_date<=date_to:purchase[self.period_key(pr.request_date,interval)]["planned_pr"]+=Decimal(pr.total_amount)
        for po in commitment_q.all():
            if date_from<=po.order_date<=date_to:purchase[self.period_key(po.order_date,interval)]["committed_po"]+=Decimal(po.total_amount)
        for inv in ap_invoices:
            if date_from<=inv.invoice_date<=date_to:purchase[self.period_key(inv.invoice_date,interval)]["payable_invoices"]+=Decimal(inv.balance_amount)
        payments=self.db.query(Payment).filter(Payment.status=="POSTED",Payment.payment_date>=date_from,Payment.payment_date<=date_to).all()
        for payment in payments:purchase[self.period_key(payment.payment_date,interval)]["actual_payments"]+=Decimal(payment.amount)
        return {"interval":interval,"cash_flow":cash_points,"ap_due":[dict(period=p,**v) for p,v in sorted(ap.items())],"profit":[{"period":p,**v,"net_profit":v["revenue"]-v["expense"]} for p,v in sorted(profit.items())],"purchase_commitments":[dict(period=p,**v) for p,v in sorted(purchase.items())]}
    def build(self,as_of_date,date_from,date_to,location_id=None,department_id=None,cash_account_id=None,currency=None,business_unit_id=None):
        if date_from>date_to:raise ValueError("date_from must be on or before date_to")
        cash_position,cash_summary,cash_svc,_=self._cash(date_from,date_to,cash_account_id,location_id,department_id,business_unit_id);ap,invoices=self._ap(as_of_date);purchasing,commitments,unconverted=self._purchasing(location_id,department_id,business_unit_id);approvals=self._approvals()
        due7=ap["overdue_ap"]+ap["due_today"]+ap["due_next_7_days"];due30=due7+ap["due_next_30_days"];current=cash_position["total_liquid_cash"]
        forecast={"current_cash":current,"overdue_payables":ap["overdue_ap"],"payables_due_7_days":due7,"payables_due_30_days":due30,"approved_po_commitments":purchasing["purchase_orders"]["committed_value"],"planned_pr_value":purchasing["purchase_requisitions"]["planned_value"],"forecast_after_due_7_days":current-due7,"forecast_after_due_30_days":current-due30,"forecast_after_all_outstanding_ap":current-ap["total_outstanding_ap"],"forecast_after_ap_and_po_commitments":current-ap["total_outstanding_ap"]-purchasing["purchase_orders"]["committed_value"]}
        month_start=date(as_of_date.year,as_of_date.month,1);previous_end=month_start-timedelta(days=1);previous_start=date(previous_end.year,previous_end.month,1);financial=FinancialStatementService(self.db);pl=financial.profit_and_loss(date_from=month_start,date_to=as_of_date,location_id=location_id,department_id=department_id,business_unit_id=business_unit_id);prev=financial.profit_and_loss(date_from=previous_start,date_to=previous_end,location_id=location_id,department_id=department_id,business_unit_id=business_unit_id);profit={**pl["summary"],"previous_month_net_profit":prev["summary"]["net_profit_after_tax"]};profit["net_profit_variance"]=profit["net_profit_after_tax"]-profit["previous_month_net_profit"];profit["net_profit_variance_percentage"]=profit["net_profit_variance"]/abs(profit["previous_month_net_profit"])*Decimal("100") if profit["previous_month_net_profit"] else None
        trial=TrialBalanceService(self.db).report(date_from=month_start,date_to=as_of_date,include_zero_balance=True,paginate=False,page_size=200,location_id=location_id,department_id=department_id,business_unit_id=business_unit_id);bs=financial.balance_sheet(as_of_date=as_of_date,location_id=location_id,department_id=department_id,business_unit_id=business_unit_id);position={"total_assets":bs["summary"]["total_assets"],"total_liabilities":bs["summary"]["total_liabilities"],"total_equity":bs["summary"]["total_equity"],"trial_balance_is_balanced":trial["summary"]["is_balanced"],"trial_balance_difference":trial["summary"]["difference"],"balance_sheet_is_balanced":bs["summary"]["is_balanced"],"balance_sheet_difference":bs["summary"]["difference"],"abnormal_balance_count":trial["summary"]["abnormal_balance_count"],"unclassified_coa_count":pl["summary"]["unclassified_account_count"]+bs["summary"]["unclassified_account_count"]}
        alerts=[]
        def alert(kind,severity,title,description,count=1,amount=None,route="/dashboard",entity_id=None):alerts.append({"alert_type":kind,"severity":severity,"title":title,"description":description,"count":count,"amount":amount,"target_route":route,"entity_id":entity_id})
        negative=[row for row in cash_position["accounts"] if row["current_balance"]<ZERO]
        if negative:alert("NEGATIVE_CASH_BALANCE","CRITICAL","Negative cash balance","One or more liquid accounts have a credit balance.",len(negative),sum((abs(row["current_balance"]) for row in negative),ZERO),"/cash-accounts")
        if forecast["forecast_after_due_30_days"]<ZERO:alert("LOW_CASH_FORECAST","CRITICAL","Negative 30-day cash forecast","Cash may be insufficient for payables due within 30 days.",1,abs(forecast["forecast_after_due_30_days"]),"/supplier-invoices")
        if ap["overdue_invoice_count"]:alert("OVERDUE_SUPPLIER_INVOICE","WARNING","Overdue supplier invoices","Supplier invoices are past due.",ap["overdue_invoice_count"],ap["overdue_ap"],"/supplier-invoices?overdue=true")
        overdue_po=self.db.query(PurchaseOrder).filter(PurchaseOrder.status.in_(["APPROVED","PARTIALLY_RECEIVED"]),PurchaseOrder.expected_date.isnot(None),PurchaseOrder.expected_date<as_of_date)
        if location_id:overdue_po=overdue_po.filter(PurchaseOrder.location_id==location_id)
        if department_id:overdue_po=overdue_po.filter(PurchaseOrder.department_id==department_id)
        overdue_po_count=overdue_po.count()
        if overdue_po_count:alert("PO_OVERDUE_DELIVERY","WARNING","Purchase orders overdue for delivery","Approved purchase orders are past their expected delivery date.",overdue_po_count,None,"/purchase-orders")
        if purchasing["goods_receipts"]["waiting_receipt"]:alert("GOODS_WAITING_RECEIPT","INFO","Goods waiting for receipt","Approved or partially received purchase orders still require receiving.",purchasing["goods_receipts"]["waiting_receipt"],None,"/goods-receipts")
        if not position["trial_balance_is_balanced"]:alert("TRIAL_BALANCE_UNBALANCED","CRITICAL","Trial Balance is unbalanced",f"Difference {position['trial_balance_difference']}.",1,abs(position["trial_balance_difference"]),"/trial-balance")
        if not position["balance_sheet_is_balanced"]:alert("BALANCE_SHEET_UNBALANCED","CRITICAL","Balance Sheet is unbalanced",f"Difference {position['balance_sheet_difference']}.",1,abs(position["balance_sheet_difference"]),"/balance-sheet")
        if cash_summary["unclassified_count"]:alert("UNCLASSIFIED_CASH_FLOW","WARNING","Unclassified cash flow","Cash movements require classification.",cash_summary["unclassified_count"],None,"/cash-flow")
        if position["unclassified_coa_count"]:alert("UNCLASSIFIED_COA","WARNING","Unclassified statement accounts","Accounts require financial-statement classification.",position["unclassified_coa_count"],None,"/chart-of-accounts")
        if position["abnormal_balance_count"]:alert("ABNORMAL_ACCOUNT_BALANCE","WARNING","Abnormal account balances","Accounts have balances opposite their normal side.",position["abnormal_balance_count"],None,"/trial-balance")
        old_drafts=self.db.query(JournalEntry).filter(JournalEntry.status=="DRAFT",JournalEntry.created_at<datetime.now(timezone.utc)-timedelta(days=7)).count()
        if old_drafts:alert("JOURNAL_DRAFT_TOO_OLD","INFO","Old draft journals","Draft journals are older than seven days.",old_drafts,None,"/journal-entries?status=DRAFT")
        waiting=self.db.query(Payment).filter(Payment.status.in_(["APPROVED"]),Payment.journal_entry_id.is_(None)).count()
        if waiting:alert("PAYMENT_WAITING_POST","WARNING","Payments waiting to post","Approved payments do not have posted journals.",waiting,None,"/payments?status=APPROVED")
        invoice_without_journal=self.db.query(SupplierInvoice).filter(SupplierInvoice.status.in_(["VERIFIED","POSTED"]),~self.db.query(JournalEntry.id).filter(JournalEntry.reference_type=="SUPPLIER_INVOICE",JournalEntry.reference_id==SupplierInvoice.id).exists()).count()
        if invoice_without_journal:alert("INVOICE_WITHOUT_JOURNAL","WARNING","Invoices without journals","Verified or posted supplier invoices do not have journal entries.",invoice_without_journal,None,"/supplier-invoices")
        payment_without_journal=self.db.query(Payment).filter(Payment.status=="POSTED",Payment.journal_entry_id.is_(None)).count()
        if payment_without_journal:alert("PAYMENT_WITHOUT_JOURNAL","WARNING","Posted payments without journals","Posted supplier payments do not have journal entries.",payment_without_journal,None,"/payments")
        open_reconciliations=self.db.query(BankReconciliation).filter(BankReconciliation.status.in_(["DRAFT","IN_PROGRESS"]))
        reconciliation={"pending_count":open_reconciliations.count(),"oldest_unreconciled_statement_date":open_reconciliations.with_entities(func.min(BankReconciliation.statement_end_date)).scalar(),"total_difference":Decimal(open_reconciliations.with_entities(func.coalesce(func.sum(func.abs(BankReconciliation.difference)),0)).scalar())}
        if reconciliation["pending_count"]:alert("BANK_RECONCILIATION_PENDING","WARNING","Bank reconciliation pending","Bank statement reconciliations require attention.",reconciliation["pending_count"],reconciliation["total_difference"],"/bank-reconciliations")
        budget_report=BudgetVsActualService(self.db).report(fiscal_year=as_of_date.year,date_from=month_start,date_to=as_of_date,group_by="ACCOUNT",include_zero=True,page_size=1000,business_unit_id=business_unit_id);budget={"current_month_budget":budget_report["summary"]["budget_amount"],"actual_expense":budget_report["summary"]["actual_amount"],"available_budget":budget_report["summary"]["available_after_commitments"],"committed_spending":budget_report["summary"]["committed_po"],"over_budget_lines":budget_report["summary"]["over_budget_count"],"near_limit_lines":budget_report["summary"]["near_limit_count"]}
        if budget["over_budget_lines"]:alert("BUDGET_OVER_LIMIT","CRITICAL","Budget lines over limit","Actual expense exceeds approved budget.",budget["over_budget_lines"],None,"/budget-vs-actual")
        if budget["near_limit_lines"]:alert("BUDGET_NEAR_LIMIT","WARNING","Budget lines near limit","Budget utilization is at least 80 percent.",budget["near_limit_lines"],None,"/budget-vs-actual")
        actual_expense_accounts={x[0] for x in self.db.query(JournalLine.account_id).join(JournalEntry).join(ChartOfAccount,ChartOfAccount.id==JournalLine.account_id).filter(JournalEntry.status=="POSTED",JournalEntry.posting_date>=month_start,JournalEntry.posting_date<=as_of_date,ChartOfAccount.account_type=="EXPENSE").distinct()};budgeted_accounts={x[0] for x in self.db.query(BudgetLine.account_id).join(Budget).filter(Budget.status.in_(["APPROVED","LOCKED"]),Budget.date_from<=as_of_date,Budget.date_to>=month_start).distinct()};no_budget_count=len(actual_expense_accounts-budgeted_accounts)
        if no_budget_count:alert("NO_BUDGET_FOR_EXPENSE","WARNING","Expense accounts without budget","Posted expense activity exists without an approved budget line.",no_budget_count,None,"/budget-vs-actual")
        asset_q=self.db.query(FixedAsset)
        if business_unit_id:asset_q=asset_q.filter(FixedAsset.business_unit_id==business_unit_id)
        if location_id:asset_q=asset_q.filter(FixedAsset.location_id==location_id)
        if department_id:asset_q=asset_q.filter(FixedAsset.department_id==department_id)
        active_assets=asset_q.filter(FixedAsset.status.in_(["ACTIVE","FULLY_DEPRECIATED"]));fixed_assets={"total_fixed_asset_cost":Decimal(active_assets.with_entities(func.coalesce(func.sum(FixedAsset.acquisition_cost),0)).scalar()),"accumulated_depreciation":Decimal(active_assets.with_entities(func.coalesce(func.sum(FixedAsset.accumulated_depreciation),0)).scalar()),"current_month_depreciation":Decimal(self.db.query(func.coalesce(func.sum(FixedAssetDepreciationSchedule.depreciation_amount),0)).filter(FixedAssetDepreciationSchedule.period_year==as_of_date.year,FixedAssetDepreciationSchedule.period_month==as_of_date.month,FixedAssetDepreciationSchedule.status=="POSTED").scalar()),"pending_capitalization":asset_q.filter(FixedAsset.status=="DRAFT").count(),"pending_depreciation_runs":self.db.query(FixedAssetDepreciationRun).filter(FixedAssetDepreciationRun.status=="CALCULATED").count(),"near_end_of_useful_life":active_assets.filter(FixedAsset.net_book_value>FixedAsset.residual_value,FixedAsset.net_book_value-FixedAsset.residual_value<=FixedAsset.acquisition_cost/12).count()};fixed_assets["net_book_value"]=fixed_assets["total_fixed_asset_cost"]-fixed_assets["accumulated_depreciation"]
        if fixed_assets["pending_capitalization"]:alert("ASSET_PENDING_CAPITALIZATION","WARNING","Assets pending capitalization","Draft assets require Finance capitalization.",fixed_assets["pending_capitalization"],None,"/fixed-assets?status=DRAFT")
        if fixed_assets["pending_depreciation_runs"]:alert("DEPRECIATION_NOT_RUN","WARNING","Depreciation pending posting","Calculated depreciation runs require posting.",fixed_assets["pending_depreciation_runs"],None,"/depreciation-runs")
        budget["fixed_assets"]=fixed_assets
        severity={"CRITICAL":0,"WARNING":1,"INFO":2};alerts.sort(key=lambda row:severity[row["severity"]])
        interval=self.interval(date_from,date_to);timeline=self._timeline(date_from,date_to,interval,cash_svc,invoices,commitments,unconverted)
        return {"period":{"as_of_date":as_of_date,"date_from":date_from,"date_to":date_to,"interval":interval,"currency":currency or "IDR","generated_at":datetime.now(timezone.utc)},"cash_position":cash_position,"cash_flow":{"opening_cash":cash_summary["opening_cash_balance"],"total_inflow":cash_summary["total_cash_inflow"],"total_outflow":cash_summary["total_cash_outflow"],"net_cash_flow":cash_summary["net_cash_flow"],"closing_cash":cash_summary["closing_cash_balance"],"operating_net":cash_summary["operating_net"],"investing_net":cash_summary["investing_net"],"financing_net":cash_summary["financing_net"],"internal_transfer_total":cash_summary["internal_transfer_total"],"unclassified_count":cash_summary["unclassified_count"]},"accounts_payable":ap,"purchasing":purchasing,"forecast":forecast,"profitability":profit,"financial_position":position,"budget":budget,"bank_reconciliation":reconciliation,"approvals":approvals,"alerts":alerts,"timelines":timeline}

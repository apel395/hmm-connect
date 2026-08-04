#!/usr/bin/env python3
"""Generate deterministic, connected development data without resetting the database."""
from __future__ import annotations

import argparse
import random
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.account_payable import AccountPayable
from app.models.bank_reconciliation import BankReconciliation
from app.models.budget import Budget, BudgetLine
from app.models.business_unit import BusinessUnit
from app.models.chart_of_account import ChartOfAccount
from app.models.department import Department
from app.models.fixed_asset import FixedAsset, FixedAssetCategory, FixedAssetDepreciationRun
from app.models.general_ledger import GeneralLedger
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.location import Location
from app.models.payment import Payment, PaymentAllocation
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_requisition import PurchaseRequisition
from app.models.purchase_requisition_item import PurchaseRequisitionItem
from app.models.role import Role
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.fixed_asset import AssetInput, CapitalizeInput, CategoryInput
from app.services.document_number import next_document_number
from app.services.fixed_asset_service import FixedAssetService, DepreciationRunService
from app.services.finance_dashboard_service import FinanceDashboardService
from app.services.financial_statement_service import FinancialStatementService
from app.services.cash_flow_service import CashFlowService
from app.services.trial_balance_service import TrialBalanceService

ZERO = Decimal("0.00")
SCALES = {
    "small": {"items":100,"suppliers":30,"warehouses":5,"coa":100,"users":20,"chains":12},
    "medium":{"items":300,"suppliers":100,"warehouses":10,"coa":250,"users":50,"chains":48},
    "large":{"items":1000,"suppliers":300,"warehouses":20,"coa":500,"users":100,"chains":144},
}
INDONESIAN_NAMES=["Adi Santoso","Budi Hartono","Citra Lestari","Dewi Anggraini","Eko Prasetyo","Fitri Handayani","Gilang Saputra","Hana Permata","Indra Wijaya","Kartika Sari","Lukman Hakim","Maya Kusuma","Nanda Putri","Rizky Ramadhan","Siti Rahmawati","Taufik Hidayat"]
ITEMS=["Beras Premium","Minyak Goreng","Kopi Arabika","Teh Melati","Gula Pasir","Sabun Laundry","Linen Hotel","Lampu LED","Filter AC","Air Mineral","Daging Sapi","Ayam Segar","Sayuran","Kemasan Makanan","Tisu Hotel","Pembersih Lantai","Sarung Tangan","Peralatan Dapur"]
CITIES=["Pekanbaru","Jakarta","Bandung","Surabaya","Medan","Padang","Palembang","Batam","Bogor","Semarang"]

def month_shift(value:date,months:int)->date:
    index=value.year*12+value.month-1+months
    return date(index//12,index%12+1,min(value.day,28))

class Generator:
    def __init__(self,db,scale,seed):
        self.db=db;self.cfg=SCALES[scale];self.seed=seed;self.rng=random.Random(seed);self.prefix=f"DEMO-{seed}-";self.today=date.today();self.user=None
        self.baseline_balance_sheet_difference=FinancialStatementService(db).balance_sheet(as_of_date=self.today)["summary"]["difference"]

    def one(self,model,defaults=None,**where):
        value=self.db.query(model).filter_by(**where).first()
        if not value:value=model(**where,**(defaults or {}));self.db.add(value);self.db.flush()
        return value

    def cleanup_transactions(self):
        """Delete only rows owned by this deterministic demo namespace."""
        for row in self.db.query(Payment).filter(Payment.external_reference.like(f"{self.prefix}%")).all():self.db.delete(row)
        self.db.flush()
        invoice_ids=[x.id for x in self.db.query(SupplierInvoice).filter(SupplierInvoice.external_reference.like(f"{self.prefix}%"))]
        if invoice_ids:self.db.query(AccountPayable).filter(AccountPayable.invoice_number.like(f"{self.prefix}%")).delete(synchronize_session=False)
        for row in self.db.query(SupplierInvoice).filter(SupplierInvoice.external_reference.like(f"{self.prefix}%")).all():self.db.delete(row)
        for row in self.db.query(GoodsReceipt).filter(GoodsReceipt.external_reference.like(f"{self.prefix}%")).all():self.db.delete(row)
        for row in self.db.query(PurchaseOrder).filter(PurchaseOrder.external_reference.like(f"{self.prefix}%")).all():self.db.delete(row)
        for row in self.db.query(PurchaseRequisition).filter(PurchaseRequisition.external_reference.like(f"{self.prefix}%")).all():self.db.delete(row)
        self.db.query(GeneralLedger).filter(GeneralLedger.journal_source=="DEMO").delete(synchronize_session=False)
        for row in self.db.query(JournalEntry).filter(JournalEntry.description.like("Demo %")).all():self.db.delete(row)
        for row in self.db.query(BankReconciliation).filter(BankReconciliation.reconciliation_number.like(f"{self.prefix}%")).all():self.db.delete(row)
        for row in self.db.query(Budget).filter(Budget.description.like(f"{self.prefix}%")).all():self.db.delete(row)
        for run in self.db.query(FixedAssetDepreciationRun).filter(FixedAssetDepreciationRun.notes.like(f"{self.prefix}%")).all():
            if run.journal_entry_id:
                journal=self.db.get(JournalEntry,run.journal_entry_id)
                if journal:self.db.delete(journal)
            self.db.delete(run)
        for row in self.db.query(FixedAsset).filter(FixedAsset.external_reference.like(f"{self.prefix}%")).all():self.db.delete(row)
        self.db.flush()

    def organization(self):
        hotel=self.one(BusinessUnit,{"name":"Hotel","description":"Hotel operations","is_active":True},code="HOTEL");catering=self.one(BusinessUnit,{"name":"Catering","description":"Catering operations","is_active":True},code="CATERING")
        locations=[];departments=[]
        for bu,code,name in ((hotel,"DEMO-HOTEL-PKU","Hotel Pekanbaru"),(catering,"DEMO-CAT-KITCHEN","Main Catering Kitchen")):
            locations.append(self.one(Location,{"name":name,"location_type":"OPERATIONS","is_active":True,"business_unit_id":bu.id},code=code))
        for bu,code,name in ((hotel,"DEMO-HOUSEKEEPING","Housekeeping"),(hotel,"DEMO-ENGINEERING","Engineering"),(catering,"DEMO-PRODUCTION","Kitchen Production"),(catering,"DEMO-DELIVERY","Delivery Operations")):
            departments.append(self.one(Department,{"name":name,"is_active":True,"business_unit_id":bu.id},code=code))
        finance=self.one(Department,{"name":"Demo Shared Finance","is_active":True,"business_unit_id":None},code="DEMO-FINANCE");departments.append(finance)
        role=self.one(Role,{"description":"Finance development access"},name="FINANCE")
        admin=self.db.query(User).filter(User.roles.any(Role.name=="ADMIN")).first() or self.db.query(User).first()
        password=admin.password_hash if admin else hash_password("Demo123!")
        for i in range(self.cfg["users"]):
            username=f"demo{self.seed}_{i+1:03d}";bu=hotel if i%2==0 else catering;loc=locations[i%2];dep=departments[i%4]
            user=self.one(User,{"email":f"{username}@hmm.demo","full_name":INDONESIAN_NAMES[i%len(INDONESIAN_NAMES)]+f" {i+1}","password_hash":password,"is_active":True,"department_id":dep.id,"location_id":loc.id,"default_business_unit_id":bu.id,"default_location_id":loc.id,"default_department_id":dep.id},username=username)
            if role not in user.roles:user.roles.append(role)
        self.user=admin or self.db.query(User).filter(User.username.like(f"demo{self.seed}_%")).first()
        return hotel,catering,locations,departments

    def coa(self):
        required=[("DEMO1100","Demo Operating Cash","ASSET","DEBIT","CASH"),("DEMO1200","Demo Inventory","ASSET","DEBIT","OTHER"),("DEMO1300","Demo Fixed Assets","ASSET","DEBIT","OTHER"),("DEMO1390","Demo Accumulated Depreciation","ASSET","CREDIT","OTHER"),("DEMO2100","Demo Accounts Payable","LIABILITY","CREDIT","OTHER"),("DEMO3100","Demo Retained Earnings","EQUITY","CREDIT","OTHER"),("DEMO4100","Demo Hotel Revenue","REVENUE","CREDIT","OTHER"),("DEMO5100","Demo Operating Expense","EXPENSE","DEBIT","OTHER"),("DEMO5200","Demo Depreciation Expense","EXPENSE","DEBIT","OTHER"),("DEMO5900","Demo Disposal Loss","EXPENSE","DEBIT","OTHER"),("DEMO4900","Demo Disposal Gain","REVENUE","CREDIT","OTHER")]
        accounts={}
        for code,name,kind,normal,subtype in required:
            accounts[code]=self.one(ChartOfAccount,{"account_name":name,"account_type":kind,"normal_balance":normal,"account_subtype":subtype,"is_posting":True,"is_system":False,"is_active":True},account_number=code)
        current=self.db.query(ChartOfAccount).count()
        for i in range(max(0,self.cfg["coa"]-current)):
            kind=("ASSET","LIABILITY","REVENUE","EXPENSE")[i%4];normal="DEBIT" if kind in ("ASSET","EXPENSE") else "CREDIT";code=f"D{self.seed%100:02d}{i+6000:04d}"
            self.one(ChartOfAccount,{"account_name":f"Demo {kind.title()} Account {i+1}","account_type":kind,"normal_balance":normal,"account_subtype":"OTHER","is_posting":True,"is_system":False,"is_active":True},account_number=code)
        return accounts

    def masters(self,accounts):
        suppliers=[]
        for i in range(self.cfg["suppliers"]):
            code=f"{self.prefix}SUP-{i+1:04d}";suppliers.append(self.one(Supplier,{"name":f"PT {ITEMS[i%len(ITEMS)]} Nusantara {CITIES[i%len(CITIES)]}","address":f"Jl. Sudirman No. {i+1}, {CITIES[i%len(CITIES)]}","bank_name":("BCA","Mandiri","BNI")[i%3],"bank_account_number":f"{seed_number(self.seed,i,12)}","bank_account_name":f"Supplier Demo {i+1}","is_active":True},code=code))
        products=[]
        for i in range(self.cfg["items"]):
            code=f"{self.prefix}ITM-{i+1:05d}";price=Decimal(10000+(i%25)*2500);products.append(self.one(Product,{"name":f"{ITEMS[i%len(ITEMS)]} {i+1}","group_code":"DEMO","group_name":"Demo Operations","subgroup_code":f"D{i%10:02d}","subgroup_name":"Operational Supply","uom":"PCS","usage_uom":"PCS","conversion":1,"cost_price":price,"selling_price":price*Decimal("1.25"),"minimum_stock":10,"reorder_level":20,"maximum_stock":200,"lead_time_days":3+(i%10),"inventory_account_id":accounts["DEMO1200"].id,"purchase_account_id":accounts["DEMO5100"].id,"is_active":True},code=code))
        for i in range(self.cfg["warehouses"]):self.one(Warehouse,{"name":f"Demo Warehouse {CITIES[i%len(CITIES)]} {i+1}","address":f"Kawasan Operasional {CITIES[i%len(CITIES)]}","is_active":True},code=f"{self.prefix}WH-{i+1:03d}")
        return suppliers,products

    def journal(self,posting_date,reference_type,reference_id,reference_number,description,lines,bu,loc,dep):
        existing=self.db.query(JournalEntry).filter_by(reference_type=reference_type,reference_id=reference_id).first()
        if existing:return existing
        entry=JournalEntry(journal_number=next_document_number(self.db,"JV",digits=8),posting_date=posting_date,status="POSTED",document_type=reference_type,document_number=reference_number,reference_type=reference_type,reference_id=reference_id,description=description,created_by_id=self.user.id,posted_by_id=self.user.id,posted_at=datetime.combine(posting_date,datetime.min.time(),tzinfo=timezone.utc),business_unit_id=bu.id,location_id=loc.id,department_id=dep.id,fiscal_year=posting_date.year,fiscal_period=posting_date.month)
        self.db.add(entry);self.db.flush()
        for number,(account,debit,credit) in enumerate(lines,1):
            self.db.add(JournalLine(journal_entry_id=entry.id,line_number=number,account_id=account.id,debit=debit,credit=credit,description=description,business_unit_id=bu.id,location_id=loc.id,department_id=dep.id))
            self.db.add(GeneralLedger(journal_number=f"{entry.journal_number}-{number}",posting_date=posting_date,fiscal_year=posting_date.year,fiscal_period=posting_date.month,account_id=account.id,debit=debit,credit=credit,journal_source="DEMO",document_type=reference_type,document_number=reference_number,reference_type=reference_type,reference_id=reference_id,reference_number=entry.journal_number,description=description,created_by_id=self.user.id))
        return entry

    def purchasing(self,hotel,catering,locations,departments,suppliers,products,accounts):
        warehouses=self.db.query(Warehouse).filter(Warehouse.code.like(f"{self.prefix}WH-%")).all();chains=self.cfg["chains"]
        for i in range(chains):
            ref=f"{self.prefix}FLOW-{i+1:04d}";existing=self.db.query(PurchaseRequisition).filter_by(external_reference=ref).first()
            if existing:continue
            doc_date=month_shift(self.today.replace(day=10),-11+(i%12));bu=hotel if i%2==0 else catering;loc=locations[i%2];dep=departments[i%4];supplier=suppliers[i%len(suppliers)];product=products[(i*7)%len(products)];qty=Decimal(2+i%8);price=Decimal(product.cost_price);amount=(qty*price).quantize(Decimal("0.01"));stage=i%6
            pr=PurchaseRequisition(pr_number=next_document_number(self.db,"PR"),status="APPROVED" if stage<5 else "SUBMITTED",request_date=doc_date,total_amount=amount,notes="Deterministic demo purchasing activity",source_type="LIVE",external_reference=ref,business_unit_id=bu.id,location_id=loc.id,department_id=dep.id,requested_by_id=self.user.id);pr_item=PurchaseRequisitionItem(product_id=product.id,quantity=qty,estimated_price=price,total_price=amount);pr.items=[pr_item];self.db.add(pr);self.db.flush()
            if stage==5:continue
            po=PurchaseOrder(po_number=next_document_number(self.db,"PO"),supplier_id=supplier.id,purchase_requisition_id=pr.id,status="APPROVED",order_date=doc_date+timedelta(days=2),expected_date=doc_date+timedelta(days=7),total_amount=amount,notes="Demo linked purchase order",source_type="LIVE",external_reference=ref,business_unit_id=bu.id,location_id=loc.id,department_id=dep.id);po_item=PurchaseOrderItem(purchase_requisition_item_id=pr_item.id,product_id=product.id,description=product.name,uom=product.uom,quantity=qty,received_quantity=ZERO,unit_price=price,total_price=amount);po.items=[po_item];self.db.add(po);self.db.flush()
            if stage==4:continue
            received=qty if stage!=3 else (qty/2).quantize(Decimal("0.01"));po_item.received_quantity=received;po.status="RECEIVED" if received==qty else "PARTIALLY_RECEIVED"
            receipt=GoodsReceipt(receipt_number=next_document_number(self.db,"GR"),status="POSTED",purchase_order_id=po.id,received_by_id=self.user.id,received_at=datetime.combine(doc_date+timedelta(days=8),datetime.min.time(),tzinfo=timezone.utc),destination_type="WAREHOUSE",warehouse_id=warehouses[i%len(warehouses)].id,business_unit_id=bu.id,location_id=loc.id,department_id=dep.id,source_type="LIVE",external_reference=ref,delivery_note_number=f"SJ-DEMO-{i+1:04d}");receipt.items=[GoodsReceiptItem(purchase_order_item_id=po_item.id,product_id=product.id,quantity=received,unit_cost=price)];self.db.add(receipt);self.db.flush()
            invoice_amount=(received*price).quantize(Decimal("0.01"));invoice=SupplierInvoice(internal_invoice_number=next_document_number(self.db,"INV"),supplier_invoice_number=f"{self.prefix}SINV-{i+1:04d}",supplier_id=supplier.id,invoice_date=doc_date+timedelta(days=10),received_date=doc_date+timedelta(days=10),due_date=doc_date+timedelta(days=40),purchase_order_id=po.id,goods_receipt_id=receipt.id,business_unit_id=bu.id,location_id=loc.id,department_id=dep.id,currency="IDR",subtotal=invoice_amount,discount_amount=ZERO,tax_amount=ZERO,withholding_tax_amount=ZERO,total_amount=invoice_amount,paid_amount=ZERO,balance_amount=invoice_amount,payment_status="UNPAID",status="POSTED",notes="Demo supplier invoice",source_type="LIVE",external_reference=ref,created_by_id=self.user.id,posted_at=datetime.combine(doc_date+timedelta(days=10),datetime.min.time(),tzinfo=timezone.utc));invoice.lines=[SupplierInvoiceLine(product_id=product.id,purchase_order_item_id=po_item.id,goods_receipt_item_id=receipt.items[0].id,description=product.name,quantity=received,uom=product.uom,unit_price=price,line_amount=invoice_amount,account_id=accounts["DEMO5100"].id,department_id=dep.id)];self.db.add(invoice);self.db.flush()
            payable=AccountPayable(supplier_id=supplier.id,purchase_order_id=po.id,invoice_number=invoice.supplier_invoice_number,invoice_date=invoice.invoice_date,due_date=invoice.due_date,amount=invoice_amount,status="OPEN",paid_amount=ZERO,outstanding_amount=invoice_amount,payment_status="UNPAID");self.db.add(payable);self.db.flush()
            self.journal(invoice.invoice_date,"SUPPLIER_INVOICE",invoice.id,invoice.internal_invoice_number,"Demo operating purchase",[(accounts["DEMO5100"],invoice_amount,ZERO),(accounts["DEMO2100"],ZERO,invoice_amount)],bu,loc,dep)
            if stage in (0,1):
                paid=invoice_amount if stage==0 else (invoice_amount/2).quantize(Decimal("0.01"));payment=Payment(payment_number=next_document_number(self.db,"PAY"),account_payable_id=payable.id,payment_date=doc_date+timedelta(days=25),amount=paid,payment_method="BANK_TRANSFER",reference_number=f"TRF-DEMO-{i+1:04d}",status="POSTED",created_by_id=self.user.id,supplier_id=supplier.id,payment_account_id=accounts["DEMO1100"].id,currency="IDR",source_type="LIVE",external_reference=ref,approved_by_id=self.user.id,posted_by_id=self.user.id,business_unit_id=bu.id,location_id=loc.id,department_id=dep.id,approved_at=datetime.now(timezone.utc),posted_at=datetime.now(timezone.utc));self.db.add(payment);self.db.flush();payment.allocations=[PaymentAllocation(supplier_invoice_id=invoice.id,allocated_amount=paid)];invoice.paid_amount=paid;invoice.balance_amount=invoice_amount-paid;invoice.payment_status="PAID" if invoice.balance_amount==ZERO else "PARTIALLY_PAID";payable.paid_amount=paid;payable.outstanding_amount=invoice.balance_amount;payable.payment_status=invoice.payment_status;payable.status="PAID" if invoice.balance_amount==ZERO else "OPEN";entry=self.journal(payment.payment_date,"SUPPLIER_PAYMENT",payment.id,payment.payment_number,"Demo supplier payment",[(accounts["DEMO2100"],paid,ZERO),(accounts["DEMO1100"],ZERO,paid)],bu,loc,dep);payment.journal_entry_id=entry.id

    def banking(self,accounts,hotel,locations,departments):
        for i,bank in enumerate(("BCA","MANDIRI","BNI")):
            code=f"DEMO11{i+1}0";account=self.one(ChartOfAccount,{"account_name":f"Bank {bank}","account_type":"ASSET","normal_balance":"DEBIT","account_subtype":"BANK","is_posting":True,"is_system":False,"is_active":True},account_number=code)
            ref=f"{self.prefix}REC-{bank}";self.one(BankReconciliation,{"account_id":account.id,"business_unit_id":hotel.id,"location_id":locations[0].id,"department_id":departments[-1].id,"statement_start_date":month_shift(self.today,-1).replace(day=1),"statement_end_date":self.today,"statement_opening_balance":Decimal("50000000"),"statement_closing_balance":Decimal("47500000")+i*Decimal("1000000"),"system_opening_balance":Decimal("50000000"),"system_closing_balance":Decimal("47500000"),"difference":ZERO if i==0 else Decimal("250000"),"status":"COMPLETED" if i==0 else "IN_PROGRESS","notes":"Deterministic demo bank reconciliation","created_by_id":self.user.id,"completed_by_id":self.user.id if i==0 else None,"completed_at":datetime.now(timezone.utc) if i==0 else None},reconciliation_number=ref)

    def close_prior_year_results(self,accounts,hotel,locations,departments):
        """Close all pre-current-year P&L balances once so the Balance Sheet has opening equity."""
        close_date=date(self.today.year-1,12,31);reference_id=self.today.year
        if self.db.query(JournalEntry).filter_by(reference_type="DEMO_YEAR_END_CLOSE",reference_id=reference_id).first():return
        rows=self.db.query(ChartOfAccount,func.coalesce(func.sum(JournalLine.debit),0),func.coalesce(func.sum(JournalLine.credit),0)).join(JournalLine,JournalLine.account_id==ChartOfAccount.id).join(JournalEntry,JournalEntry.id==JournalLine.journal_entry_id).filter(JournalEntry.status=="POSTED",JournalEntry.posting_date<=close_date,ChartOfAccount.account_type.in_(["REVENUE","EXPENSE"])).group_by(ChartOfAccount.id).all()
        lines=[];retained_debit=ZERO;retained_credit=ZERO
        for account,debit,credit in rows:
            balance=Decimal(credit)-Decimal(debit) if account.account_type=="REVENUE" else Decimal(debit)-Decimal(credit)
            if balance==ZERO:continue
            if account.account_type=="REVENUE":lines.append((account,balance,ZERO));retained_credit+=balance
            else:lines.append((account,ZERO,balance));retained_debit+=balance
        net=retained_credit-retained_debit
        if net>ZERO:lines.append((accounts["DEMO3100"],ZERO,net))
        elif net<ZERO:lines.append((accounts["DEMO3100"],-net,ZERO))
        if lines:self.journal(close_date,"DEMO_YEAR_END_CLOSE",reference_id,f"CLOSE-{close_date.year}","Demo year-end result closing",lines,hotel,locations[0],departments[-1])

    def budgets_assets(self,hotel,catering,locations,departments,accounts):
        for i,bu in enumerate((hotel,catering)):
            ref=f"{self.prefix}BUD-{bu.code}";budget=self.db.query(Budget).filter_by(description=ref).first()
            if not budget:
                start=self.today.replace(month=1,day=1);end=self.today.replace(month=12,day=31);budget=Budget(budget_number=next_document_number(self.db,"BUD"),name=f"Demo {bu.name} Annual Budget",fiscal_year=self.today.year,date_from=start,date_to=end,status="APPROVED",currency="IDR",description=ref,created_by_id=self.user.id,approved_by_id=self.user.id,approved_at=datetime.now(timezone.utc));budget.lines=[BudgetLine(account_id=accounts["DEMO5100"].id,business_unit_id=bu.id,location_id=locations[i].id,department_id=departments[i*2].id,month=m,budget_amount=Decimal("25000000") if m!=self.today.month else Decimal("1000000"),notes="Demo monthly operating budget") for m in range(1,13)];self.db.add(budget)
        svc=FixedAssetService(self.db);category=self.db.query(FixedAssetCategory).filter_by(code=f"{self.prefix}EQUIP").first()
        if not category:category=svc.create_category(CategoryInput(code=f"{self.prefix}EQUIP",name="Demo Hotel and Catering Equipment",default_useful_life_months=36,asset_account_id=accounts["DEMO1300"].id,accumulated_depreciation_account_id=accounts["DEMO1390"].id,depreciation_expense_account_id=accounts["DEMO5200"].id,disposal_gain_account_id=accounts["DEMO4900"].id,disposal_loss_account_id=accounts["DEMO5900"].id))
        names=["Hotel Building","Air Conditioner","Laundry Machine","Commercial Oven","Delivery Vehicle","Hotel Furniture","Computers","Kitchen Equipment"]
        for i,name in enumerate(names):
            ref=f"{self.prefix}ASSET-{i+1:02d}";asset=self.db.query(FixedAsset).filter_by(external_reference=ref).first()
            if asset:continue
            bu=hotel if i<4 else catering;loc=locations[0 if i<4 else 1];dep=departments[0 if i<4 else 2];cost=Decimal(50000000+(i*7500000));asset=svc.create_asset(AssetInput(asset_name=name,asset_category_id=category.id,acquisition_date=month_shift(self.today,-11+i),acquisition_cost=cost,residual_value=ZERO,useful_life_months=1 if i==1 else 36,business_unit_id=bu.id,location_id=loc.id,department_id=dep.id,asset_account_id=accounts["DEMO1300"].id,accumulated_depreciation_account_id=accounts["DEMO1390"].id,depreciation_expense_account_id=accounts["DEMO5200"].id,disposal_gain_account_id=accounts["DEMO4900"].id,disposal_loss_account_id=accounts["DEMO5900"].id,source_type="DEMO",external_reference=ref),self.user)
            if i!=7:svc.capitalize(asset,CapitalizeInput(capitalization_date=asset.acquisition_date,depreciation_start_date=asset.acquisition_date,create_journal=False),self.user)
        run=self.db.query(FixedAssetDepreciationRun).filter_by(period_year=self.today.year,period_month=self.today.month,business_unit_id=catering.id,location_id=locations[1].id).first()
        if not run:
            run=FixedAssetDepreciationRun(run_number=next_document_number(self.db,"FADR"),period_year=self.today.year,period_month=self.today.month,business_unit_id=catering.id,location_id=locations[1].id,status="DRAFT",notes=f"{self.prefix}monthly depreciation",created_by_id=self.user.id);self.db.add(run);self.db.flush()
        run_service=DepreciationRunService(self.db)
        if run.status=="DRAFT":run_service.calculate(run)
        if run.status=="CALCULATED" and run.asset_count:run_service.post(run,self.user)

    def validate(self):
        debit,credit=self.db.query(func.coalesce(func.sum(JournalLine.debit),0),func.coalesce(func.sum(JournalLine.credit),0)).join(JournalEntry).filter(JournalEntry.status=="POSTED",JournalEntry.reference_type.in_(["SUPPLIER_INVOICE","SUPPLIER_PAYMENT"]),JournalEntry.document_number.like(f"%") ).one()
        if Decimal(debit)!=Decimal(credit):raise RuntimeError(f"Demo journals unbalanced: {debit} != {credit}")
        trial=TrialBalanceService(self.db).report(date_from=month_shift(self.today,-12),date_to=self.today,include_zero_balance=True,paginate=False,page_size=1000)
        if not trial["summary"]["is_balanced"]:raise RuntimeError("Trial Balance is not balanced")
        balance_sheet=FinancialStatementService(self.db).balance_sheet(as_of_date=self.today)
        if not balance_sheet["summary"]["is_balanced"]:raise RuntimeError(f"Balance Sheet is not balanced: {balance_sheet['summary']['difference']}")
        cash_flow=CashFlowService(self.db).summary(month_shift(self.today,-12),self.today)
        if "net_cash_flow" not in cash_flow:raise RuntimeError("Cash Flow validation failed")
        dashboard=FinanceDashboardService(self.db,self.user).build(self.today,month_shift(self.today,-1),self.today)
        if "cash_position" not in dashboard or "fixed_assets" not in dashboard["budget"]:raise RuntimeError("Dashboard validation failed")
        if not self.db.query(Budget).filter(Budget.description.like(f"{self.prefix}%")).count():raise RuntimeError("Budget generation failed")
        if not self.db.query(FixedAsset).filter(FixedAsset.external_reference.like(f"{self.prefix}%")).count():raise RuntimeError("Asset generation failed")
        if not self.db.query(BankReconciliation).filter(BankReconciliation.reconciliation_number.like(f"{self.prefix}%")).count():raise RuntimeError("Bank reconciliation generation failed")
        orphan_po=self.db.query(PurchaseOrder).filter(PurchaseOrder.external_reference.like(f"{self.prefix}%"),PurchaseOrder.purchase_requisition_id.is_(None)).count();orphan_receipt=self.db.query(GoodsReceipt).filter(GoodsReceipt.external_reference.like(f"{self.prefix}%"),GoodsReceipt.purchase_order_id.is_(None)).count();orphan_invoice=self.db.query(SupplierInvoice).filter(SupplierInvoice.external_reference.like(f"{self.prefix}%"),SupplierInvoice.purchase_order_id.is_(None)).count()
        if orphan_po or orphan_receipt or orphan_invoice:raise RuntimeError("Orphan demo documents detected")

    def counts(self):
        return {"Business Units":self.db.query(BusinessUnit).count(),"Locations":self.db.query(Location).count(),"Departments":self.db.query(Department).count(),"Items":self.db.query(Product).filter(Product.code.like(f"{self.prefix}%")).count(),"Suppliers":self.db.query(Supplier).filter(Supplier.code.like(f"{self.prefix}%")).count(),"Warehouses":self.db.query(Warehouse).filter(Warehouse.code.like(f"{self.prefix}%")).count(),"Users":self.db.query(User).filter(User.username.like(f"demo{self.seed}_%")).count(),"PR":self.db.query(PurchaseRequisition).filter(PurchaseRequisition.external_reference.like(f"{self.prefix}%")).count(),"PO":self.db.query(PurchaseOrder).filter(PurchaseOrder.external_reference.like(f"{self.prefix}%")).count(),"Goods Receipt":self.db.query(GoodsReceipt).filter(GoodsReceipt.external_reference.like(f"{self.prefix}%")).count(),"Purchase Invoice":self.db.query(SupplierInvoice).filter(SupplierInvoice.external_reference.like(f"{self.prefix}%")).count(),"Purchase Payment":self.db.query(Payment).filter(Payment.external_reference.like(f"{self.prefix}%")).count(),"Journal Entries":self.db.query(JournalEntry).filter(JournalEntry.description.like("Demo %")).count(),"General Ledger rows":self.db.query(GeneralLedger).filter(GeneralLedger.journal_source=="DEMO").count(),"Bank Reconciliations":self.db.query(BankReconciliation).filter(BankReconciliation.reconciliation_number.like(f"{self.prefix}%")).count(),"Budgets":self.db.query(Budget).filter(Budget.description.like(f"{self.prefix}%")).count(),"Assets":self.db.query(FixedAsset).filter(FixedAsset.external_reference.like(f"{self.prefix}%")).count(),"Depreciation Runs":self.db.query(FixedAssetDepreciationRun).count()}

def seed_number(seed,index,digits):return str((seed*1000003+(index+1)*7919)%10**digits).zfill(digits)

def main():
    parser=argparse.ArgumentParser();size=parser.add_mutually_exclusive_group();size.add_argument("--small",action="store_true");size.add_argument("--medium",action="store_true");size.add_argument("--large",action="store_true");parser.add_argument("--seed",type=int,default=123);args=parser.parse_args();scale="large" if args.large else "medium" if args.medium else "small"
    answer=input("Delete existing development data? Type YES or NO: ").strip().upper()
    if answer not in {"YES","NO"}:raise SystemExit("Answer must be YES or NO")
    db=SessionLocal()
    try:
        generator=Generator(db,scale,args.seed)
        if answer=="YES":generator.cleanup_transactions()
        hotel,catering,locations,departments=generator.organization();accounts=generator.coa();suppliers,products=generator.masters(accounts);generator.purchasing(hotel,catering,locations,departments,suppliers,products,accounts);generator.close_prior_year_results(accounts,hotel,locations,departments);generator.banking(accounts,hotel,locations,departments);generator.budgets_assets(hotel,catering,locations,departments,accounts);db.commit();generator.validate();counts=generator.counts();print(f"Demo data generated: scale={scale}, seed={args.seed}");[print(f"{key}: {value}") for key,value in counts.items()];print("Dashboard ready: YES\nValidation passed: YES")
    except Exception:db.rollback();raise
    finally:db.close()

if __name__=="__main__":main()

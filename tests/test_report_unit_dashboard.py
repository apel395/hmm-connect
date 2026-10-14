from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.models.purchase_requisition import PurchaseRequisition
from app.models.opening_balance import OpeningBalance
from app.api.v1.financial_reports import executive_overview
from app.api.v1.ap_reporting import detail
from app.api.v1.purchasing_reports import purchasing_summary as summary
from app.services.purchasing_exceptions import unfinished_documents
from app.services.financial_reconciliation_service import FinancialReconciliationService
from app.services.cash_flow_service import CashFlowService
from test_organization_and_asset_delivery import db, ADMIN, scoped_user


def journal(db, number, amount, location, department):
    row=JournalEntry(journal_number=number,posting_date=date(2026,10,2),status='POSTED',reference_type='MANUAL',reference_id=0,location_id=location,department_id=department)
    row.lines=[JournalLine(account_id=4,debit=0,credit=amount,location_id=location,department_id=department),JournalLine(account_id=5,debit=amount,credit=0,location_id=location,department_id=department)]
    db.add(row);db.commit()


def test_owner_dashboard_trend_and_scope_match_headlines(db):
    db.add_all([ChartOfAccount(id=4,account_number='400-100-100',account_name='Revenue',account_type='REVENUE',normal_balance='CREDIT',is_posting=True),ChartOfAccount(id=5,account_number='100-100-100',account_name='Cash',account_type='ASSET',account_subtype='CASH',normal_balance='DEBIT',is_posting=True)])
    db.commit();journal(db,'HOTEL-LEGACY',100,1,1);journal(db,'CATERING-LEGACY',999,2,3)
    result=executive_overview(as_of_date=date(2026,10,14),business_unit_id=1,db=db,user=ADMIN)
    visuals=result['dashboard']
    assert visuals['monthly'][-1]['revenue']=='100.00'
    assert sum(Decimal(row['revenue']) for row in visuals['monthly'])==100
    assert visuals['cash_balance']=='100.00'
    assert [row['name'] for row in visuals['performance']]==['House Keeping']
    assert visuals['performance'][0]['YTD']['net_profit']=='100.00'
    assert 'account_id' not in str(visuals) and 'Catering' not in str(visuals)
    assert result['profit_loss']['presentation_rows'][0]['periods']['YTD']['current']=='100.00'


def test_ap_purchasing_and_archive_follow_legacy_location_unit(db):
    db.add(Supplier(id=1,code='SUP',name='Supplier'))
    for ident,location in [(1,1),(2,2)]:
        db.add(SupplierInvoice(id=ident,internal_invoice_number=f'INV-{ident}',supplier_invoice_number=str(ident),supplier_id=1,invoice_date=date(2026,10,2),status='POSTED',subtotal=ident*100,total_amount=ident*100,location_id=location))
        db.add(PurchaseRequisition(pr_number=f'PR-{ident}',location_id=location,request_date=date(2026,10,2),status='DRAFT'))
    db.commit()
    report=detail(page=1,page_size=20,status=None,supplier_id=None,business_unit_id=1,location_id=None,department_id=None,search=None,db=db,current_user=ADMIN)
    assert [row['invoice_number'] for row in report['items']]==['INV-1']
    assert summary(business_unit_id=1,db=db,user=ADMIN)['requisitions']['total']==1
    assert [row['number'] for row in unfinished_documents(db,ADMIN,business_unit_id=1)]==['PR-1']
    with pytest.raises(HTTPException):
        detail(page=1,page_size=20,status=None,supplier_id=None,business_unit_id=2,location_id=None,department_id=None,search=None,db=db,current_user=scoped_user())


def test_reconciliation_and_mixed_cash_journal_are_unit_scoped(db):
    db.add(ChartOfAccount(id=5,account_number='100-100-100',account_name='Cash',account_type='ASSET',account_subtype='CASH',normal_balance='DEBIT',is_posting=True));db.commit()
    row=JournalEntry(journal_number='MIXED',posting_date=date(2026,10,2),status='POSTED',reference_type='MANUAL',reference_id=0)
    row.lines=[JournalLine(account_id=5,debit=10,credit=0,location_id=1),JournalLine(account_id=5,debit=999,credit=0,location_id=2)]
    db.add(row);db.add(OpeningBalance(fiscal_year=2026,account_id=5,location_id=1,balance_type='DEBIT',amount=100));db.add(OpeningBalance(fiscal_year=2026,account_id=5,location_id=2,balance_type='DEBIT',amount=900));db.commit()
    svc=FinancialReconciliationService(db,business_unit_id=1)
    assert svc._gl_balance([5],as_of=date(2026,10,14))==110
    assert svc.accounts_receivable()['source_balance'] is None
    assert [r['delta'] for r in CashFlowService(db).movements(business_unit_id=1)]==[Decimal(10)]
    svc.report(date_to=date(2026,10,14))

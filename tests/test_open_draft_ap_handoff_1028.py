"""Actual receipt → verified invoice → payment with open draft accounting."""
from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.api.v1 import payments, supplier_invoices
from app.models.bank_account import BankAccount
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.general_ledger import GeneralLedger
from app.models.supplier_invoice import SupplierInvoice
from app.models.payment import Payment
from app.schemas.payment import PaymentCreate
from app.services.goods_receipt_service import GoodsReceiptService
from app.services.supplier_invoice_service import SupplierInvoiceService
from app.services.document_accounting import invoice_is_accounted
from app.services.financial_reconciliation_service import FinancialReconciliationService
from app.services.ap_reporting_service import APReportingService
from app.services.accounting_unpost import _assert_invoice_has_no_posted_dependents
from test_receiving_line_destinations import setup_receiving, create
from test_stock_opname_functional import stock_db


def test_receipt_draft_journal_verification_payment_and_finalization_once(stock_db, monkeypatch):
    data=setup_receiving(stock_db)
    db,wh,user,products,balances,expense,supplier=data
    payable=ChartOfAccount(account_number='200-100-1',account_name='AP',account_type='LIABILITY',normal_balance='CREDIT',is_posting=True,is_active=True)
    cash=ChartOfAccount(account_number='100-110-100',account_name='Bank',account_type='ASSET',account_subtype='BANK',normal_balance='DEBIT',is_posting=True,is_active=True)
    db.add_all([payable,cash]);db.flush();supplier.payable_account_id=payable.id
    bank=BankAccount(bank_name='Test',account_number='DRAFT-AP',account_name='Operating',coa_account_id=cash.id,business_unit_id=user.default_business_unit_id,currency='IDR',is_active=True,is_payment_account=True)
    db.add(bank);db.commit()
    receipt=create(data)
    GoodsReceiptService.post(db,receipt_id=receipt.id,user=user)
    gr_journal=db.query(JournalEntry).filter_by(reference_type='GOODS_RECEIPT',reference_id=receipt.id).one()
    assert gr_journal.status=='DRAFT'
    invoice=db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    invoice.supplier_invoice_number='VENDOR-REAL-1028';db.commit()
    service=SupplierInvoiceService(db)
    service.verify(invoice,user,commit=False)
    je=service.generate_journal(invoice,user,commit=False);db.commit()
    assert je.status=='DRAFT' and invoice.status=='VERIFIED'
    assert invoice_is_accounted(db,invoice)
    assert db.query(GeneralLedger).count()==0
    monkeypatch.setattr(payments,'result',lambda db,p,user:{'id':p.id,'status':p.status})
    queue=payments.ready_to_pay(page=1,page_size=50,search=None,currency='IDR',db=db,user=user)
    assert queue['items'][0]['id']==invoice.id
    payload=PaymentCreate(supplier_id=supplier.id,payment_date=date.today(),total_amount=40,business_unit_id=user.default_business_unit_id,location_id=user.location_id,department_id=user.default_department_id,
        allocations=[{'supplier_invoice_id':invoice.id,'allocated_amount':40}],funding_lines=[{'bank_account_id':bank.id,'amount':40}])
    payment_id=payments.create(payload,db=db,user=user)['id']
    payments.approve(payment_id,db=db,user=user)
    payments.generate(payment_id,db=db,user=user)
    payment=db.get(Payment,payment_id)
    payment_je=db.get(JournalEntry,payment.journal_entry_id)
    assert payment_je.status=='DRAFT' and invoice.paid_amount==0
    # Accounting recognizes approval with a complete journal; settlement caches stay untouched.
    assert APReportingService(db)._rows()[0]['outstanding_amount']==0
    with pytest.raises(HTTPException,match='accounted payment'):
        _assert_invoice_has_no_posted_dependents(db,invoice)
    before=FinancialReconciliationService(db)._gl_balance([payable.id],None,None)
    assert before==0
    payments.post(payment_id,db=db,user=user)
    assert invoice.paid_amount==40 and invoice.balance_amount==0
    assert FinancialReconciliationService(db)._gl_balance([payable.id],None,None)==before
    assert APReportingService(db)._rows()[0]['outstanding_amount']==0
    assert db.query(GeneralLedger).count()==2
    with pytest.raises(HTTPException):payments.post(payment_id,db=db,user=user)
    assert db.query(GeneralLedger).count()==2
    # Period closing must finalize the same receipt and invoice journals without
    # requiring legacy GRNI configuration or duplicating the paid allocation.
    from app.models.fiscal_period import FiscalPeriod
    from app.models.accounting_setting import AccountingSetting
    from app.services.period_closing_service import PeriodClosingService
    earnings=ChartOfAccount(account_number='300-100-103',account_name='Current earnings',account_type='EQUITY',normal_balance='CREDIT',is_posting=True,is_active=True)
    db.add(earnings);db.flush();db.add(AccountingSetting(setting_key='CURRENT_YEAR_EARNINGS_ACCOUNT',account_id=earnings.id));db.commit()
    period=db.query(FiscalPeriod).one()
    first=PeriodClosingService.close(db,period.id,user);db.commit()
    assert gr_journal.status=='POSTED' and je.status=='POSTED' and invoice.status=='POSTED'
    assert invoice.paid_amount==40
    assert len(first['closing_journal_ids'])==1
    rows=db.query(GeneralLedger).count()
    PeriodClosingService.reopen(db,period.id,user,'Review closing');db.commit()
    PeriodClosingService.close(db,period.id,user);db.commit()
    assert db.query(GeneralLedger).count()==rows
    assert invoice.paid_amount==40


def test_reopen_invoice_withdraws_draft_recognition_but_keeps_identity(stock_db,monkeypatch):
    data=setup_receiving(stock_db);db,wh,user,products,balances,expense,supplier=data
    payable=ChartOfAccount(account_number='200-100-1',account_name='AP',account_type='LIABILITY',normal_balance='CREDIT',is_posting=True,is_active=True)
    db.add(payable);db.flush();supplier.payable_account_id=payable.id;db.commit()
    receipt=create(data);GoodsReceiptService.post(db,receipt_id=receipt.id,user=user)
    invoice=db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    invoice.supplier_invoice_number='REAL-REOPEN';db.commit()
    service=SupplierInvoiceService(db);service.verify(invoice,user,commit=False)
    je=service.generate_journal(invoice,user,commit=False);db.commit();identity=je.id
    monkeypatch.setattr(supplier_invoices,'result',lambda db,invoice,user:{'status':invoice.status})
    supplier_invoices.admin_reopen(invoice.id,db=db,user=user)
    assert not invoice_is_accounted(db,invoice) and not je.lines
    service.verify(invoice,user,commit=False)
    restored=service.generate_journal(invoice,user,commit=False);db.commit()
    assert restored.id==identity and invoice_is_accounted(db,invoice)

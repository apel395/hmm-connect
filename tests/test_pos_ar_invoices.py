from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.models.account_receivable import AccountReceivable
from app.models.accounting_setting import AccountingSetting
from app.models.chart_of_account import ChartOfAccount
from app.models.customer import Customer
from app.models.customer_payment import CustomerPayment
from app.models.journal_line import JournalLine
from app.models.general_ledger import GeneralLedger
from app.models.stock_movement import StockMovement
from app.schemas.sales_transaction import SalesTransactionCreate, SalesTransactionPost, InvoiceARCorrection
from app.schemas.customer_payment import CustomerPaymentCreate
from app.services.ar_invoice_service import receive_payment, correct_posted_invoice
from app.services.ar_reporting_service import ARReportingService
from app.services.sales_transaction_service import SalesTransactionService as Service
from app.api.v1.ar_invoice_print import invoice as print_invoice
from test_finance_delivery_1007 import db, ADMIN
from test_pos_sell_catalog_1021 import products
from test_pos_pbjt import setup


def invoice_setup(db,monkeypatch,kind='INVOICE'):
    s,unit,loc,dept,base=db
    liability=setup(s,base,monkeypatch)
    s.add(AccountingSetting(setting_key='POS_TRANSFER_ACCOUNT',account_id=base[2].id));s.commit()
    customer=Customer(customer_code='PHR',customer_name='PHR',is_active=True)
    ar_account=ChartOfAccount(account_number='100-200-101',account_name='Piutang Usaha',account_type='ASSET',normal_balance='DEBIT',is_posting=True,is_active=True)
    s.add_all([customer,ar_account]);s.commit()
    p,_,_=products(s);p.pbjt_rate=10;p.selling_price=100000;p.service_charge_rate=0;s.commit()
    tx=Service.create(s,data=SalesTransactionCreate(transaction_type=kind,location_id=loc.id,department_id=dept.id,customer_id=customer.id,invoice_due_date=date(2026,2,1),sale_date=date(2026,1,5),items=[dict(product_id=p.id,quantity=1)]),user=ADMIN)
    return s,tx,customer,ar_account,base,liability


def test_invoice_post_creates_unpaid_ar_without_bank_or_receipt(db,monkeypatch):
    s,tx,customer,account,base,liability=invoice_setup(db,monkeypatch)
    tx=Service.post(s,transaction_id=tx.id,data=SalesTransactionPost(payment_method='BANK_TRANSFER',payment_received=110000),user=ADMIN)
    ar=s.query(AccountReceivable).one()
    assert ar.source_sale_id==tx.id and ar.customer_id==customer.id and ar.outstanding_amount==110000
    assert ar.received_amount==0 and ar.status=='UNPAID'
    assert tx.payment_received==0 and tx.payment_method is None
    entries={l.account_id:(l.debit,l.credit) for l in s.query(JournalLine).all()}
    assert entries=={account.id:(D(110000),D(0)),base[0].id:(D(0),D(100000)),liability.id:(D(0),D(10000))}
    assert not s.query(CustomerPayment).count() and not s.query(StockMovement).count()
    assert ARReportingService(s,ADMIN).summary()['metrics']['outstanding_receivables']==110000
    from app.services.financial_reconciliation_service import FinancialReconciliationService
    assert FinancialReconciliationService(s).accounts_receivable()['difference']==0
    assert FinancialReconciliationService(s).accounts_receivable(ar.location_id)['difference']==0
    printed=print_invoice(ar.id,s,ADMIN)
    assert printed['print_ready'] and printed['document']['tax_label']=='PBJT'
    with pytest.raises(HTTPException):Service.post(s,transaction_id=tx.id,data=SalesTransactionPost(),user=ADMIN)
    assert s.query(AccountReceivable).count()==1 and s.query(GeneralLedger).count()==3


def test_customer_receipts_are_partial_idempotent_and_scoped(db,monkeypatch):
    s,tx,customer,account,base,_=invoice_setup(db,monkeypatch)
    Service.post(s,transaction_id=tx.id,data=SalesTransactionPost(),user=ADMIN)
    ar=s.query(AccountReceivable).one()
    data=CustomerPaymentCreate(account_receivable_id=ar.id,cash_account_id=base[2].id,payment_date=date(2026,1,10),amount=40000,payment_method='BANK_TRANSFER',idempotency_key='receipt-request-1')
    first=receive_payment(s,data,ADMIN);again=receive_payment(s,data,ADMIN)
    assert first.id==again.id and s.query(CustomerPayment).count()==1
    assert ar.received_amount==40000 and ar.outstanding_amount==70000 and ar.status=='PARTIAL'
    assert s.query(GeneralLedger).count()==5
    limited=SimpleNamespace(**{**vars(ADMIN),'roles':[],'default_location_id':999})
    assert not ARReportingService(s,limited).detail()['items']
    with pytest.raises(HTTPException):receive_payment(s,data,limited)
    with pytest.raises(HTTPException):print_invoice(ar.id,s,limited)
    with pytest.raises(HTTPException):receive_payment(s,data.model_copy(update={'amount':D(70001),'idempotency_key':'receipt-too-much'}),ADMIN)
    receive_payment(s,data.model_copy(update={'amount':D(70000),'idempotency_key':'receipt-request-2'}),ADMIN)
    assert ar.status=='PAID' and ar.outstanding_amount==0 and ar.received_amount==110000
    assert s.query(CustomerPayment).count()==2 and s.query(GeneralLedger).count()==7
    from app.services.financial_reconciliation_service import FinancialReconciliationService
    assert FinancialReconciliationService(s).accounts_receivable(as_of=date(2026,1,7))['difference']==0
    assert FinancialReconciliationService(s).accounts_receivable(as_of=date(2026,1,7))['source_balance']==110000


def test_missing_customer_or_due_date_does_not_post_invoice(db,monkeypatch):
    s,tx,_,_,_,_=invoice_setup(db,monkeypatch)
    tx.customer_id=None;tx.invoice_due_date=None;s.commit()
    with pytest.raises(HTTPException):Service.post(s,transaction_id=tx.id,data=SalesTransactionPost(),user=ADMIN)
    assert tx.status=='DRAFT' and s.query(JournalLine).count()==s.query(AccountReceivable).count()==0


def test_legacy_paid_posting_is_corrected_once_without_duplicate_revenue(db,monkeypatch):
    s,tx,customer,account,base,liability=invoice_setup(db,monkeypatch,'POS')
    tx=Service.post(s,transaction_id=tx.id,data=SalesTransactionPost(payment_method='BANK_TRANSFER'),user=ADMIN)
    original=tx.journal_entry_id
    tx.transaction_type='INVOICE';s.commit() # simulate an invoice made by the old paid-sale implementation
    data=InvoiceARCorrection(customer_id=customer.id,invoice_due_date=date(2026,2,1),receivable_account_id=account.id,correction_date=date(2026,1,10),confirm_unpaid=True)
    correct_posted_invoice(s,tx,data,ADMIN)
    assert tx.journal_entry_id==original and tx.ar_correction_journal_id!=original
    assert s.query(AccountReceivable).one().outstanding_amount==110000
    assert sum((l.debit-l.credit for l in s.query(JournalLine).filter_by(account_id=base[2].id)),D(0))==0
    assert sum((l.credit for l in s.query(JournalLine).filter_by(account_id=base[0].id)),D(0))==100000
    assert sum((l.credit for l in s.query(JournalLine).filter_by(account_id=liability.id)),D(0))==10000
    with pytest.raises(HTTPException):correct_posted_invoice(s,tx,data,ADMIN)
    assert s.query(AccountReceivable).count()==1 and s.query(JournalLine).count()==5

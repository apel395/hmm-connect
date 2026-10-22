"""Customer invoices and their separately recorded receipts."""
from datetime import date
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import or_
from app.models.account_receivable import AccountReceivable
from app.models.chart_of_account import ChartOfAccount
from app.models.customer import Customer
from app.models.customer_payment import CustomerPayment
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.general_ledger import GeneralLedger
from app.models.sales_transaction import SalesTransaction
from app.schemas.journal import JournalCreate
from app.services.activity_service import ActivityService
from app.services.direct_coa_service import DirectCoaService
from app.services.document_number import next_document_number
from app.services.journal_service import JournalService
from app.services.location_access import apply_location_scope
from app.services.organization_access import business_unit_scope, department_scope

ZERO=Decimal('0')


class ARJournalService(JournalService):
    @staticmethod
    def generate_number(db):
        return next_document_number(db,'JV',digits=4)


def scoped_receivables(db,user):
    q=apply_location_scope(db.query(AccountReceivable),AccountReceivable.location_id,user)
    unit,dept=business_unit_scope(db,user),department_scope(user)
    if unit is not None:q=q.filter(AccountReceivable.business_unit_id==unit)
    if dept is not None:q=q.filter(AccountReceivable.department_id==dept)
    return q


def receivable_choices(db):
    return db.query(ChartOfAccount).filter(ChartOfAccount.is_active.is_(True),ChartOfAccount.is_posting.is_(True),ChartOfAccount.account_type=='ASSET',ChartOfAccount.normal_balance=='DEBIT',ChartOfAccount.account_number.like('100-200-%')).order_by(ChartOfAccount.account_number)


def receivable_account(db,account_id=None):
    if account_id is None:
        mapped=DirectCoaService(db).setting_account('ACCOUNTS_RECEIVABLE_ACCOUNT','Piutang Usaha')
        account_id=mapped.id if mapped else None
    if account_id is None:
        row=receivable_choices(db).filter(ChartOfAccount.account_number=='100-200-101').first()
    else:row=receivable_choices(db).filter(ChartOfAccount.id==account_id).first()
    if not row:raise HTTPException(409,'Choose an active Piutang Usaha posting account (100-200); invoice posting does not use a bank account')
    return row


def invoice_party(db,transaction,customer_id=None,due_date=None,account_id=None):
    customer=db.get(Customer,customer_id or transaction.customer_id) if (customer_id or transaction.customer_id) else None
    due=due_date or transaction.invoice_due_date
    if not customer or not customer.is_active:raise HTTPException(422,'Choose an active customer for the invoice')
    if not due or due<transaction.sale_date:raise HTTPException(422,'Choose an invoice due date on or after its invoice date')
    account=receivable_account(db,account_id or transaction.receivable_account_id)
    transaction.customer_id=customer.id;transaction.invoice_due_date=due;transaction.receivable_account_id=account.id
    return account


def create_receivable(db,transaction,account):
    if db.query(AccountReceivable).filter(or_(AccountReceivable.source_sale_id==transaction.id,AccountReceivable.invoice_number==transaction.transaction_number)).first():
        raise HTTPException(409,'This invoice already has an AR entry')
    ar=AccountReceivable(source_sale_id=transaction.id,account_id=account.id,customer_id=transaction.customer_id,
        invoice_number=transaction.transaction_number,invoice_date=transaction.sale_date,due_date=transaction.invoice_due_date,
        amount=transaction.total_amount,received_amount=ZERO,outstanding_amount=transaction.total_amount,status='UNPAID',
        location_id=transaction.location_id,business_unit_id=transaction.business_unit_id,department_id=transaction.department_id)
    db.add(ar);db.flush();return ar


def bank_choices(db):
    return db.query(ChartOfAccount).filter(ChartOfAccount.is_active.is_(True),ChartOfAccount.is_posting.is_(True),ChartOfAccount.account_type=='ASSET',ChartOfAccount.normal_balance=='DEBIT',or_(ChartOfAccount.account_subtype.in_(DirectCoaService.BANK_SUBTYPES),ChartOfAccount.account_number.like('100-110-%'),ChartOfAccount.account_number.like('100-100-%'))).order_by(ChartOfAccount.account_number)


def correct_posted_invoice(db,transaction,data,user):
    if data.correction_date<transaction.sale_date:raise HTTPException(422,'Correction date cannot precede the invoice date')
    if transaction.status!='POSTED' or transaction.transaction_type!='INVOICE' or transaction.ar_correction_journal_id:
        raise HTTPException(409,'Only an uncorrected posted invoice can be corrected to AR')
    if db.query(AccountReceivable).filter_by(source_sale_id=transaction.id).first():raise HTTPException(409,'Invoice is already in AR')
    source=db.query(JournalEntry).filter_by(id=transaction.journal_entry_id).with_for_update().first()
    if not source or source.status!='POSTED' or source.reference_type!='SALES_TRANSACTION' or source.reference_id!=transaction.id:
        raise HTTPException(409,'The original posted source journal could not be verified')
    source_lines=db.query(JournalLine).filter_by(journal_entry_id=source.id).all()
    debit=[l for l in source_lines if Decimal(l.debit or 0)>0]
    total=Decimal(transaction.total_amount or 0)
    if total<=0 or len(debit)!=1 or Decimal(debit[0].debit)!=total or sum((Decimal(l.credit or 0) for l in source_lines),ZERO)!=total:
        raise HTTPException(409,'Original journal no longer matches a single full cash/bank sale')
    book={};ledger={}
    for line in source_lines:
        old=book.get(line.account_id,(ZERO,ZERO));book[line.account_id]=(old[0]+Decimal(line.debit or 0),old[1]+Decimal(line.credit or 0))
    for line in db.query(GeneralLedger).filter_by(reference_type='SALES_TRANSACTION',reference_id=transaction.id).all():
        old=ledger.get(line.account_id,(ZERO,ZERO));ledger[line.account_id]=(old[0]+Decimal(line.debit or 0),old[1]+Decimal(line.credit or 0))
    if book!=ledger:raise HTTPException(409,'Original journal and GL differ; inspect before correcting this invoice')
    bank=bank_choices(db).filter(ChartOfAccount.id==debit[0].account_id).first()
    if not bank:raise HTTPException(409,'Original debit account is not a verified cash/bank posting account')
    ar_account=invoice_party(db,transaction,data.customer_id,data.invoice_due_date,data.receivable_account_id)
    correction=ARJournalService.post(db=db,user=user,journal=JournalCreate(posting_date=data.correction_date,
        document_type='INVOICE_AR_CORRECTION',document_number=transaction.transaction_number,reference_type='INVOICE_AR_CORRECTION',reference_id=transaction.id,
        description=f'Correct unpaid invoice {transaction.transaction_number} to AR',location_id=transaction.location_id,business_unit_id=transaction.business_unit_id,department_id=transaction.department_id,
        lines=[dict(account_id=ar_account.id,debit=total,credit=ZERO,description='Customer invoice receivable'),dict(account_id=bank.id,debit=ZERO,credit=total,description='Reverse incorrect payment recognition')]))
    transaction.ar_correction_journal_id=correction.id
    transaction.payment_received=ZERO;transaction.change_amount=ZERO;transaction.payment_method=None
    ar=create_receivable(db,transaction,ar_account)
    ActivityService.log(db=db,user=user,action='CORRECT',entity_type='SALES_TRANSACTION',entity_id=transaction.id,summary=f'Corrected unpaid invoice {transaction.transaction_number} to AR',details={'original_journal_id':source.id,'correction_journal_id':correction.id,'account_receivable_id':ar.id})
    db.commit();return transaction


def receive_payment(db,data,user):
    ar=scoped_receivables(db,user).filter(AccountReceivable.id==data.account_receivable_id).with_for_update().first()
    if not ar:raise HTTPException(404,'Account receivable not found')
    if data.idempotency_key:
        existing=db.query(CustomerPayment).filter_by(request_key=data.idempotency_key).first()
        if existing:
            if existing.account_receivable_id!=ar.id or Decimal(existing.amount)!=data.amount or existing.payment_date!=data.payment_date or existing.cash_account_id!=data.cash_account_id or existing.payment_method!=data.payment_method or existing.reference_number!=data.reference_number:
                raise HTTPException(409,'Payment retry key belongs to different receipt details')
            return existing
    if not ar.location_id or not ar.account_id:raise HTTPException(409,'Legacy AR requires a verified location and receivable account before receipt posting')
    if data.payment_date<ar.invoice_date:raise HTTPException(422,'Receipt date cannot precede the invoice date')
    outstanding=Decimal(ar.outstanding_amount or 0)
    if data.amount>outstanding or outstanding<=0:raise HTTPException(409,'Receipt exceeds the unpaid invoice balance')
    bank=bank_choices(db).filter(ChartOfAccount.id==data.cash_account_id).first()
    if not bank:raise HTTPException(422,'Choose an active cash/bank posting account for the actual receipt')
    account=receivable_account(db,ar.account_id)
    payment=CustomerPayment(payment_number=next_document_number(db,'CP'),account_receivable_id=ar.id,payment_date=data.payment_date,amount=data.amount,payment_method=data.payment_method,reference_number=data.reference_number,cash_account_id=bank.id,request_key=data.idempotency_key,status='POSTED')
    db.add(payment);db.flush()
    journal=ARJournalService.post(db=db,user=user,journal=JournalCreate(posting_date=payment.payment_date,document_type='CUSTOMER_PAYMENT',document_number=payment.payment_number,reference_type='CUSTOMER_PAYMENT',reference_id=payment.id,
        description=f'Customer receipt for {ar.invoice_number}',location_id=ar.location_id,business_unit_id=ar.business_unit_id,department_id=ar.department_id,
        lines=[dict(account_id=bank.id,debit=data.amount,credit=ZERO,description='Actual customer receipt'),dict(account_id=account.id,debit=ZERO,credit=data.amount,description=f'Settle {ar.invoice_number}')]))
    payment.journal_entry_id=journal.id
    ar.received_amount=Decimal(ar.received_amount or 0)+data.amount;ar.outstanding_amount=outstanding-data.amount
    ar.status='PAID' if ar.outstanding_amount==0 else 'PARTIAL'
    ActivityService.log(db=db,user=user,action='RECEIVE',entity_type='CUSTOMER_PAYMENT',entity_id=payment.id,summary=f'Received {payment.payment_number} for {ar.invoice_number}',details={'account_receivable_id':ar.id,'journal_id':journal.id,'amount':str(data.amount)})
    db.commit();db.refresh(payment);return payment

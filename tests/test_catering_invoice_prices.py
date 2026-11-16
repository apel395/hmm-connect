from decimal import Decimal as D
import pytest
from fastapi import HTTPException
from test_finance_delivery_1007 import db, ADMIN
from test_pos_ar_invoices import invoice_setup
from app.models.account_receivable import AccountReceivable
from app.models.general_ledger import GeneralLedger
from app.models.stock_movement import StockMovement
from app.schemas.sales_transaction import SalesTransactionUpdate, SalesTransactionPost
from app.services.sales_transaction_service import SalesTransactionService as Service
from app.api.v1.ar_invoice_print import invoice as print_invoice, update_document, InvoiceDocument
from app.api.v1.sales import get_sale


def test_catering_invoice_same_menu_different_prices_preserves_reference_and_posts_once(db,monkeypatch):
    s,tx,customer,account,base,liability=invoice_setup(db,monkeypatch)
    product=tx.lines[0].product
    reference=product.selling_price
    Service.update(s,transaction=tx,data=SalesTransactionUpdate(items=[
        {'product_id':product.id,'quantity':1,'unit_price':'230817730.00',
         'description':'Biweekly Catering Service Minas','registration_number':'268/MMH-MINAS/VI/2026',
         'service_period_from':'2026-06-01','service_period_to':'2026-06-15'},
        {'product_id':product.id,'quantity':1,'unit_price':'238436660.00',
         'description':'Biweekly Catering Service Minas','registration_number':'274/MMH-MINAS/VI/2026',
         'service_period_from':'2026-06-16','service_period_to':'2026-06-30'}]),user=ADMIN)
    assert product.selling_price==reference
    assert tx.subtotal==D('469254390') and tx.tax_amount==D('46925439') and tx.total_amount==D('516179829')
    assert s.query(GeneralLedger).count()==0
    saved=get_sale(tx.id,s,ADMIN)
    assert [D(str(line['unit_price'])) for line in saved['items']]==[D('230817730'),D('238436660')]
    # Later changes to the reference do not reset the agreed transaction prices.
    product.selling_price=D('1500000000');s.commit()
    Service.post(s,transaction_id=tx.id,data=SalesTransactionPost(),user=ADMIN)
    ar=s.query(AccountReceivable).one()
    result=print_invoice(ar.id,s,ADMIN)
    assert result['amount']==D('516179829') and result['print_ready']
    assert [D(line['amount']) for line in result['document']['lines']]==[D('230817730'),D('238436660')]
    assert [line['registration_number'] for line in result['document']['lines']]==[
        '268/MMH-MINAS/VI/2026','274/MMH-MINAS/VI/2026']
    assert [(line['service_period_from'],line['service_period_to']) for line in result['document']['lines']]==[
        ('2026-06-01','2026-06-15'),('2026-06-16','2026-06-30')]
    assert [line['source_line_id'] for line in result['document']['lines']]==[line.id for line in tx.lines]
    assert product.selling_price==D('1500000000')
    assert s.query(StockMovement).count()==0
    count=s.query(GeneralLedger).count()
    with pytest.raises(HTTPException): Service.post(s,transaction_id=tx.id,data=SalesTransactionPost(),user=ADMIN)
    assert s.query(GeneralLedger).count()==count
    with pytest.raises(HTTPException): Service.update(s,transaction=tx,data=SalesTransactionUpdate(items=[{'product_id':product.id,'quantity':1,'unit_price':1}]),user=ADMIN)


def test_catering_draft_price_changes_keep_invoice_identity(db,monkeypatch):
    s,tx,_,_,_,_=invoice_setup(db,monkeypatch)
    product=tx.lines[0].product
    identity=(tx.id,tx.transaction_number)
    for price in [250000,375000]:
        Service.update(s,transaction=tx,data=SalesTransactionUpdate(items=[{'product_id':product.id,'quantity':2,'unit_price':price}]),user=ADMIN)
        assert tx.total_amount==D(price)*D('2.2')
        assert (tx.id,tx.transaction_number)==identity and tx.status=='DRAFT'
        assert product.selling_price==100000


@pytest.mark.parametrize('price',[0,-1])
def test_invalid_catering_price_never_posts(db,monkeypatch,price):
    s,tx,_,_,_,_=invoice_setup(db,monkeypatch)
    product_id=tx.lines[0].product_id
    from pydantic import ValidationError
    with pytest.raises((HTTPException,ValidationError)):
        Service.update(s,transaction=tx,data=SalesTransactionUpdate(items=[{'product_id':product_id,'quantity':1,'unit_price':price}]),user=ADMIN)
    s.rollback()
    assert tx.status=='DRAFT' and not s.query(GeneralLedger).count()


def test_new_catering_invoice_accepts_distinct_price_lines(db,monkeypatch):
    from app.schemas.sales_transaction import SalesTransactionCreate
    s,source,customer,account,_,_=invoice_setup(db,monkeypatch)
    product=source.lines[0].product
    tx=Service.create(s,data=SalesTransactionCreate(transaction_type='INVOICE',location_id=source.location_id,
        department_id=source.department_id,customer_id=customer.id,invoice_due_date=source.invoice_due_date,
        sale_date=source.sale_date,items=[{'product_id':product.id,'quantity':1,'unit_price':250000},
                                       {'product_id':product.id,'quantity':1,'unit_price':300000}]),user=ADMIN)
    assert len(tx.lines)==2 and tx.lines[0].id!=tx.lines[1].id
    assert tx.total_amount==D('605000') and product.selling_price==100000
    assert s.query(GeneralLedger).count()==0


def test_normal_pos_keeps_single_menu_line_rule(db,monkeypatch):
    s,tx,_,_,_,_=invoice_setup(db,monkeypatch,'POS')
    product_id=tx.lines[0].product_id
    with pytest.raises(HTTPException):
        Service.update(s,transaction=tx,data=SalesTransactionUpdate(items=[
            {'product_id':product_id,'quantity':1,'unit_price':250000},
            {'product_id':product_id,'quantity':1,'unit_price':300000}]),user=ADMIN)
    s.rollback()
    assert tx.status=='DRAFT' and not s.query(GeneralLedger).count()


def test_catering_pdf_invoice_print_number_and_lines_are_not_accounting_mutations(db, monkeypatch):
    from app.models.journal_line import JournalLine
    from app.models.ar_invoice_layout import ARInvoiceLayout
    from pydantic import ValidationError
    s, tx, customer, account, base, liability = invoice_setup(db, monkeypatch)
    product = tx.lines[0].product
    Service.update(s, transaction=tx, data=SalesTransactionUpdate(items=[
        {'product_id':product.id,'quantity':1,'unit_price':'230817730.00',
         'description':'Biweekly Catering Service Minas','registration_number':'268/MMH-MINAS/VI/2026',
         'service_period_from':'2026-06-01','service_period_to':'2026-06-15'},
        {'product_id':product.id,'quantity':1,'unit_price':'238436660.00',
         'description':'Biweekly Catering Service Minas','registration_number':'274/MMH-MINAS/VI/2026',
         'service_period_from':'2026-06-16','service_period_to':'2026-06-30'},
    ]),user=ADMIN)
    Service.post(s,transaction_id=tx.id,data=SalesTransactionPost(),user=ADMIN)
    ar=s.query(AccountReceivable).one()
    before=(s.query(JournalLine).count(),s.query(GeneralLedger).count(),
            s.query(StockMovement).count(),ar.invoice_number,ar.amount,ar.outstanding_amount)
    line_data=print_invoice(ar.id,s,ADMIN)['document']['lines']
    doc=InvoiceDocument(
        billing_invoice_number='MMH-MNS/186/VI/2026',
        description='Invoice Catering Service in Minas for periode 01-30 Juni 2026',
        contract_number='SPHR00802A',tax_label='Tax 10% PB1 Jasa Catering',
        tax_amount=D('46925439.00'),lines=line_data)
    saved=update_document(ar.id,doc,s,ADMIN)
    printed=print_invoice(ar.id,s,ADMIN)
    assert saved['billing_invoice_number']=='MMH-MNS/186/VI/2026'
    assert printed['document']['billing_invoice_number']=='MMH-MNS/186/VI/2026'
    assert printed['invoice_number']==ar.invoice_number != 'MMH-MNS/186/VI/2026'
    assert printed['print_ready'] is True
    assert doc.total()==ar.amount==D('516179829')
    assert len(printed['document']['lines'])==2
    assert (s.query(JournalLine).count(),s.query(GeneralLedger).count(),
            s.query(StockMovement).count(),ar.invoice_number,ar.amount,ar.outstanding_amount)==before

    with pytest.raises(HTTPException) as tax_error:
        update_document(ar.id,doc.model_copy(update={'tax_amount':D('1000000'),
            'lines':[doc.lines[0].model_copy(update={'amount':D('276743169')}),doc.lines[1]]}),s,ADMIN)
    assert tax_error.value.status_code==422
    with pytest.raises(HTTPException) as fake_line:
        update_document(ar.id,doc.model_copy(update={'lines':[doc.lines[0].model_copy(update={'source_line_id':999999}),doc.lines[1]]}),s,ADMIN)
    assert fake_line.value.status_code==422
    with pytest.raises(ValidationError):
        InvoiceDocument(lines=[{'description':'Invalid period','service_period_from':'2026-07-01',
                                'service_period_to':'2026-06-30','amount':'1'}])


def test_customer_facing_catering_invoice_number_cannot_duplicate_another_document(db, monkeypatch):
    from app.schemas.sales_transaction import SalesTransactionCreate
    s, source, customer, _, _, _ = invoice_setup(db, monkeypatch)
    p=source.lines[0].product
    Service.post(s, transaction_id=source.id, data=SalesTransactionPost(), user=ADMIN)
    first=s.query(AccountReceivable).one()
    doc=InvoiceDocument(billing_invoice_number='MMH-MNS/186/VI/2026',tax_label='PBJT',
                        tax_amount=D('10000'),lines=[{'registration_number':'REG-A',
                            'description':'First service','amount':'100000'}])
    update_document(first.id,doc,s,ADMIN)
    second=Service.create(s,data=SalesTransactionCreate(transaction_type='INVOICE',
        location_id=source.location_id,department_id=source.department_id,
        customer_id=customer.id,invoice_due_date=source.invoice_due_date,sale_date=source.sale_date,
        items=[{'product_id':p.id,'quantity':1,'unit_price':100000}]),user=ADMIN)
    Service.post(s,transaction_id=second.id,data=SalesTransactionPost(),user=ADMIN)
    other=s.query(AccountReceivable).filter_by(source_sale_id=second.id).one()
    with pytest.raises(HTTPException) as duplicate:
        update_document(other.id,doc,s,ADMIN)
    assert duplicate.value.status_code==409

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
from app.api.v1.ar_invoice_print import invoice as print_invoice
from app.api.v1.sales import get_sale


def test_catering_invoice_same_menu_different_prices_preserves_reference_and_posts_once(db,monkeypatch):
    s,tx,customer,account,base,liability=invoice_setup(db,monkeypatch)
    product=tx.lines[0].product
    reference=product.selling_price
    Service.update(s,transaction=tx,data=SalesTransactionUpdate(items=[
        {'product_id':product.id,'quantity':1,'unit_price':'230817730.00'},
        {'product_id':product.id,'quantity':1,'unit_price':'238436660.00'}]),user=ADMIN)
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

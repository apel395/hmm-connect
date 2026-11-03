from datetime import datetime, time, timezone
from decimal import Decimal
import pytest
from fastapi import HTTPException
from test_store_request_flow import store_db
from app.models.chart_of_account import ChartOfAccount
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.inventory import Inventory
from app.models.inventory_return import InventoryReturn, InventoryReplacement
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.models.supplier_adjustment import SupplierAdjustment
from app.models.general_ledger import GeneralLedger
from app.models.journal_entry import JournalEntry
from app.models.stock_movement import StockMovement
from app.schemas.inventory_return import ReturnInput, ReplacementInput, ReturnCreditInput
from app.services import inventory_return_service as service
from app.services.fiscal_period_service import FiscalPeriodService
from app.api.v1.inventory_period_report import period_report
from app.api.v1.inventory_returns import create as api_create


@pytest.fixture
def setup_return(store_db):
    db, bu, dept, location, warehouse, requester, store_user, products = store_db
    today = FiscalPeriodService.business_today()
    accounts = []
    for code, kind, balance in [('CLEAR','ASSET','DEBIT'),('CREDIT','ASSET','DEBIT'),('AP','LIABILITY','CREDIT')]:
        a = ChartOfAccount(account_number=code, account_name=code, account_type=kind, normal_balance=balance, is_active=True, is_posting=True)
        db.add(a); accounts.append(a)
    db.flush()
    supplier = Supplier(code='RET-SUP', name='Return Supplier', payable_account_id=accounts[2].id)
    db.add(supplier); db.flush()
    receipt = GoodsReceipt(receipt_number='GR-RET', status='POSTED', supplier_id=supplier.id, warehouse_id=warehouse.id,
        destination_type='WAREHOUSE', business_unit_id=bu.id, department_id=dept.id, location_id=location.id,
        received_at=datetime.combine(today, time(), tzinfo=timezone.utc), subtotal=100, tax_amount=0, total_amount=100)
    receipt.items = [GoodsReceiptItem(product_id=p.id, quantity=10, unit_cost=10, destination_type='WAREHOUSE') for p in products]
    db.add(receipt)
    for p in products:
        db.add(Inventory(product_id=p.id, warehouse_id=warehouse.id, quantity=10, average_cost=Decimal('12.3456')))
    db.commit()
    return db, receipt, accounts, store_user, requester, today


def new_return(fixture, purpose='REPLACEMENT', quantity='3'):
    db, source, accounts, user, _, today = fixture
    row = service.create_return(db, ReturnInput(goods_receipt_id=source.id, purpose=purpose, return_date=today,
        reason='Damaged packaging', clearing_account_id=accounts[0].id,
        items=[{'goods_receipt_item_id': source.items[0].id, 'quantity':quantity}]), user)
    db.commit()
    return row


def invoice(fixture, paid=0):
    db, source, accounts, user, _, today = fixture
    row = SupplierInvoice(internal_invoice_number='INV-RET', supplier_invoice_number='Supplier-1', supplier_id=source.supplier_id,
        invoice_date=today, goods_receipt_id=source.id, status='POSTED', currency='IDR', business_unit_id=source.business_unit_id,
        department_id=source.department_id, location_id=source.location_id, subtotal=100, tax_amount=0, total_amount=100, paid_amount=paid)
    row.lines = [SupplierInvoiceLine(product_id=source.items[0].product_id, goods_receipt_item_id=source.items[0].id,
        description='Items', quantity=10, unit_price=10, line_amount=100, account_id=source.items[0].product.inventory_account_id)]
    db.add(row);db.commit()
    return row


def test_partial_return_and_four_decimal_replacement_exactly_once(setup_return):
    db, source, accounts, user, _, today = setup_return
    row = new_return(setup_return)
    assert db.query(StockMovement).count() == 0
    service.post_return(db, row.id, user);db.commit()
    stock = db.query(Inventory).filter_by(product_id=source.items[0].product_id).one()
    assert stock.quantity == 7
    assert row.total_cost == Decimal('37.04')
    movement = db.query(StockMovement).one()
    assert movement.unit_cost == Decimal('12.3456')
    with pytest.raises(HTTPException): service.post_return(db, row.id, user)
    with pytest.raises(HTTPException): service.guard_receipt(db, source.id)
    data = ReplacementInput(received_date=today, delivery_note='Replacement-1',
        items=[{'return_item_id':row.items[0].id,'quantity':3}])
    service.replace_goods(db, row.id, data, user);db.commit()
    assert stock.quantity == 10
    assert stock.average_cost == Decimal('12.3456')
    assert db.query(SupplierInvoice).count() == 0
    assert db.query(InventoryReplacement).count() == 1
    result = service.serialize(db, row)
    replacement = db.get(GoodsReceipt,result['replacement_receipts'][0]['id'])
    assert replacement.source_type == 'SUPPLIER_REPLACEMENT'
    assert replacement.items[0].unit_cost == Decimal('12.3456')
    with pytest.raises(HTTPException): service.replace_goods(db, row.id, data, user)
    assert db.query(StockMovement).count() == 2


@pytest.mark.parametrize('paid,expected_ap,expected_credit', [(0,30,0),(90,10,20),(100,0,30)])
def test_credit_preserves_paid_amount_and_separates_supplier_credit(setup_return,paid,expected_ap,expected_credit):
    db, source, accounts, user, _, today = setup_return
    inv = invoice(setup_return, paid)
    row = new_return(setup_return,'AP_CREDIT')
    service.post_return(db,row.id,user);db.commit()
    data = ReturnCreditInput(supplier_invoice_id=inv.id,credit_date=today,credit_reference='CN-1',net_amount=30,
        supplier_credit_account_id=accounts[1].id, variance_account_id=source.items[0].product.cogs_account_id)
    service.settle_credit(db,row.id,data,user);db.commit()
    assert inv.paid_amount == paid
    assert inv.adjustment_amount == expected_ap
    assert row.supplier_credit == expected_credit
    assert row.credit_applied == expected_ap
    assert inv.balance_amount == max(0,100-paid-expected_ap)
    assert db.query(SupplierAdjustment).count() == (1 if expected_ap else 0)
    gl = db.query(GeneralLedger).filter(GeneralLedger.reference_type=='SUPPLIER_RETURN_CREDIT').all()
    assert sum(r.debit for r in gl) == sum(r.credit for r in gl)
    with pytest.raises(HTTPException): service.settle_credit(db,row.id,data,user)
    with pytest.raises(HTTPException): service.guard_invoice(db,inv.id)


def test_credit_variance_requires_explicit_account_and_rolls_back(setup_return):
    db, source, accounts, user, _, today = setup_return
    inv = invoice(setup_return)
    row = new_return(setup_return,'AP_CREDIT')
    service.post_return(db,row.id,user);db.commit()
    before = db.query(JournalEntry).count()
    data = ReturnCreditInput(supplier_invoice_id=inv.id,credit_date=today,credit_reference='CN',net_amount=30)
    with pytest.raises(HTTPException): service.settle_credit(db,row.id,data,user)
    db.rollback()
    assert db.query(JournalEntry).count() == before
    assert inv.adjustment_amount == 0
    assert row.credit_journal_id is None


def test_over_return_and_later_line_failure_leave_stock_unchanged(setup_return):
    db, source, accounts, user, _, today = setup_return
    row = new_return(setup_return,quantity='8')
    other = new_return(setup_return,quantity='4')
    service.post_return(db,row.id,user);db.commit()
    with pytest.raises(HTTPException): service.post_return(db,other.id,user)
    assert db.query(StockMovement).count() == 1
    assert db.query(Inventory).filter_by(product_id=source.items[0].product_id).one().quantity == 2
    db.rollback()


def test_closed_period_and_authorization(setup_return):
    db, source, accounts, user, requester, today = setup_return
    data = ReturnInput(goods_receipt_id=source.id,purpose='REPLACEMENT',return_date=today,reason='Return',
        clearing_account_id=accounts[0].id,items=[{'goods_receipt_item_id':source.items[0].id,'quantity':1}])
    with pytest.raises(HTTPException) as error: api_create(data,db,requester)
    assert error.value.status_code == 403
    row = new_return(setup_return)
    from app.models.fiscal_period import FiscalPeriod
    period = db.query(FiscalPeriod).one();period.is_closed=True;period.is_open=False;db.commit()
    with pytest.raises(HTTPException): service.post_return(db,row.id,user)
    assert db.query(StockMovement).count() == 0


def test_period_report_returns_replacements_and_full_filtered_totals(setup_return):
    db, source, accounts, user, _, today = setup_return
    row = new_return(setup_return)
    service.post_return(db,row.id,user);db.commit()
    args = dict(date_from=today,date_to=today,warehouse_id=source.warehouse_id,business_unit_id=None,
        location_id=None,search=None,page_size=1,db=db,user=user)
    first = period_report(page=1,**args)
    second = period_report(page=2,**args)
    assert first['total_items'] == 2
    assert first['summary'] == second['summary']
    assert first['items'][0]['return_quantity'] == -3
    assert first['items'][0]['opening_quantity'] == 10
    assert first['items'][0]['closing_quantity'] == 7
    assert first['summary']['opening_value'] + first['summary']['in_value'] - first['summary']['out_value'] == first['summary']['closing_value']
    service.replace_goods(db,row.id,ReplacementInput(received_date=today,delivery_note='R',
        items=[{'return_item_id':row.items[0].id,'quantity':3}]),user);db.commit()
    final = period_report(page=1,**args)
    assert final['items'][0]['replacement_quantity'] == 3
    assert final['items'][0]['closing_quantity'] == 10


def test_split_replacements_allocate_original_currency_value_without_gain_loss(setup_return):
    db, source, accounts, user, _, today = setup_return
    row = new_return(setup_return)
    service.post_return(db,row.id,user);db.commit()
    values=[]
    for index in range(3):
        service.replace_goods(db,row.id,ReplacementInput(received_date=today,delivery_note=f'R-{index}',
            items=[{'return_item_id':row.items[0].id,'quantity':1}]),user);db.commit()
        latest=db.query(GoodsReceipt).filter_by(source_type='SUPPLIER_REPLACEMENT').order_by(GoodsReceipt.id.desc()).first()
        values.append(latest.items[0].replacement_line_value)
    assert values==[Decimal('12.35'),Decimal('12.35'),Decimal('12.34')]
    assert sum(values)==row.total_cost
    assert service.serialize(db,row)['clearing_balance']==0
    assert db.query(Inventory).filter_by(product_id=source.items[0].product_id).one().average_cost==Decimal('12.3456')
    for entry in db.query(JournalEntry).filter_by(reference_type='SUPPLIER_REPLACEMENT'):
        assert {line.account_id for line in entry.lines}=={accounts[0].id,source.items[0].product.inventory_account_id}


def test_return_tax_credit_is_bounded_by_returned_invoice_lines(setup_return):
    db, source, accounts, user, _, today = setup_return
    inv=invoice(setup_return)
    inv.supplier.is_pkp=True
    inv.lines[0].is_taxable=True;inv.lines[0].tax_rate=11
    db.commit()
    row=new_return(setup_return,'AP_CREDIT')
    service.post_return(db,row.id,user);db.commit()
    bad=ReturnCreditInput(supplier_invoice_id=inv.id,credit_date=today,credit_reference='CN-TAX',net_amount=30,tax_amount=4,
        variance_account_id=source.items[0].product.cogs_account_id)
    with pytest.raises(HTTPException):service.settle_credit(db,row.id,bad,user)
    db.rollback()
    vat=ChartOfAccount(account_number='VAT-RET',account_name='Input VAT',account_type='ASSET',normal_balance='DEBIT',is_active=True,is_posting=True)
    db.add(vat);db.flush()
    from app.models.accounting_setting import AccountingSetting
    db.add(AccountingSetting(setting_key='INPUT_VAT_ACCOUNT',account_id=vat.id));db.commit()
    bad.tax_amount=Decimal('3.30')
    service.settle_credit(db,row.id,bad,user);db.commit()
    assert row.credit_tax==Decimal('3.30')
    assert row.credit_applied==Decimal('33.30')
    vat_line=db.query(GeneralLedger).filter_by(reference_type='SUPPLIER_RETURN_CREDIT',account_id=vat.id).one()
    assert vat_line.credit==Decimal('3.30')


def test_replacement_is_excluded_from_purchase_reference_and_invoice_sources(setup_return):
    db, source, accounts, user, _, today=setup_return
    row=new_return(setup_return)
    service.post_return(db,row.id,user);db.commit()
    service.replace_goods(db,row.id,ReplacementInput(received_date=today,delivery_note='R',items=[{'return_item_id':row.items[0].id,'quantity':3}]),user);db.commit()
    replacement=db.query(GoodsReceipt).filter_by(source_type='SUPPLIER_REPLACEMENT').one()
    from app.services.supplier_invoice_service import SupplierInvoiceService
    with pytest.raises(HTTPException):SupplierInvoiceService(db).prepare_receipt_draft(replacement,user)
    with pytest.raises(HTTPException):SupplierInvoiceService._validate_receipt_set([replacement],source.supplier_id,source.business_unit_id,source.location_id,source.department_id)
    from app.services.item_reference_cost import receipt_costs
    costs=receipt_costs(db,[source.items[0].product_id],user,source.business_unit_id)
    assert costs[source.items[0].product_id]['last_purchase_price']==Decimal('10')


def test_multi_line_failure_does_not_mutate_earlier_return_line(setup_return):
    db, source, accounts, user, _, today=setup_return
    data=ReturnInput(goods_receipt_id=source.id,purpose='REPLACEMENT',return_date=today,reason='Multi-line return',clearing_account_id=accounts[0].id,
        items=[{'goods_receipt_item_id':line.id,'quantity':3} for line in source.items])
    row=service.create_return(db,data,user);db.commit()
    second=db.query(Inventory).filter_by(product_id=source.items[1].product_id).one()
    second.quantity=0;db.commit()
    with pytest.raises(HTTPException):service.post_return(db,row.id,user)
    db.rollback()
    assert db.query(StockMovement).count()==0
    assert db.query(Inventory).filter_by(product_id=source.items[0].product_id).one().quantity==10


def test_create_retry_and_duplicate_partial_replacement_are_not_second_events(setup_return):
    db, source, accounts, user, _, today=setup_return
    data=ReturnInput(goods_receipt_id=source.id,purpose='REPLACEMENT',return_date=today,reason='Retry',clearing_account_id=accounts[0].id,
        items=[{'goods_receipt_item_id':source.items[0].id,'quantity':3}])
    row=service.create_return(db,data,user);db.commit()
    assert service.create_return(db,data,user).id==row.id
    assert db.query(InventoryReturn).count()==1
    service.post_return(db,row.id,user);db.commit()
    assert service.create_return(db,data,user).id==row.id
    replacement=ReplacementInput(received_date=today,delivery_note='DEL-1',items=[{'return_item_id':row.items[0].id,'quantity':1}])
    service.replace_goods(db,row.id,replacement,user);db.commit()
    with pytest.raises(HTTPException):service.replace_goods(db,row.id,replacement,user)
    assert db.query(InventoryReplacement).count()==1
    data.reason='Different payload'
    with pytest.raises(HTTPException):service.create_return(db,data,user)

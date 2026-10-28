from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.models.goods_receipt import GoodsReceiptItem
from app.models.supplier_invoice import SupplierInvoice
from app.models.journal_entry import JournalEntry
from app.models.stock_movement import StockMovement
from app.models.general_ledger import GeneralLedger
from app.models.fiscal_period import FiscalPeriod
from app.models.role import Role
from app.schemas.goods_receipt import GoodsReceiptUpdate
from app.services.receiving_depost import depost_receiving
from app.services.receiving_stock_cycle import active_receipt_stock, DEPOST
from app.services.goods_receipt_service import GoodsReceiptService as Service
from test_stock_opname_functional import stock_db
from test_receiving_line_destinations import setup_receiving, create


def posted(stock_db, stock=True):
    data=setup_receiving(stock_db);db,wh,user,products,inventory,*_=data
    before=[(Decimal(s.quantity),Decimal(s.average_cost)) for s in inventory]
    receipt=create(data,warehouse=stock,items=[dict(product_id=products[0 if stock else 1].id,quantity=2,unit_cost=10)])
    Service.post(db,receipt_id=receipt.id,user=user)
    return data,receipt,before


@pytest.mark.parametrize('stock',[True,False])
def test_depost_edit_and_repost_preserve_receipt_and_journal_identity(stock_db,stock):
    data,receipt,before=posted(stock_db,stock);db,wh,user,products,inventory,*_=data
    journal=db.query(JournalEntry).filter_by(reference_type='GOODS_RECEIPT',reference_id=receipt.id).one();jid=journal.id;number=journal.journal_number
    original=db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    depost_receiving(db,receipt.id,user,'Correct receiving item')
    assert receipt.status=='DRAFT' and original.status=='VOID' and all(l.goods_receipt_item_id is None for l in original.lines)
    assert journal.status=='DRAFT' and not journal.lines and not active_receipt_stock(db,receipt.id)
    assert [(Decimal(s.quantity),Decimal(s.average_cost)) for s in inventory]==before
    Service.update(db,receipt=receipt,user=user,data=GoodsReceiptUpdate(received_at=receipt.received_at,warehouse_id=wh.id if stock else None,
        items=[dict(product_id=products[0 if stock else 1].id,quantity=3,unit_cost=12,is_taxable=False)]))
    Service.post(db,receipt_id=receipt.id,user=user)
    assert receipt.status=='POSTED'
    assert db.query(JournalEntry).filter_by(reference_type='GOODS_RECEIPT',reference_id=receipt.id).one().id==jid
    assert journal.journal_number==number and sum(l.debit for l in journal.lines)==36
    assert db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id,status='DRAFT').count()==1
    assert len(active_receipt_stock(db,receipt.id))==(1 if stock else 0)
    if stock:
        assert db.query(StockMovement).filter_by(reference_type=DEPOST).count()==1
        assert Decimal(inventory[0].quantity)==before[0][0]+3
        assert db.query(StockMovement).filter_by(goods_receipt_id=receipt.id).count()==3
    assert db.query(GeneralLedger).count()==0
    # Repeating the operation after another successful post reverses only this cycle.
    depost_receiving(db,receipt.id,user,'Second correction')
    assert Decimal(inventory[0].quantity)==before[0][0]


@pytest.mark.parametrize('kind',['confirmed_invoice','closed_period','subsequent_stock','permissions'])
def test_unsafe_depost_has_no_partial_changes(stock_db,kind):
    data,receipt,before=posted(stock_db);db,wh,user,products,inventory,*_=data
    invoice=db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    if kind=='confirmed_invoice':invoice.supplier_invoice_number='REAL-SUPPLIER-REF'
    elif kind=='closed_period':
        period=db.query(FiscalPeriod).one();period.is_open=False;period.is_closed=True
    elif kind=='subsequent_stock':
        db.add(StockMovement(product_id=products[0].id,warehouse_id=wh.id,movement_type='OUT',quantity=1,unit_cost=10,reference_type='TEST_ISSUE',reference_id=999))
    else:user.roles=[Role(name='STORE')]
    db.commit();qty=Decimal(inventory[0].quantity);count=db.query(StockMovement).count()
    with pytest.raises(HTTPException):depost_receiving(db,receipt.id,user,'Correction requested')
    assert receipt.status=='POSTED' and Decimal(inventory[0].quantity)==qty
    assert invoice.status=='DRAFT' and db.query(StockMovement).count()==count


def test_double_depost_is_rejected(stock_db):
    data,receipt,_=posted(stock_db);db,_,user,*_=data
    depost_receiving(db,receipt.id,user,'First correction')
    count=db.query(StockMovement).count()
    with pytest.raises(HTTPException):depost_receiving(db,receipt.id,user,'Repeated correction')
    assert db.query(StockMovement).count()==count and receipt.status=='DRAFT'

def test_depost_unposts_gl_but_reuses_journal_on_receiving_repost(stock_db):
    from app.api.v1.journals import post as post_journal
    data,receipt,_=posted(stock_db);db,_,user,*_=data
    journal=db.query(JournalEntry).filter_by(reference_type='GOODS_RECEIPT',reference_id=receipt.id).one()
    post_journal(journal.id,db,user)
    assert journal.status=='POSTED' and db.query(GeneralLedger).count()>0
    depost_receiving(db,receipt.id,user,'Correct recorded receiving')
    assert journal.status=='DRAFT' and not journal.lines and db.query(GeneralLedger).count()==0
    Service.post(db,receipt_id=receipt.id,user=user)
    assert db.query(JournalEntry).filter_by(reference_type='GOODS_RECEIPT',reference_id=receipt.id).one().id==journal.id
    post_journal(journal.id,db,user)
    assert db.query(GeneralLedger).count()==len(journal.lines)


def test_late_failure_rolls_back_invoice_inventory_and_journal(stock_db,monkeypatch):
    data,receipt,_=posted(stock_db);db,_,user,_,inventory,*_=data
    qty=inventory[0].quantity;count=db.query(StockMovement).count()
    invoice=db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    line_id=invoice.lines[0].goods_receipt_item_id
    def fail(**kwargs):raise RuntimeError('audit unavailable')
    monkeypatch.setattr('app.services.receiving_depost.ActivityService.log',fail)
    with pytest.raises(RuntimeError):depost_receiving(db,receipt.id,user,'Correction with failure')
    assert receipt.status=='POSTED' and invoice.status=='DRAFT'
    assert invoice.lines[0].goods_receipt_item_id==line_id
    assert inventory[0].quantity==qty and db.query(StockMovement).count()==count

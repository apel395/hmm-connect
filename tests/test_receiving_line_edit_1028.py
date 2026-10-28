from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.models.goods_receipt import GoodsReceiptItem
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.models.stock_movement import StockMovement
from app.models.general_ledger import GeneralLedger
from app.schemas.goods_receipt import GoodsReceiptUpdate
from app.services.goods_receipt_service import GoodsReceiptService as Service
from app.services.receiving_edit_policy import edit_block_reason
from test_stock_opname_functional import stock_db
from test_receiving_line_destinations import setup_receiving, create


def payload(receipt, items):
    return GoodsReceiptUpdate(received_at=receipt.received_at, warehouse_id=receipt.warehouse_id, items=items)


def line(item):
    return dict(item_id=item.id, quantity=item.quantity, unit_cost=item.unit_cost, is_taxable=item.is_taxable)


def test_remove_saved_line_recalculates_without_stock_or_journal_writes(stock_db):
    data=setup_receiving(stock_db);db,_,user,_,inventory,*_=data
    receipt=create(data);keep,remove=receipt.items
    old_inventory=[(i.quantity,i.average_cost) for i in inventory]
    result=Service.update(db,receipt=receipt,user=user,data=payload(receipt,[line(keep)]))
    assert [i.id for i in result.items]==[keep.id]
    assert db.get(GoodsReceiptItem,remove.id) is None
    assert result.subtotal==Decimal('20') and result.destination_type=='WAREHOUSE'
    assert [(i.quantity,i.average_cost) for i in inventory]==old_inventory
    assert db.query(StockMovement).count()==db.query(GeneralLedger).count()==0


def test_reselect_product_creates_new_identity_and_follows_master(stock_db):
    data=setup_receiving(stock_db);db,_,user,products,*_=data
    receipt=create(data,items=[dict(product_id=products[0].id,quantity=2,unit_cost=10)])
    old_id=receipt.items[0].id
    result=Service.update(db,receipt=receipt,user=user,data=payload(receipt,[dict(product_id=products[1].id,quantity=3,unit_cost=12,is_taxable=False)]))
    assert result.items[0].id!=old_id
    assert result.items[0].product_id==products[1].id
    assert result.destination_type=='DIRECT_USE' and result.warehouse_id is None
    assert result.subtotal==36 and not db.query(StockMovement).count()


def test_unknown_line_and_empty_receipt_rejected(stock_db):
    data=setup_receiving(stock_db);db,_,user,*_=data;receipt=create(data)
    with pytest.raises(ValidationError):payload(receipt,[])
    with pytest.raises(HTTPException) as err:
        Service.update(db,receipt=receipt,user=user,data=payload(receipt,[dict(item_id=99999,quantity=1,unit_cost=10,is_taxable=False)]))
    assert err.value.status_code==409 and len(receipt.items)==2


@pytest.mark.parametrize('status',['DRAFT','VERIFIED','POSTED','VOID'])
def test_invoice_link_prevents_silent_removal_or_detachment(stock_db,status):
    data=setup_receiving(stock_db);db,_,user,_,_,_,supplier=data;receipt=create(data);keep,remove=receipt.items
    invoice=SupplierInvoice(internal_invoice_number='LINK-EDIT',supplier_invoice_number='VENDOR-EDIT',supplier_id=supplier.id,invoice_date=date(2026,1,3),status=status,subtotal=20,total_amount=20)
    # Line-only linkage covers invoices containing more than one receipt.
    invoice.lines=[SupplierInvoiceLine(goods_receipt_item_id=remove.id,description='Referenced',quantity=remove.quantity,unit_price=remove.unit_cost,line_amount=20)]
    db.add(invoice);db.commit()
    with pytest.raises(HTTPException) as err:
        Service.update(db,receipt=receipt,user=user,data=payload(receipt,[line(keep)]))
    assert err.value.status_code==409
    db.rollback()
    assert db.get(GoodsReceiptItem,remove.id) is not None and invoice.lines[0].goods_receipt_item_id==remove.id


def test_posted_receipt_still_requires_correction_workflow(stock_db):
    data=setup_receiving(stock_db);db,_,user,*_=data;receipt=create(data)
    Service.post(db,receipt_id=receipt.id,user=user)
    assert 'posted' in edit_block_reason(receipt,None,user).lower()
    before=db.query(StockMovement).count()
    with pytest.raises(HTTPException):
        Service.update(db,receipt=receipt,user=user,data=payload(receipt,[line(receipt.items[0])]))
    assert db.query(StockMovement).count()==before and receipt.status=='POSTED'

@pytest.mark.parametrize('stock_line',[True,False])
def test_inconsistent_draft_with_posting_evidence_cannot_be_edited(stock_db,stock_line):
    from app.models.journal_entry import JournalEntry
    data=setup_receiving(stock_db);db,_,user,products,*_=data
    receipt=create(data,warehouse=stock_line,items=[dict(product_id=products[0 if stock_line else 1].id,quantity=2,unit_cost=10)])
    Service.post(db,receipt_id=receipt.id,user=user)
    invoice=db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one();invoice.status='VOID'
    if not stock_line:
        journal=db.query(JournalEntry).filter_by(reference_type='GOODS_RECEIPT',reference_id=receipt.id).one();journal.status='POSTED'
    receipt.status='DRAFT';db.commit()
    before=[(i.id,i.quantity,i.unit_cost) for i in receipt.items]
    with pytest.raises(HTTPException) as err:
        Service.update(db,receipt=receipt,user=user,data=payload(receipt,[line(receipt.items[0])]))
    assert err.value.status_code==409
    assert [(i.id,i.quantity,i.unit_cost) for i in receipt.items]==before

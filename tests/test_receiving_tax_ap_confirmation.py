from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.models.role import Role
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.schemas.goods_receipt import GoodsReceiptCreate
from app.services.goods_receipt_service import GoodsReceiptService
from app.services.supplier_invoice_service import SupplierInvoiceService
from test_stock_opname_functional import stock_db


def receive(stock_db, tax_rate=0, master_rate=11):
    db,warehouse,user,products,_=stock_db
    user.roles=[Role(name='SYSTEM_ADMINISTRATOR')]
    p=products[0];p.inventory_treatment='STOCK';p.tax_category='REVIEW_REQUIRED';p.is_taxable=True;p.tax_rate=master_rate
    supplier=Supplier(code='SUP',name='Non PKP',is_pkp=False);db.add(supplier);db.commit()
    payload=GoodsReceiptCreate(supplier_id=supplier.id,business_unit_id=user.default_business_unit_id,location_id=user.location_id,department_id=user.default_department_id,warehouse_id=warehouse.id,destination_type='WAREHOUSE',items=[dict(product_id=p.id,quantity=1,unit_cost=10,is_taxable=tax_rate>0,tax_rate=tax_rate)])
    row=GoodsReceiptService.create(db,data=payload,user=user)
    return db,user,supplier,p,row


def test_receiving_uses_master_tax_even_when_payload_says_zero(stock_db):
    db,user,supplier,p,row=receive(stock_db)
    assert row.items[0].is_taxable is True
    assert row.tax_amount==Decimal('1.10') and row.total_amount==Decimal('11.10')
    assert p.tax_category=='REVIEW_REQUIRED' and p.is_taxable is True and p.tax_rate==11


def test_receiving_master_tax_matches_payload(stock_db):
    db,user,supplier,p,row=receive(stock_db,11)
    assert row.items[0].is_taxable is True
    assert row.tax_amount==Decimal('1.10') and row.total_amount==Decimal('11.10')


def test_ap_tax_can_differ_from_receiving_but_non_pkp_still_rejected(stock_db):
    db,user,supplier,p,receipt=receive(stock_db,master_rate=0)
    receipt.status='POSTED'
    invoice=SupplierInvoice(internal_invoice_number='INV-TAX',supplier_invoice_number='SUP-TAX',supplier_id=supplier.id,invoice_date=date.today(),goods_receipt_id=receipt.id,business_unit_id=receipt.business_unit_id,location_id=receipt.location_id,department_id=receipt.department_id,subtotal=10,tax_amount=Decimal('1.10'),total_amount=Decimal('11.10'),status='DRAFT',source_type='HISTORICAL_IMPORT')
    invoice.lines=[SupplierInvoiceLine(product_id=p.id,goods_receipt_item_id=receipt.items[0].id,description=p.name,quantity=1,uom=p.uom,unit_price=10,line_amount=10,is_taxable=True,tax_rate=11,tax_amount=Decimal('1.10'))]
    db.add(invoice);db.commit()
    service=SupplierInvoiceService(db)
    assert service.match_summary(invoice)['can_verify'] is True
    with pytest.raises(HTTPException) as error:service.verify(invoice,user)
    assert 'PKP' in str(error.value.detail)
    assert receipt.tax_amount==0 and invoice.tax_amount==Decimal('1.10')
    supplier.is_pkp=True
    invoice.source_type='LIVE'
    invoice.tax_invoice_number='FP-TEST'
    invoice.tax_invoice_date=date.today()
    db.commit()
    verified=service.verify(invoice,user)
    assert verified.status=='VERIFIED'
    assert verified.tax_amount==Decimal('1.10') and verified.total_amount==Decimal('11.10')
    assert receipt.tax_amount==0 and p.tax_category=='REVIEW_REQUIRED'

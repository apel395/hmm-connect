"""Receiving must use current Item Master PPN, never the caller's percentage."""
from decimal import Decimal
from app.schemas.goods_receipt import GoodsReceiptUpdate
from app.services.goods_receipt_service import GoodsReceiptService as Service
from test_receiving_line_destinations import setup_receiving, create
from test_stock_opname_functional import stock_db


def test_receiving_ignores_typed_percentage_and_uses_master(stock_db):
    data=setup_receiving(stock_db)
    db,_,_,products,*_=data
    products[0].is_taxable=True; products[0].tax_rate=Decimal('11')
    products[1].is_taxable=False; products[1].tax_rate=Decimal('12')
    db.commit()
    receipt=create(data,items=[dict(product_id=p.id,quantity=2,unit_cost=10,is_taxable=True,tax_rate=99) for p in products])
    assert [(i.is_taxable,i.tax_rate) for i in receipt.items]==[(True,Decimal('11')),(False,Decimal('0'))]
    assert receipt.tax_amount==Decimal('2.20')


def test_authorized_draft_edit_refreshes_master_tax_and_preserves_identity(stock_db):
    data=setup_receiving(stock_db);db,_,user,products,*_=data
    receipt=create(data); identity=(receipt.id,receipt.receipt_number)
    products[0].is_taxable=True;products[0].tax_rate=Decimal('11');db.commit()
    result=Service.update(db,receipt=receipt,user=user,data=GoodsReceiptUpdate(received_at=receipt.received_at,warehouse_id=receipt.warehouse_id,
        items=[dict(item_id=i.id,quantity=i.quantity,unit_cost=i.unit_cost,is_taxable=False,tax_rate=0) for i in receipt.items]))
    assert (result.id,result.receipt_number)==identity
    assert result.tax_amount==Decimal('2.20')


def test_receiving_post_preserves_recorded_tax_when_master_changes(stock_db):
    data=setup_receiving(stock_db);db,_,user,products,*_=data
    products[0].is_taxable=True;products[0].tax_rate=Decimal('11');db.commit()
    receipt=create(data)
    products[0].tax_rate=Decimal('12');db.commit()
    Service.post(db,receipt_id=receipt.id,user=user)
    assert receipt.items[0].tax_rate==Decimal('11')
    assert receipt.tax_amount==Decimal('2.20')


def test_receiving_po_tax_uses_master_instead_of_po_or_payload(stock_db):
    from app.models.purchase_order import PurchaseOrder
    from app.models.purchase_order_item import PurchaseOrderItem
    from app.schemas.goods_receipt import GoodsReceiptCreate
    from app.api.v1.goods_receipts import remaining_items
    data=setup_receiving(stock_db);db,wh,user,products,_,_,supplier=data
    product=products[0];product.is_taxable=True;product.tax_rate=Decimal('11')
    order=PurchaseOrder(po_number='PO-MASTER-TAX',supplier_id=supplier.id,status='APPROVED',
        business_unit_id=user.default_business_unit_id,location_id=user.location_id,department_id=user.default_department_id)
    order.items=[PurchaseOrderItem(product_id=product.id,quantity=2,unit_price=10,received_quantity=0,is_taxable=False,tax_rate=0)]
    db.add(order);db.commit()
    candidate=remaining_items(order)[0]
    assert candidate['is_taxable'] and candidate['tax_rate']==Decimal('11')
    receipt=Service.create(db,user=user,data=GoodsReceiptCreate(purchase_order_id=order.id,warehouse_id=wh.id,
        items=[dict(purchase_order_item_id=order.items[0].id,quantity=2,unit_cost=10,is_taxable=True,tax_rate=99)]))
    assert receipt.tax_amount==Decimal('2.20')


def test_receiving_discount_lookup_uses_configured_credit_account(stock_db):
    from app.api.v1.goods_receipts import receiving_charge_accounts
    from app.models.accounting_setting import AccountingSetting
    from app.models.chart_of_account import ChartOfAccount
    data=setup_receiving(stock_db);db,_,user,*_=data
    assert receiving_charge_accounts(db,user)['discount_account'] is None
    account=ChartOfAccount(account_number='DISC-TEST',account_name='Purchase discount',account_type='EXPENSE',normal_balance='CREDIT',is_active=True,is_posting=True)
    db.add(account);db.flush();db.add(AccountingSetting(setting_key='PURCHASE_DISCOUNT_ACCOUNT',account_id=account.id));db.commit()
    assert receiving_charge_accounts(db,user)['discount_account']['id']==account.id
    account.is_active=False;db.flush()
    assert receiving_charge_accounts(db,user)['discount_account'] is None

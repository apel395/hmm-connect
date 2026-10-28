"""Explicit, audited rollback of an isolated posted receiving for correction."""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import or_
from app.dependencies.authorization import has_permission
from app.models.goods_receipt import GoodsReceipt
from app.models.product import Product
from app.models.inventory import Inventory
from app.models.stock_movement import StockMovement
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.models.journal_entry import JournalEntry
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.payment import PaymentAllocation
from app.services.activity_service import ActivityService
from app.services.location_access import enforce_location_access
from app.services.fiscal_period_service import FiscalPeriodService
from app.services.receiving_stock_cycle import active_receipt_stock, DEPOST

PERMISSIONS = ('receiving.manage','receiving.edit','receiving.post','journal.manage')

def can_depost(receipt, user):
    return receipt.status == 'POSTED' and all(has_permission(user,p) for p in PERMISSIONS)


def depost_receiving(db, receipt_id, user, reason):
    try:
        return _depost(db,receipt_id,user,reason)
    except Exception:
        db.rollback()
        raise


def _depost(db, receipt_id, user, reason):
    if not all(has_permission(user,p) for p in PERMISSIONS):
        raise HTTPException(403,'Receiving Manage/Edit/Post and Journal Manage permissions are required to depost receiving')
    if len(reason.strip()) < 3:
        raise HTTPException(422,'Enter a depost reason')
    receipt = db.query(GoodsReceipt).filter_by(id=receipt_id).with_for_update().first()
    if not receipt:
        raise HTTPException(404,'Receiving not found')
    enforce_location_access(user,receipt.location_id)
    if receipt.status != 'POSTED':
        raise HTTPException(409,'Only posted receiving can be deposted; refresh its current status')
    from app.services.goods_receipt_service import GoodsReceiptService as Service
    from app.services.supplier_invoice_service import SupplierInvoiceService
    FiscalPeriodService.validate_posting_date(db,Service.business_date(receipt.received_at),system_closing=True)
    ids=[item.id for item in receipt.items]
    linked=db.query(SupplierInvoiceLine.supplier_invoice_id).filter(SupplierInvoiceLine.goods_receipt_item_id.in_(ids))
    invoices=db.query(SupplierInvoice).filter(or_(SupplierInvoice.goods_receipt_id==receipt.id,SupplierInvoice.id.in_(linked)),SupplierInvoice.status.notin_({'VOID','REJECTED'})).order_by(SupplierInvoice.id).with_for_update().all()
    if len(invoices)>1:
        raise HTTPException(409,'Resolve duplicate linked invoices before deposting receiving')
    for invoice in invoices:
        journal=db.query(JournalEntry.id).filter_by(reference_type='SUPPLIER_INVOICE',reference_id=invoice.id).filter(JournalEntry.status!='VOID').first()
        allocated=db.query(PaymentAllocation.id).filter_by(supplier_invoice_id=invoice.id).first()
        if journal or allocated or Decimal(invoice.paid_amount or 0) or Decimal(invoice.adjustment_amount or 0) or not SupplierInvoiceService.is_unconfirmed_receipt_draft(invoice,receipt):
            raise HTTPException(409,f'Resolve supplier invoice {invoice.internal_invoice_number} before deposting receiving; only untouched automatic drafts can be withdrawn here')
    journals=db.query(JournalEntry).filter_by(reference_type='GOODS_RECEIPT',reference_id=receipt.id).filter(JournalEntry.status!='VOID').with_for_update().all()
    if len(journals)>1:
        raise HTTPException(409,'Multiple active receipt journals require Finance review')
    journal=journals[0] if journals else None
    from app.services.accounting_unpost import matching_ledger_rows
    from app.models.general_ledger import GeneralLedger
    if (journal and journal.status != 'POSTED' and matching_ledger_rows(db,journal)) or (not journal and db.query(GeneralLedger.id).filter_by(reference_type='GOODS_RECEIPT',reference_id=receipt.id).first()):
        raise HTTPException(409,'Receipt journal and GL status differ; Finance must inspect before deposting')
    movements=active_receipt_stock(db,receipt.id)
    from app.services.receiving_destination import warehouse_items
    if {r.goods_receipt_item_id for r in movements} != {i.id for i in warehouse_items(receipt)} or len(movements)!=len(warehouse_items(receipt)):
        raise HTTPException(409,'Receiving stock evidence does not match its current items; Finance must inspect it')
    db.query(Product).filter(Product.id.in_(sorted({i.product_id for i in receipt.items}))).order_by(Product.id).with_for_update().all()
    buckets=defaultdict(list)
    for movement in movements:
        buckets[(movement.product_id,movement.warehouse_id)].append(movement)
    reversals=[]
    for (product_id,warehouse_id),rows in sorted(buckets.items()):
        if db.query(StockMovement.id).filter(StockMovement.product_id==product_id,StockMovement.warehouse_id==warehouse_id,StockMovement.id>max(r.id for r in rows)).first():
            raise HTTPException(409,f'Product {product_id} has subsequent stock movements; reverse downstream activity first')
        stock=db.query(Inventory).filter_by(product_id=product_id,warehouse_id=warehouse_id).with_for_update().first()
        quantity=sum((Decimal(r.quantity) for r in rows),Decimal(0));value=sum((Decimal(r.quantity)*Decimal(r.unit_cost) for r in rows),Decimal(0))
        if not stock or Decimal(stock.quantity)<quantity:
            raise HTTPException(409,f'Product {product_id} has insufficient stock to depost this receiving')
        before_quantity=Decimal(stock.quantity);before_value=before_quantity*Decimal(stock.average_cost)
        remaining=before_quantity-quantity;remaining_value=before_value-value
        tolerance=before_quantity*Decimal('0.00005')+Decimal('0.01')
        if (remaining and remaining_value < 0) or (remaining==0 and abs(remaining_value)>tolerance):
            raise HTTPException(409,f'Product {product_id} valuation no longer permits a safe depost')
        reversals.append((stock,rows,remaining,remaining_value,before_quantity,before_value))
    order=db.query(PurchaseOrder).filter_by(id=receipt.purchase_order_id).with_for_update().first() if receipt.purchase_order_id else None
    po_rows={}
    if order:
        if db.query(GoodsReceipt.id).filter(GoodsReceipt.purchase_order_id==order.id,GoodsReceipt.status=='DRAFT',GoodsReceipt.id!=receipt.id).first():
            raise HTTPException(409,'Another receiving draft exists for this PO; resolve it first')
        totals=defaultdict(Decimal)
        for item in receipt.items:totals[item.purchase_order_item_id]+=Decimal(item.quantity)
        for item_id,quantity in sorted(totals.items()):
            row=db.query(PurchaseOrderItem).filter_by(id=item_id,purchase_order_id=order.id).with_for_update().first()
            if not row or Decimal(row.received_quantity)<quantity:
                raise HTTPException(409,'PO received quantities no longer match this receipt')
            po_rows[item_id]=(row,quantity)
    before={'status':receipt.status,'items':[{'id':i.id,'product_id':i.product_id,'quantity':str(i.quantity),'unit_cost':str(i.unit_cost)} for i in receipt.items],
        'journal':{'id':journal.id,'status':journal.status,'lines':[{'account_id':l.account_id,'debit':str(l.debit),'credit':str(l.credit)} for l in journal.lines]} if journal else None,
        'withdrawn_invoices':[{'id':i.id,'number':i.internal_invoice_number,'receipt_item_ids':[l.goods_receipt_item_id for l in i.lines]} for i in invoices]}
    if journal and journal.status=='POSTED':
        from app.services.accounting_unpost import unpost_journal
        unpost_journal(db,journal=journal,user=user,commit=False)
    if journal:
        journal.lines.clear() # No recognized DRAFT accrual while receiving is back in draft.
        journal.status='DRAFT';journal.posted_at=None;journal.posted_by_id=None
    for stock,rows,remaining,remaining_value,old_quantity,old_value in reversals:
        stock.quantity=remaining;stock.average_cost=remaining_value/remaining if remaining else Decimal(0)
        for row in rows:
            db.add(StockMovement(product_id=row.product_id,warehouse_id=row.warehouse_id,goods_receipt_id=receipt.id,goods_receipt_item_id=row.goods_receipt_item_id,
                movement_type='OUT',quantity=row.quantity,unit_cost=row.unit_cost,reference_type=DEPOST,reference_id=receipt.id,
                business_unit_id=receipt.business_unit_id,location_id=receipt.location_id,department_id=receipt.department_id,
                notes=f'Depost reversal of stock movement {row.id}: {reason.strip()}',inventory_account_id=row.inventory_account_id,
                offset_account_id=row.offset_account_id,journal_entry_id=journal.id if journal else None))
    for row,quantity in po_rows.values():row.received_quantity=Decimal(row.received_quantity)-quantity
    if order:
        order.status='RECEIVED' if all(Decimal(i.received_quantity or 0)>=Decimal(i.quantity) for i in order.items) else 'PARTIALLY_RECEIVED' if any(Decimal(i.received_quantity or 0)>0 for i in order.items) else 'APPROVED'
    for invoice in invoices:
        invoice.status='VOID';invoice.voided_at=datetime.now(timezone.utc)
        for line in invoice.lines:line.goods_receipt_item_id=None
        ActivityService.log(db=db,user=user,action='RECEIVING_DEPOST_INVOICE_WITHDRAWN',entity_type='SUPPLIER_INVOICE',entity_id=invoice.id,
            summary=f'Withdrew automatic draft {invoice.internal_invoice_number} when deposting {receipt.receipt_number}',details={'reason':reason.strip(),'receipt_id':receipt.id})
    receipt.status='DRAFT'
    from app.services.receiving_edit_policy import reopen_approved_receiving
    reopen_approved_receiving(db,receipt,user)
    ActivityService.log(db=db,user=user,action='RECEIVING_DEPOSTED',entity_type='GOODS_RECEIPT',entity_id=receipt.id,
        summary=f'Deposted {receipt.receipt_number} for correction',before_data=before,after_data={'status':'DRAFT','journal_id':journal.id if journal else None},
        details={'reason':reason.strip(),'reversed_stock_ids':[r.id for r in movements],
            'inventory':[{'product_id':s.product_id,'before_quantity':str(q),'before_value':str(v),'remaining_quantity':str(n),'remaining_value':str(rv),'zero_quantity_rounding_remainder':str(rv) if not n else None} for s,rows,n,rv,q,v in reversals]})
    db.commit();db.refresh(receipt);return receipt

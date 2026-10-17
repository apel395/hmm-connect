"""Atomic repair of falsely stocked, receiving-only item history.

Never invent an OUT, change source prices/tax/AP or erase subsequent warehouse
activity. A changed master is not evidence that real past issues never happened.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from app.dependencies.authorization import has_permission, is_superuser
from app.models.chart_of_account import ChartOfAccount
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.inventory import Inventory
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.general_ledger import GeneralLedger
from app.models.stock_movement import StockMovement
from app.services.fiscal_period_service import FiscalPeriodService
from app.services.general_ledger import GeneralLedgerService
from app.services.receiving_destination import line_destination, receipt_destination
from app.services.audit import record_audit

ZERO=Decimal('0')
CENT=Decimal('.01')


def money(value):
    return Decimal(value or 0).quantize(CENT, rounding=ROUND_HALF_UP)


def snapshot(row):
    return {c.name: str(getattr(row,c.name)) if isinstance(getattr(row,c.name), Decimal) else getattr(row,c.name) for c in row.__table__.columns}


def signature(rows):
    return Counter((r.account_id,money(r.debit),money(r.credit)) for r in rows if r.debit or r.credit)


def correct_receiving_only_stock(db, product, *, expense_account_id, user, reason):
    stocks=db.query(Inventory).filter(Inventory.product_id==product.id).order_by(Inventory.id).with_for_update().all()
    if not stocks:
        return {'corrected_receipts':[], 'removed_stock_rows':0}
    if not is_superuser(user) and not has_permission(user,'finance.manage'):
        raise HTTPException(403,'Finance management permission is required to correct existing stock accounting')
    if not reason or len(reason.strip())<3:
        raise HTTPException(422,'Enter a reason for correcting existing stock')
    account=db.get(ChartOfAccount,expense_account_id) if expense_account_id else None
    if not account or not account.is_active or not account.is_posting or account.account_type!='EXPENSE' or account.normal_balance!='DEBIT':
        raise HTTPException(422,'Select an active posting expense account before changing stocked items to Direct Use')
    events=db.query(StockMovement).filter(StockMovement.product_id==product.id).order_by(StockMovement.id).with_for_update().all()
    if any(e.movement_type!='IN' or e.reference_type!='GOODS_RECEIPT' or not e.goods_receipt_item_id or not e.goods_receipt_id or e.quantity<=0 for e in events):
        raise HTTPException(409,'Item has warehouse issues, transfers or adjustments. Correct that history separately before changing its treatment; no data changed')
    by_warehouse=defaultdict(list)
    for e in events:by_warehouse[e.warehouse_id].append(e)
    if set(by_warehouse)-{s.warehouse_id for s in stocks}:
        raise HTTPException(409,'Receiving movements and warehouse balances disagree; no data changed')
    for stock in stocks:
        members=by_warehouse[stock.warehouse_id]
        quantity=sum((e.quantity for e in members),ZERO)
        value=sum((e.quantity*e.unit_cost for e in members),ZERO)
        if stock.quantity!=quantity or money(stock.quantity*stock.average_cost)!=money(value):
            raise HTTPException(409,'Stock quantity/value does not match its receiving history; inspection required')
    by_receipt=defaultdict(list)
    for e in events:by_receipt[e.goods_receipt_id].append(e)
    before={'item':snapshot(product),'inventory':[snapshot(s) for s in stocks], 'movements':[snapshot(e) for e in events], 'receipts':[]}
    repaired=[]
    for rid in sorted(by_receipt):
        receipt=db.query(GoodsReceipt).filter(GoodsReceipt.id==rid).with_for_update().one()
        entries=by_receipt[rid]
        if product.catalog_type == "HOTEL" and receipt.department_id is None:
            raise HTTPException(409,"Hotel Direct Use requires a consuming department on the receiving document")
        if receipt.status!='POSTED' or receipt.received_at.year<2026:
            raise HTTPException(409,'Only posted 2026 receiving-only stock can be corrected automatically')
        journals=db.query(JournalEntry).filter(JournalEntry.reference_type=='GOODS_RECEIPT',JournalEntry.reference_id==rid,JournalEntry.status!='VOID').with_for_update().all()
        if len(journals)!=1 or journals[0].status!='POSTED':
            raise HTTPException(409,'Receiving requires one posted source journal before stock treatment correction')
        journal=journals[0]
        FiscalPeriodService.validate_posting_date(db,journal.posting_date)
        source=db.query(JournalLine).filter(JournalLine.journal_entry_id==journal.id).order_by(JournalLine.id).with_for_update().all()
        ledger=db.query(GeneralLedger).filter(GeneralLedger.reference_type=='GOODS_RECEIPT',GeneralLedger.reference_id==rid,GeneralLedger.reference_number==journal.journal_number).order_by(GeneralLedger.id).with_for_update().all()
        if signature(source)!=signature(ledger):
            raise HTTPException(409,'Receiving journal and General Ledger differ; correct that discrepancy first')
        all_items=db.query(GoodsReceiptItem).filter(GoodsReceiptItem.goods_receipt_id==rid).with_for_update().all()
        original_destinations={item.id:line_destination(receipt,item) for item in all_items}
        header_fields=('subtotal','tax_amount','total_amount','supplier_id','received_at','business_unit_id','location_id','department_id','purchase_order_id','market_list_id')
        item_fields=('product_id','quantity','unit_cost','is_taxable','tax_rate','tax_amount','purchase_order_item_id','market_list_item_id')
        original_header={key:getattr(receipt,key) for key in header_fields}
        original_items={item.id:{key:getattr(item,key) for key in item_fields} for item in all_items}
        old={'receipt':snapshot(receipt),'items':[snapshot(i) for i in all_items], 'journal_lines':[snapshot(l) for l in source], 'ledger':[snapshot(g) for g in ledger]}
        amounts=defaultdict(lambda:ZERO)
        seen=set()
        for movement in entries:
            item=next((i for i in all_items if i.id==movement.goods_receipt_item_id),None)
            if (not item or item.product_id!=product.id or item.id in seen or original_destinations[item.id]!='WAREHOUSE'
                    or item.destination_override_reason or movement.warehouse_id!=receipt.warehouse_id
                    or item.quantity!=movement.quantity or item.unit_cost!=movement.unit_cost
                    or movement.journal_entry_id not in (None,journal.id)):
                raise HTTPException(409,'Receipt line contains a warehouse exception or changed quantities/costs; automatic correction refused')
            seen.add(item.id)
            inventory_account=movement.inventory_account_id or product.inventory_account_id
            if not inventory_account:
                raise HTTPException(409,'Original inventory account is missing from stock history')
            original_account=db.get(ChartOfAccount,inventory_account)
            if not original_account or original_account.account_type != "ASSET" or original_account.normal_balance != "DEBIT":
                raise HTTPException(409,"Stock history does not identify an inventory asset debit")
            amounts[inventory_account]+=money(item.quantity*item.unit_cost)
        # All warehouse lines for this item must be represented, not a partial
        # duplicated receiving movement that happens to match current stock.
        expected={i.id for i in all_items if i.product_id==product.id and original_destinations[i.id]=='WAREHOUSE'}
        if seen!=expected:
            raise HTTPException(409,'Receiving line/movement coverage is incomplete')
        totals_before=(sum((l.debit for l in source),ZERO),sum((l.credit for l in source),ZERO))
        for inventory_account,amount in amounts.items():
            candidates=[l for l in source if l.account_id==inventory_account and l.credit==0 and l.debit>=amount]
            gl_candidates=[g for g in ledger if g.account_id==inventory_account and g.credit==0 and g.debit>=amount]
            if len(candidates)!=1 or len(gl_candidates)!=1:
                raise HTTPException(409,'Split inventory accounting requires a separate reviewed correction')
            debit=candidates[0];gl=gl_candidates[0]
            debit.debit-=amount;gl.debit-=amount
            line=JournalLine(journal_entry_id=journal.id,account_id=account.id,debit=amount,credit=ZERO,
                line_number=max((l.line_number or 0 for l in source),default=0)+1,
                description=f'Direct Use correction: {product.code}',
                **{k:getattr(debit,k) for k in ('business_unit_id','location_id','department_id','supplier_id')})
            copied={c.name:getattr(gl,c.name) for c in GeneralLedger.__table__.columns if c.name not in ('id','journal_number','created_at','updated_at')}
            copied.update(account_id=account.id,debit=amount,credit=ZERO,description=line.description,
                journal_number=GeneralLedgerService.generate_number(db),created_by_id=user.id)
            new_gl=GeneralLedger(**copied)
            db.add_all([line,new_gl]);source.append(line);ledger.append(new_gl)
            if debit.debit==0:db.delete(debit);source.remove(debit)
            if gl.debit==0:db.delete(gl);ledger.remove(gl)
        for item in all_items:
            if item.id in seen:
                item.destination_type='DIRECT_USE';item.expense_account_id=account.id
                item.destination_override_reason=None
            elif item.destination_type is None:
                item.destination_type=original_destinations[item.id]
        receipt.destination_type=receipt_destination(receipt)
        if receipt.destination_type=='DIRECT_USE':receipt.warehouse_id=None
        db.flush()
        if any(getattr(receipt,key)!=value for key,value in original_header.items()) or any(getattr(item,key)!=value for item in all_items for key,value in original_items[item.id].items()):
            raise HTTPException(409,'Receiving financial values or organization changed during correction; review the original source before retrying')
        if totals_before!=(sum((l.debit for l in source),ZERO),sum((l.credit for l in source),ZERO)) or signature(source)!=signature(ledger):
            raise HTTPException(409,'Accounting verification failed; correction rolled back')
        journal.updated_at=datetime.now(timezone.utc)
        import json
        receipt_audit=record_audit(db,user,'ITEM_TREATMENT_CORRECTION','GOODS_RECEIPT',f'Corrected {product.code} to Direct Use in {receipt.receipt_number}',entity_id=receipt.id,document_number=receipt.receipt_number,document_status=receipt.status,before_data=json.loads(json.dumps(old,default=str)),after_data={'product_id':product.id,'expense_account_id':account.id,'destination_type':receipt.destination_type},details={'reason':reason.strip(),'journal_id':journal.id})
        if getattr(user,'audit_source',None):receipt_audit.source=user.audit_source
        before['receipts'].append(old)
        repaired.append(receipt.receipt_number)
    for e in events:db.delete(e)
    for s in stocks:db.delete(s)
    db.flush()
    # JSON audit snapshots preserve the false source state instead of leaving
    # fabricated warehouse events or changing the payable/tax amounts.
    import json
    audit=record_audit(db,user,'ITEM_STOCK_HISTORY_CORRECTED','PRODUCT',f'Corrected receiving-only stock for {product.code}',entity_id=product.id,
        before_data=json.loads(json.dumps(before,default=str)),
        after_data={'expense_account_id':account.id,'receipts':repaired,'stock_rows':0},details={'reason':reason.strip(),'method':'ORIGINAL_RECEIVING_RECLASSIFICATION','no_synthetic_out':True})
    if getattr(user,'audit_source',None):audit.source=user.audit_source
    return {'corrected_receipts':repaired,'removed_stock_rows':len(stocks)}

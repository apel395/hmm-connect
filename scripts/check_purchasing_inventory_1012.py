"""Read-only production schema and stock/accounting evidence check."""
import json
from sqlalchemy import inspect,func
from app.core.database import SessionLocal
from app.models.goods_receipt import GoodsReceipt
from app.models.store_request import StoreIssue
from app.models.journal_entry import JournalEntry
from app.models.stock_movement import StockMovement


def main():
    with SessionLocal() as db:
        schema=inspect(db.bind)
        required={'goods_receipts':['market_list_id'],'goods_receipt_items':['market_list_item_id'],'store_issues':['issue_date']}
        columns={table:{name:name in {c['name'] for c in schema.get_columns(table)} for name in names} for table,names in required.items()}
        if not all(ok for table in columns.values() for ok in table.values()):
            print(json.dumps({'schema':columns,'migration_required':'20261012_purch_inventory'},indent=2));return
        journals=db.query(JournalEntry).filter(JournalEntry.reference_type.in_(['STORE_ISSUE','STOCK_OPNAME'])).all()
        source_counts=dict(db.query(StockMovement.reference_type,func.count()).filter(StockMovement.reference_type.in_(['STORE_REQUEST','STOCK_OPNAME'])).group_by(StockMovement.reference_type).all())
        result={'schema':columns,'market_list_receipts':db.query(GoodsReceipt).filter(GoodsReceipt.market_list_id.isnot(None)).count(),
            'legacy_issues_without_date':db.query(StoreIssue).filter(StoreIssue.issue_date.is_(None)).count(),
            'stock_event_counts':source_counts,
            'source_journals':[{'id':j.id,'source':j.reference_type,'source_id':j.reference_id,'status':j.status,'document':j.document_number} for j in journals]}
        print(json.dumps(result,indent=2,default=str))
        db.rollback()
    print('READ ONLY: no source documents, stock, journals, GL or opening balances changed.')

if __name__=='__main__':main()

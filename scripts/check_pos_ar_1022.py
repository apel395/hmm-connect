"""Read-only invoice-to-AR deployment check; never corrects posted data."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
from sqlalchemy import inspect, text
from app.core.database import SessionLocal
from app.services.ar_invoice_service import receivable_account
from fastapi import HTTPException


def main():
    with SessionLocal() as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        inspector=inspect(db.connection())
        wanted={'sales_transactions':['invoice_due_date','receivable_account_id','ar_correction_journal_id'], 'account_receivables':['source_sale_id','account_id','location_id','business_unit_id','department_id'], 'customer_payments':['journal_entry_id','cash_account_id','request_key']}
        schema={table:{column:column in {r['name'] for r in inspector.get_columns(table)} for column in columns} for table,columns in wanted.items()}
        result={'schema':schema}
        try:
            account=receivable_account(db);result['receivable_account']={'id':account.id,'code':account.account_number,'name':account.account_name}
        except HTTPException as exc:result['receivable_account_error']=exc.detail
        if all(all(cols.values()) for cols in schema.values()):
            result['invoices']=[dict(r) for r in db.execute(text("SELECT s.id,s.transaction_number,s.status,s.customer_id,s.total_amount,s.invoice_due_date,ar.id AS account_receivable_id,ar.received_amount,ar.outstanding_amount,s.ar_correction_journal_id FROM sales_transactions s LEFT JOIN account_receivables ar ON ar.source_sale_id=s.id WHERE s.transaction_type='INVOICE' ORDER BY s.id DESC LIMIT 20")).mappings()]
        print(json.dumps(result,default=str,indent=2));db.rollback()
    print('READ ONLY: no invoices, receipts, journals, GL, stock or opening balances changed.')


if __name__=='__main__':main()

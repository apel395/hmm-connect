#!/usr/bin/env python3
"""Read-only trace of computer expense and equipment asset postings."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from sqlalchemy import text
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        db.execute(text("SET LOCAL statement_timeout='30s'"))

        def rows(sql, params=None):
            return [dict(r) for r in db.execute(text(sql), params or {}).mappings()]

        codes=['700-500-121','100-600-104']
        accounts=rows('SELECT * FROM chart_of_accounts WHERE account_number=ANY(:codes)', {'codes':codes})
        journals=rows("""SELECT DISTINCT j.* FROM journal_entries j
            JOIN journal_lines l ON l.journal_entry_id=j.id
            JOIN chart_of_accounts a ON a.id=l.account_id
            WHERE a.account_number=ANY(:codes)
            ORDER BY j.id""", {'codes':codes})
        ids=[j['id'] for j in journals]
        numbers=[j['journal_number'] for j in journals]
        lines=rows("""SELECT l.*,a.account_number,a.account_name FROM journal_lines l
            JOIN chart_of_accounts a ON a.id=l.account_id
            WHERE l.journal_entry_id=ANY(:ids) ORDER BY l.journal_entry_id,l.line_number""", {'ids':ids})
        ledger=rows("""SELECT g.*,a.account_number,a.account_name FROM general_ledger g
            JOIN chart_of_accounts a ON a.id=g.account_id
            WHERE a.account_number=ANY(:codes) OR g.reference_number=ANY(:numbers)
            ORDER BY g.id""", {'codes':codes,'numbers':numbers})
        assets=rows("""SELECT to_jsonb(f) AS record FROM fixed_assets f
            WHERE f.id=2 OR f.asset_account_id IN (
                SELECT id FROM chart_of_accounts WHERE account_number='100-600-104')
            ORDER BY f.id""")
        invoice_ids=list({r['record']['purchase_invoice_id'] for r in assets
                          if r['record'].get('purchase_invoice_id')})
        invoices=rows('SELECT * FROM supplier_invoices WHERE id=ANY(:ids)', {'ids':invoice_ids})
        invoice_lines=rows("""SELECT l.*,a.account_number,a.account_name
            FROM supplier_invoice_lines l LEFT JOIN chart_of_accounts a ON a.id=l.account_id
            WHERE l.supplier_invoice_id=ANY(:ids) ORDER BY l.id""", {'ids':invoice_ids})
        report={'accounts':accounts,'journals':journals,'journal_lines':lines,'general_ledger':ledger,
                'fixed_assets':assets,'supplier_invoices':invoices,'supplier_invoice_lines':invoice_lines}
        path=Path('/tmp/computer-asset-postings.json')
        path.write_text(json.dumps(report,indent=2,default=str)+'\n')
        print(json.dumps(report,indent=2,default=str))
        print(f'READ ONLY: no changes. Trace saved to {path}')
        db.rollback()


if __name__=='__main__':
    main()

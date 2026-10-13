"""Read-only equity evidence for a selected balance-sheet date and location."""
import argparse
import json
from datetime import date
from decimal import Decimal
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.opening_balance import OpeningBalance
from app.services.financial_reporting_service import FinancialReportingService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of', type=date.fromisoformat, required=True)
    parser.add_argument('--location', type=int)
    args = parser.parse_args()
    with SessionLocal() as db:
        if db.bind.dialect.name == 'postgresql': db.execute(text('SET TRANSACTION READ ONLY'))
        report = FinancialReportingService(db).build(report_type='BALANCE_SHEET', as_of_date=args.as_of,
                                                     location_id=args.location, include_zero=True)
        evidence = report['summary']['YTD']['current']['earnings_reconciliation']
        openings, journals = [], []
        if evidence['account_id']:
            query = db.query(OpeningBalance).filter(OpeningBalance.account_id == evidence['account_id'],
                                                   OpeningBalance.fiscal_year == args.as_of.year)
            if args.location is not None: query = query.filter(OpeningBalance.location_id == args.location)
            openings = [{'id': r.id, 'location_id': r.location_id, 'balance_type': r.balance_type,
                         'amount': r.amount, 'posted_by_id': r.posted_by_id, 'created_at': r.created_at} for r in query.all()]
            query = db.query(JournalEntry, JournalLine).join(JournalLine, JournalLine.journal_entry_id == JournalEntry.id).filter(
                JournalEntry.status == 'POSTED', JournalLine.account_id == evidence['account_id'],
                JournalEntry.posting_date.between(date(args.as_of.year, 1, 1), args.as_of),
                JournalEntry.reference_type.notin_(('OPENING_BALANCE', 'OPENING_BALANCE_ADJUSTMENT')))
            if args.location is not None:
                from sqlalchemy import func
                query = query.filter(func.coalesce(JournalLine.location_id, JournalEntry.location_id) == args.location)
            journals = [{'id': j.id, 'number': j.journal_number, 'date': j.posting_date,
                         'source': j.reference_type, 'created_by_id': j.created_by_id, 'posted_by_id': j.posted_by_id,
                         'debit': l.debit, 'credit': l.credit} for j, l in query.all()]
        print(json.dumps({'as_of': args.as_of, 'location_id': args.location,
                          'equity_evidence': evidence, 'opening_records': openings, 'posted_equity_lines': journals,
                          'equity_rows': [r for r in report['rows'] if r['section'] == 'EQUITY'],
                          'totals': report['section_totals']}, default=lambda value: f'{value:.2f}' if isinstance(value, Decimal) else str(value), indent=2))
        db.rollback()
    print('READ ONLY: no openings, accounts, journals, GL or balances changed.')


if __name__ == '__main__': main()

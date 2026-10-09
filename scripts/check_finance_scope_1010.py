"""Read-only date range, department statement and journal unit inspection."""
import argparse
import json
import sys
from pathlib import Path
from datetime import date
from decimal import Decimal
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import func
from app.core.database import SessionLocal
from app.models.journal_entry import JournalEntry
from app.models.business_unit import BusinessUnit
from app.models.location import Location
from app.services.trial_balance_service import TrialBalanceService
from app.services.financial_reporting_service import FinancialReportingService
from app.api.v1.profit_loss import serialize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--from-date', type=date.fromisoformat, default=date(2026,10,1))
    parser.add_argument('--to-date', type=date.fromisoformat, default=date(2026,10,31))
    parser.add_argument('--location-id', type=int)
    args = parser.parse_args()
    with SessionLocal() as db:
        trial = TrialBalanceService(db).report(date_from=args.from_date, date_to=args.to_date, location_id=args.location_id, paginate=False)
        service = FinancialReportingService(db)
        report = service.build(report_type='PROFIT_LOSS', as_of_date=args.to_date, location_id=args.location_id)
        departments = service.department_reports(report)
        checks = {}
        for period in ('MTD','YTD'):
            checks[period] = {}
            for section, totals in report['section_totals'].items():
                actual = totals[period]['current']
                department_sum = sum((row['section_totals'][section][period]['current'] for row in departments), Decimal(0))
                checks[period][section] = {'total': actual, 'departments_total': department_sum, 'match': actual == department_sum}
        unit = db.query(Location.business_unit_id).filter(Location.id == JournalEntry.location_id).scalar_subquery()
        query = db.query(func.coalesce(JournalEntry.business_unit_id,unit),func.count(JournalEntry.id))
        if args.location_id is not None:
            query = query.filter(JournalEntry.location_id == args.location_id)
        unit_names = {row.id: row.name for row in db.query(BusinessUnit).all()}
        output = {'trial_balance': {'opening_as_of': trial['opening_as_of'], 'movement_from': trial['movement_from'],
                  'movement_to': trial['movement_to'], 'accounts': trial['total_items'], 'summary': trial['summary']},
                  'journal_units': [{'unit': unit_names.get(unit_id,'Unassigned'), 'journals': count} for unit_id,count in query.group_by(func.coalesce(JournalEntry.business_unit_id,unit)).all()],
                  'department_tables': [{'department': row['department_name'], 'rows': len(row['rows'])} for row in departments],
                  'department_totals': checks}
        print(json.dumps(serialize(output), indent=2))
        print('READ ONLY: no journals, openings, budgets, master data or balances changed.')
        if not all(value['match'] for period in checks.values() for value in period.values()):
            raise SystemExit('Department totals require inspection')


if __name__ == '__main__':
    main()

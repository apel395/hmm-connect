"""Read-only checks for Hotel/Catering management report delivery."""
import argparse
from datetime import date
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.database import SessionLocal
from app.api.v1.profit_loss import serialize
from app.services.financial_reporting_service import FinancialReportingService
from app.services.profit_loss_delivery import deliver, workbook_sheets

parser = argparse.ArgumentParser()
parser.add_argument('--as-of', type=date.fromisoformat, default=date(2026,10,31))
parser.add_argument('--location-id', type=int)
args = parser.parse_args()
with SessionLocal() as db:
    service = FinancialReportingService(db)
    for scope in ('HOTEL','CATERING','CONSOLIDATED'):
        if args.location_id and scope != 'CONSOLIDATED':
            continue
        report = deliver(service, as_of_date=args.as_of, report_scope=scope, location_id=args.location_id)
        data = {"scope":scope,"sheets":[name for name,_ in workbook_sheets(report)],
                "MTD":{r['key']:r['periods']['MTD']['current'] for r in report['presentation_rows'] if r['kind']=='subtotal'},
                "YTD":{r['key']:r['periods']['YTD']['current'] for r in report['presentation_rows'] if r['kind']=='subtotal'},
                "balance_control":report['balance_control'],"split_control":report['split_control']}
        print(json.dumps(serialize(data), indent=2))
    print('READ ONLY: no accounts, budgets, journals, openings or balances changed.')

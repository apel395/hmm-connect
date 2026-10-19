"""Read-only Hotel P&L attribution and ledger-net check for EC2."""
import argparse
import json
from datetime import date
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of',type=date.fromisoformat,default=date(2026,1,31))
    parser.add_argument('--location-id',type=int,default=8)
    args=parser.parse_args()
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from app.core.database import engine
    from app.services.financial_reporting_service import FinancialReportingService
    from app.services.profit_loss_delivery import deliver
    from app.api.v1.profit_loss import serialize
    with engine.connect() as connection,connection.begin():
        connection.execute(text('SET TRANSACTION READ ONLY'))
        with Session(bind=connection) as db:
            report=deliver(FinancialReportingService(db),as_of_date=args.as_of,location_id=args.location_id,report_scope='HOTEL',include_breakdown=False)
            totals={r['key']:r['periods']['YTD']['current'] for r in report['presentation_rows'] if r['kind']!='detail'}
            sections=report['section_totals']
            ledger_net=sections['REVENUE']['YTD']['current']-sections['COST_OF_REVENUE']['YTD']['current']-sections['EXPENSES']['YTD']['current']
            result=dict(as_of=args.as_of,scope=report['scope'],attribution=report['metadata']['hotel_attribution'],YTD=totals,
                        net_control=dict(ledger_net=ledger_net,report_net=totals['NOP'],match=ledger_net==totals['NOP']))
            print(json.dumps(serialize(result),indent=2))
            if ledger_net!=totals['NOP']:raise SystemExit('Report net differs from ledger; inspection required')
    print('READ ONLY: no journals, GL, COA or opening balances changed.')


if __name__=='__main__':main()

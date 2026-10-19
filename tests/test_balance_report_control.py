"""Full-scope balance evidence stays independent of report display choices."""
from datetime import date
from decimal import Decimal
from copy import deepcopy
from io import BytesIO
from openpyxl import load_workbook
from app.models.opening_balance import OpeningBalance
from app.models.financial_report_setting import FinancialReportSetting
from app.services.financial_reporting_service import FinancialReportingService
from app.services.balance_sheet_workbook import workbook_sheets
from app.services.xlsx_export import build_xlsx
from app.api.v1.profit_loss import serialize
from test_asset_filters_balance_export import setup_accounts, posting
from test_organization_and_asset_delivery import db


def test_balance_status_uses_complete_scope_even_when_details_are_hidden(db):
    setup_accounts(db)
    posting(db,'BALANCED',25,1)
    service=FinancialReportingService(db)
    report=service.build(report_type='BALANCE_SHEET',as_of_date=date(2026,10,19),location_id=1)
    assert report['balance_control']['is_balanced'] is True
    db.add(OpeningBalance(fiscal_year=2026,account_id=1,location_id=1,balance_type='DEBIT',amount=100))
    db.add(FinancialReportSetting(report_type='BALANCE_SHEET',selected_account_ids=[],header_only=True))
    db.commit()
    service=FinancialReportingService(db)
    report=service.build(report_type='BALANCE_SHEET',as_of_date=date(2026,10,19),location_id=1,kap=True)
    before=deepcopy(report['balance_control'])
    assert before['assets']==125 and before['liabilities_and_equity']==25
    assert before['difference']==Decimal(100) and before['is_balanced'] is False
    assert before['basis']=='COMPLETE_REPORT'
    data=serialize(report)
    assert data['balance_control']['difference']=='100.00'
    sheets=workbook_sheets(service,report)
    wb=load_workbook(BytesIO(build_xlsx(sheets)))
    for name in ('Summary','Account detail'):
        records=list(wb[name].values)
        assert next(r[1] for r in records if r[0]=='Balance status')=='Out of balance'
        assert next(r[1] for r in records if r[0]=='Difference')==100
    # Another location must not inherit this location's opening discrepancy.
    other=service.build(report_type='BALANCE_SHEET',as_of_date=date(2026,10,19),location_id=2)
    assert other['balance_control']['is_balanced'] is True
    assert db.query(OpeningBalance).one().amount==100

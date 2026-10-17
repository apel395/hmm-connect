"""Use PC LIPET for every Catering location, without allocating financial data."""
from copy import deepcopy
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook
from app.services.profit_loss_template import detail_rows, layouts
from app.services.xlsx_export import build_xlsx
from test_hotel_pl_template_departments import statement, amounts
from test_profit_loss_delivery import records, subtotal
from app.services.financial_reporting_service import FinancialReportingService
from app.services.profit_loss_delivery import deliver, workbook_sheets
from datetime import date


@pytest.mark.parametrize('location', ['Lipet','Rumin','Zamped','Pekanbaru','Head Office','New Location'])
def test_every_location_including_head_office_uses_pc_lipet(location):
    source=statement('', [('Food Revenue','REVENUE',1000), ('Food Cost','COST_OF_REVENUE',200), ('Salary','OPERATING_PAYROLL',80)])
    source.update(report_scope='CATERING', scope_labels={'location_id':location}, statistics={'rows':[]})
    before=deepcopy(source)
    rows=detail_rows(source, location, '2026-01-31')
    assert rows.template_profile['source_sheet']=='PC LIPET'
    assert len(rows.headers)==12
    assert rows[2][0]=='PROJECT CATERING DEPARTEMEN — '+location.upper()
    expected=[r['cells'].get('A',{}).get('label','') for i,r in layouts()['PROJECT']['rows'].items() if int(i)>=7]
    assert [r[0] if r else '' for r in rows[6:]]==expected
    assert next(r[1] for r in rows if r and r[0]=='Gross Profit')==800
    assert next(r[1] for r in rows if r and r[0]=='Gross Operating Income / Profit / Loss')==720
    assert source==before


def test_catering_export_summary_equals_locations_and_consolidated_keeps_same_layout(records):
    db,*_=records
    service=FinancialReportingService(db)
    catering=deliver(service,as_of_date=date(2026,10,10),report_scope='CATERING')
    sheets=workbook_sheets(catering)
    final=lambda rows: next(r for r in rows if r and r[0]=='Gross Operating Income / Profit / Loss')
    for period in ('MTD','YTD'):
        col=sheets[0][1].headers.index(period+' Current')
        summary_net=next(r for r in sheets[0][1] if r and r[0]=='NOP')
        assert summary_net[col]==sum(final(rows)[col] for _,rows in sheets[1:])
    assert not any(r and r[0].strip()=='Salaries & Wages' for r in sheets[0][1])
    wb=load_workbook(BytesIO(build_xlsx(sheets)))
    for sheet in wb:
        assert sheet.freeze_panes=='B7'
        assert sheet.sheet_view.zoomScale==100
        assert all(row.height==15 for row in sheet.row_dimensions.values())
        assert all(cell.data_type not in ('e','f') for row in sheet for cell in row)
    report=deliver(service,as_of_date=date(2026,10,10))
    combined=workbook_sheets(report)
    for name,rows in combined:
        if name.startswith('Project Catering ·'):
            assert rows.template_profile['source_sheet']=='PC LIPET'
    summary=combined[0][1]
    assert next(r[1] for r in summary if r and r[0]=='NETT OPERATING PROFIT')==subtotal(report,'NOP')


def test_pc_lipet_additional_actual_accounts_do_not_disappear():
    source=statement('', [('Catering income','REVENUE',1000), ('New project deduction','UNDER_EXPENSE',20)])
    source['report_scope']='CATERING'
    source['statistics']={'rows':[]}
    rows=detail_rows(source,'Catering','2026-01-31')
    labels=[r[0] if r else '' for r in rows]
    assert labels.index('   Catering income')<labels.index('Net Revenue Without SC')
    assert labels.index('   New project deduction')<labels.index('Total Other Expenses')
    assert next(r[1] for r in rows if r and r[0]=='Gross Operating Income / Profit / Loss')==980

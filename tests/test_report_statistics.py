from datetime import date
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from openpyxl import load_workbook
from test_profit_loss_delivery import records
from app.models.chart_of_account import ChartOfAccount
from app.models.statistical_value import StatisticalValue
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.budget import Budget, BudgetLine
from app.models.general_ledger import GeneralLedger
from app.services.report_statistics import SOURCES, save_mappings, mappings, aggregate
from app.services.financial_reporting_service import FinancialReportingService
from app.services.profit_loss_delivery import deliver, workbook_sheets
from app.services.xlsx_export import build_xlsx


@pytest.fixture
def statistical_records(records):
    db,hotel,c1,c2,dept,expenses = records
    stat = {}
    for key,(name,code,mode) in SOURCES.items():
        if not code or mode == 'financial':continue
        account=ChartOfAccount(account_number=code,account_name=name,account_type='STATISTIC',normal_balance='DEBIT',is_posting=False)
        db.add(account);db.flush();stat[key]=account
    room_revenue=ChartOfAccount(account_number='400-100-100',account_name='Room Sales',account_type='REVENUE',normal_balance='CREDIT',is_posting=True)
    db.add(room_revenue);db.flush()
    for month,available,occupied,rate,covers in [(1,100,80,16000,100),(2,100,20,16500,200)]:
        for key,value,unit in [('ROOM_AVAILABLE',available,'ROOM_NIGHT'),('ROOM_OCCUPIED',occupied,'ROOM_NIGHT'),('BOOKKEEPING_RATE',rate,'IDR/USD'),('FOOD_COVERS',covers,'COVER')]:
            db.add(StatisticalValue(account_id=stat[key].id,period=date(2026,month,1),location_id=hotel.id,actual=value,budget=available+10 if key=='ROOM_AVAILABLE' else occupied if key=='ROOM_OCCUPIED' else None,unit=unit,updated_by_id=1))
        j=JournalEntry(journal_number=f'STAT-REV-{month}',posting_date=date(2026,month,5),status='POSTED',reference_type='MANUAL',reference_id=0,location_id=hotel.id,business_unit_id=hotel.business_unit_id,department_id=dept.id)
        j.lines=[JournalLine(account_id=room_revenue.id,debit=0,credit=1000*month)]
        db.add(j)
    db.commit()
    return db,hotel,c1,c2,dept,stat,room_revenue


def item(report,key):return next(r for r in report['statistics']['rows'] if r['key']==key)
def build(db,**kwargs):return deliver(FinancialReportingService(db),as_of_date=date(2026,2,28),**kwargs)


def test_sum_latest_ratios_and_paid_room_mapping(statistical_records):
    db,h,_,_,_,stat,_=statistical_records
    before=db.query(JournalEntry).count(),db.query(GeneralLedger).count()
    report=build(db,report_scope='HOTEL')
    assert item(report,'ROOM_AVAILABLE')['periods']['YTD']['current']==200
    assert item(report,'ROOM_OCCUPIED')['periods']['YTD']['current']==100
    assert item(report,'OCCUPANCY')['periods']['YTD']['current']==Decimal('.5')
    assert item(report,'OCCUPANCY')['periods']['MTD']['current']==Decimal('.2')
    assert item(report,'BOOKKEEPING_RATE')['periods']['YTD']['current']==16500
    assert item(report,'FOOD_COVERS')['periods']['YTD']['current']==300
    assert item(report,'ADR')['periods']['YTD']['current'] is None
    save_mappings(db,{'ROOM_SOLD':stat['ROOM_OCCUPIED'].id});db.commit()
    mapped=build(db,report_scope='HOTEL')
    assert item(mapped,'ADR')['periods']['YTD']['current']==30
    assert item(mapped,'ADR')['periods']['MTD']['current']==100
    assert item(mapped,'BOOKKEEPING_RATE')['periods']['YTD']['current']==16500
    assert before==(db.query(JournalEntry).count(),db.query(GeneralLedger).count())
    assert mapped['section_totals']==report['section_totals']


def test_location_total_not_double_counted_and_access_is_scoped(statistical_records):
    db,h,c1,_,dept,stat,_=statistical_records
    for key,value in [('ROOM_AVAILABLE',10),('ROOM_OCCUPIED',5)]:
        db.add(StatisticalValue(account_id=stat[key].id,period=date(2026,2,1),location_id=h.id,department_id=dept.id,actual=value,unit='ROOM_NIGHT',updated_by_id=1))
        db.add(StatisticalValue(account_id=stat[key].id,period=date(2026,2,1),location_id=c1.id,actual=10000,unit='ROOM_NIGHT',updated_by_id=1))
    db.commit()
    assert item(build(db),'ROOM_AVAILABLE')['periods']['YTD']['current']==200
    assert item(build(db),'ROOM_OCCUPIED')['periods']['YTD']['current']==100
    scoped=build(db,report_scope='HOTEL',department_id=dept.id)
    assert item(scoped,'ROOM_AVAILABLE')['periods']['MTD']['current']==10
    from app.api.v1.financial_reports import comparison
    user=SimpleNamespace(id=1,location_id=h.id,default_location_id=h.id,roles=[])
    report=comparison(report_type='PROFIT_LOSS',as_of_date=date(2026,2,28),report_scope='HOTEL',db=db,user=user)
    assert Decimal(item(report,'ROOM_AVAILABLE')['periods']['YTD']['current'])==200
    with pytest.raises(HTTPException):
        comparison(report_type='PROFIT_LOSS',as_of_date=date(2026,2,28),location_id=c1.id,report_scope='CATERING',db=db,user=user)


def test_missing_and_zero_inputs_and_month_comparison(statistical_records):
    db,h,_,_,_,stat,_=statistical_records
    record=db.query(StatisticalValue).filter_by(account_id=stat['ROOM_OCCUPIED'].id,period=date(2026,2,1)).one()
    record.actual=0;db.commit()
    report=build(db,report_scope='HOTEL')
    assert item(report,'ROOM_OCCUPIED')['periods']['MTD']['current']==0
    assert item(report,'OCCUPANCY')['periods']['MTD']['current']==0
    assert item(report,'ROOM_OCCUPIED')['periods']['MTD']['last_month']==80
    assert item(report,'GUESTS')['periods']['MTD']['current'] is None
    assert item(report,'ROOM_OCCUPIED')['periods']['MTD']['last_year'] is None
    db.query(StatisticalValue).filter_by(account_id=stat['ROOM_AVAILABLE'].id,period=date(2026,2,1)).one().actual=0;db.commit()
    assert item(build(db,report_scope='HOTEL'),'OCCUPANCY')['periods']['MTD']['current'] is None


def test_budget_adr_uses_room_budget_and_paid_room_statistics(statistical_records):
    db,h,_,_,_,stat,revenue=statistical_records
    save_mappings(db,{'ROOM_SOLD':stat['ROOM_OCCUPIED'].id})
    budget=Budget(budget_number='STAT-BUDGET',name='Hotel',fiscal_year=2026,date_from=date(2026,1,1),date_to=date(2026,12,31),status='APPROVED')
    budget.lines=[BudgetLine(account_id=revenue.id,location_id=h.id,business_unit_id=h.business_unit_id,month=1,budget_amount=900),BudgetLine(account_id=revenue.id,location_id=h.id,business_unit_id=h.business_unit_id,month=2,budget_amount=1100)]
    db.add(budget);db.commit()
    report=build(db,report_scope='HOTEL',budget_id=budget.id)
    assert item(report,'ADR')['periods']['YTD']['budget']==20
    assert item(report,'ADR')['periods']['YTD']['variance']==10
    assert item(report,'OCCUPANCY')['periods']['YTD']['budget']==Decimal(100)/220


def test_catering_room_revenue_and_statistics_never_enter_hotel_adr(statistical_records):
    db,h,c1,_,_,stat,revenue=statistical_records
    save_mappings(db,{'ROOM_SOLD':stat['ROOM_OCCUPIED'].id})
    journal=JournalEntry(journal_number='CATERING-SAME-COA',posting_date=date(2026,2,5),status='POSTED',reference_type='MANUAL',reference_id=0,location_id=c1.id,business_unit_id=c1.business_unit_id)
    journal.lines=[JournalLine(account_id=revenue.id,debit=0,credit=90000)]
    db.add(journal);db.commit()
    assert item(build(db),'ADR')['periods']['YTD']['current']==30
    catering=build(db,report_scope='CATERING')
    assert {r['key'] for r in catering['statistics']['rows']}=={'FOOD_COVERS','BEVERAGE_COVERS'}


def test_mapping_validation_and_api_setup_roundtrip(statistical_records):
    db,_,_,_,_,stat,revenue=statistical_records
    from app.api.v1.financial_reports import setup,save_setup,ReportSetupInput
    user=SimpleNamespace(id=1,roles=[])
    data=setup(db,user)
    assert data['effective_statistic_accounts']['BOOKKEEPING_RATE']==stat['BOOKKEEPING_RATE'].id
    assert 'ROOM_SOLD' not in data['effective_statistic_accounts']
    save_setup(ReportSetupInput(statistic_accounts={'ROOM_SOLD':stat['ROOM_OCCUPIED'].id}), 'PROFIT_LOSS', db, user)
    assert setup(db,user)['statistic_accounts']['ROOM_SOLD']==stat['ROOM_OCCUPIED'].id
    with pytest.raises(HTTPException):save_mappings(db,{'BOOKKEEPING_RATE':revenue.id})
    with pytest.raises(HTTPException):save_mappings(db,{'UNKNOWN':stat['ROOM_OCCUPIED'].id})


def test_unit_and_currency_mismatch_are_not_added(statistical_records):
    db,h,_,_,_,stat,_=statistical_records
    db.query(StatisticalValue).filter_by(account_id=stat['BOOKKEEPING_RATE'].id,period=date(2026,1,1)).one().unit='IDR/EUR'
    db.commit()
    row=item(build(db,report_scope='HOTEL'),'BOOKKEEPING_RATE')
    assert row['periods']['MTD']['current']==16500
    assert row['periods']['MTD']['last_month'] is None
    assert 'currency pair' in row['issues']['MTD']['last_month']
    rows=[SimpleNamespace(period=date(2026,2,1),location_id=1,department_id=None,unit='IDR/USD',actual=100),SimpleNamespace(period=date(2026,2,1),location_id=2,department_id=None,unit='IDR/USD',actual=200)]
    assert aggregate(rows,date(2026,1,1),date(2026,2,28),'actual','latest')[0] is None


def test_export_statistical_rows_numeric_percent_and_no_financial_effect(statistical_records,tmp_path):
    db,*_=statistical_records
    report=build(db,report_scope='HOTEL')
    content=build_xlsx(workbook_sheets(report))
    wb=load_workbook(BytesIO(content))
    sheet=wb['Summary']
    row=next(r for r in sheet if r[0].value=='Occupancy (%)')
    assert row[1].value==.2 and row[10].value==.5 and row[1].number_format=='0.00%'
    rate=next(r for r in sheet if r[0].value=='Bookkeeping Rate (IDR/USD)')
    assert rate[1].value==rate[10].value==16500
    assert all(cell.data_type!='e' for s in wb for r in s for cell in r)
    import os
    if output:=os.environ.get('STATISTICS_QA_XLSX'):
        from pathlib import Path
        Path(output).write_bytes(content)
        import json
        Path(output+'.json').write_text(json.dumps(report,default=str))

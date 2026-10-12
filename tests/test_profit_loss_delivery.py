from datetime import date
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from app.models import Base
from app.models.business_unit import BusinessUnit
from app.models.location import Location
from app.models.department import Department
from app.models.location_department import LocationDepartment
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.accounting_setting import AccountingSetting
from app.services.financial_reporting_service import FinancialReportingService
from app.services.profit_loss_delivery import deliver, workbook_sheets
from app.services.xlsx_export import build_xlsx

@pytest.fixture
def records():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    hotel = BusinessUnit(code='HOTEL', name='Hotel')
    catering = BusinessUnit(code='CATERING', name='Project Catering')
    db.add_all([hotel, catering]); db.flush()
    h = Location(code='H', name='Hotel', business_unit_id=hotel.id)
    c1 = Location(code='C1', name='Location one', business_unit_id=catering.id)
    c2 = Location(code='C2', name='Location two', business_unit_id=catering.id)
    d = Department(code='HK', name='House Keeping', business_unit_id=hotel.id)
    accounts = [ChartOfAccount(account_number=f'700-{i}', account_name=name, account_type='EXPENSE', normal_balance='DEBIT', is_posting=True, financial_statement_group=group) for i,(name,group) in enumerate([('Cost','COST_OF_REVENUE'),('Salary','OPERATING_EXPENSE'),('Supplies','OPERATING_EXPENSE'),('Admin salary','OPERATING_EXPENSE'),('Admin expenses','OPERATING_EXPENSE'),('Other','OTHER_EXPENSE'),('Unknown',None)])]
    revenue = ChartOfAccount(account_number='400', account_name='Revenue', account_type='REVENUE', normal_balance='CREDIT', is_posting=True)
    db.add_all([h,c1,c2,d,revenue,*accounts]); db.flush()
    db.add(LocationDepartment(location_id=h.id,department_id=d.id))
    for acc, cat in zip(accounts[1:5],['OPERATING_PAYROLL','OPERATING_EXPENSE','OVERHEAD_PAYROLL','OVERHEAD_EXPENSE']):
        db.add(AccountingSetting(setting_key=f'PL_CATEGORY:{acc.id}', account_id=acc.id, description=cat))
    for idx,(loc,dept,mult) in enumerate([(h,d.id,1),(c1,None,2),(c2,None,3)]):
        j=JournalEntry(journal_number=f'PL-{idx}',posting_date=date(2026,10,5),status='POSTED',reference_type='MANUAL',reference_id=0,location_id=loc.id,business_unit_id=loc.business_unit_id,department_id=dept)
        j.lines=[JournalLine(account_id=revenue.id,debit=0,credit=1000*mult)] + [JournalLine(account_id=a.id,debit=amount*mult,credit=0) for a,amount in zip(accounts,[100,50,40,30,20,10,5])]
        db.add(j)
    db.commit();yield db,h,c1,c2,d,accounts
    db.close();engine.dispose()


def subtotal(report,key):
    return next(r for r in report['presentation_rows'] if r['key']==key)['periods']['MTD']['current']


def test_scopes_and_management_subtotals_keep_every_expense(records):
    db,h,c1,c2,d,accounts=records
    service=FinancialReportingService(db)
    hotel=deliver(service,as_of_date=date(2026,10,10),report_scope='HOTEL')
    assert subtotal(hotel,'GOI')==Decimal(810)
    assert subtotal(hotel,'GOP')==Decimal(760)
    assert subtotal(hotel,'NOP')==Decimal(745)
    assert len(hotel['group_reports'])==1
    assert hotel['group_reports'][0]['department_name']=='House Keeping'
    catering=deliver(service,as_of_date=date(2026,10,10),report_scope='CATERING')
    assert subtotal(catering,'NOP')==Decimal(3725)
    assert {r['scope']['location_id'] for r in catering['group_reports']}=={c1.id,c2.id}
    consolidated=deliver(service,as_of_date=date(2026,10,10))
    assert subtotal(consolidated,'NOP')==subtotal(hotel,'NOP')+subtotal(catering,'NOP')
    assert all(gap==0 for vals in consolidated['split_control'].values() for gap in vals.values())
    assert db.query(JournalEntry).count()==3


def test_excel_summary_first_one_sheet_per_dimension_both_periods(records):
    db,*_=records
    report=deliver(FinancialReportingService(db),as_of_date=date(2026,10,10))
    sheets=workbook_sheets(report)
    assert sheets[0][0]=='Summary'
    assert len(sheets)==4
    assert len(set(name.casefold() for name,_ in sheets))==4
    assert all(len(name)<=31 for name,_ in sheets)
    assert all('MTD Current' in rows[1] and 'YTD Current' in rows[1] for _,rows in sheets)
    with ZipFile(BytesIO(build_xlsx(sheets))) as x:
        root=ET.fromstring(x.read('xl/workbook.xml'))
        assert len(root.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheets'))==4
        assert b'700-0' not in x.read('xl/worksheets/sheet1.xml')


def test_location_scope_and_hidden_details_do_not_change_totals(records):
    db,h,c1,c2,d,accounts=records
    report=deliver(FinancialReportingService(db),as_of_date=date(2026,10,10),report_scope='CONSOLIDATED',location_id=c1.id,include_breakdown=False)
    assert subtotal(report,'NOP')==1490
    assert not report['group_reports']
    with pytest.raises(HTTPException):
        deliver(FinancialReportingService(db),as_of_date=date(2026,10,10),report_scope='HOTEL',location_id=c1.id)


def test_report_setup_mapping_is_explicit_and_totals_ignore_hidden_details(records):
    from app.models.financial_report_setting import FinancialReportSetting
    db,h,c1,c2,d,accounts=records
    db.add(FinancialReportSetting(report_type='PROFIT_LOSS',selected_account_ids=[accounts[0].id],header_only=False))
    db.commit()
    report=deliver(FinancialReportingService(db),as_of_date=date(2026,10,10),report_scope='HOTEL')
    assert subtotal(report,'NOP')==745
    details=[r for r in report['presentation_rows'] if r['kind']=='detail']
    assert {aid for r in details for aid in r['account_ids']}=={accounts[0].id}
    assert next(r for r in report['presentation_rows'] if r['key']=='UNDER_EXPENSE')['periods']['MTD']['current']==15


def test_organization_gap_is_reported_not_redistributed(records):
    db,h,c1,c2,d,accounts=records
    journal=JournalEntry(journal_number='UNASSIGNED',posting_date=date(2026,10,5),status='POSTED',reference_type='MANUAL',reference_id=0)
    journal.lines=[JournalLine(account_id=accounts[0].id,debit=17,credit=0)]
    db.add(journal);db.commit()
    report=deliver(FinancialReportingService(db),as_of_date=date(2026,10,10))
    assert report['split_control']['MTD']['COST_OF_REVENUE']==17
    assert subtotal(report,'NOP')==4453
    assert db.query(JournalEntry).count()==4


def test_exact_summary_order_and_drilldown_includes_zero_accounts(records):
    db,*_=records
    zero=ChartOfAccount(account_number='700-999',account_name='Zero operations expense',account_type='EXPENSE',normal_balance='DEBIT',is_posting=True,financial_statement_group='OPERATING_EXPENSE')
    db.add(zero);db.commit()
    report=deliver(FinancialReportingService(db),as_of_date=date(2026,10,10),report_scope='HOTEL')
    assert [r['key'] for r in report['presentation_rows'] if r['kind']!='detail']==['REVENUE','BEBAN','COST_OF_REVENUE','OPERATING_PAYROLL','OPERATING_EXPENSE','GOI','OVERHEAD_PAYROLL','OVERHEAD_EXPENSE','GOP','UNDER_EXPENSE','NOP']
    row=next(r for r in report['related_accounts'] if r['account_id']==zero.id)
    assert row['periods']['MTD']['current']==0
    assert zero.id in next(r for r in report['presentation_rows'] if r['key']=='OPERATING_EXPENSE')['account_ids']
    assert zero.id in next(r for r in report['presentation_rows'] if r['key']=='NOP')['account_ids']

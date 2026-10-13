import asyncio
from datetime import date
from decimal import Decimal
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile
import pytest
from types import SimpleNamespace
from fastapi import HTTPException
from app.models.chart_of_account import ChartOfAccount
from app.models.fixed_asset import FixedAsset, FixedAssetCategory
from app.models.financial_report_setting import FinancialReportSetting
from app.models.opening_balance import OpeningBalance
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.financial_reporting_service import FinancialReportingService
from app.services.balance_sheet_workbook import workbook_sheets
from app.services.xlsx_export import build_xlsx
from app.api.v1.fixed_assets_core import listing
from app.api.v1.financial_reports import export_comparison
from test_organization_and_asset_delivery import db, ADMIN, scoped_user


def setup_accounts(db):
    db.add_all([ChartOfAccount(id=4,account_number='100-600-104',account_name='Equipment',account_type='ASSET',normal_balance='DEBIT',is_posting=True),ChartOfAccount(id=5,account_number='300-100-100',account_name='Equity',account_type='EQUITY',normal_balance='CREDIT',is_posting=True)])
    db.commit()


def posting(db,number,amount,dept,location=1,unit=1):
    j=JournalEntry(journal_number=number,posting_date=date(2026,10,2),status='POSTED',reference_type='MANUAL',reference_id=0,location_id=location,business_unit_id=unit,department_id=dept)
    j.lines=[JournalLine(account_id=4,debit=amount,credit=0,location_id=location,business_unit_id=unit,department_id=dept),JournalLine(account_id=5,debit=0,credit=amount,location_id=location,business_unit_id=unit,department_id=dept)]
    db.add(j);db.commit()


def test_workbook_has_full_department_detail_and_unassigned_openings(db):
    setup_accounts(db)
    db.add(OpeningBalance(fiscal_year=2026,account_id=1,location_id=1,balance_type='DEBIT',amount=100))
    db.add(FinancialReportSetting(report_type='BALANCE_SHEET',selected_account_ids=[],header_only=True));db.commit()
    posting(db,'HK',10,1);posting(db,'SHARED',20,2);posting(db,'UNASSIGNED',7,None);posting(db,'OUTSIDE',999,3,2,2)
    svc=FinancialReportingService(db);report=svc.build(report_type='BALANCE_SHEET',as_of_date=date(2026,10,13),location_id=1,business_unit_id=1,kap=True)
    before=(db.query(JournalEntry).count(),db.query(OpeningBalance).count())
    sheets=workbook_sheets(svc,report)
    names=[name for name,_ in sheets]
    assert names[:2]==['Summary','Account detail']
    assert {'House Keeping','Shared','Unassigned department','Opening balances'}<=set(names)
    assert 'Operational' not in names
    by_name=dict(sheets)
    assert next(row for row in by_name['Summary'] if row[0]=='Assets')[1]==137
    for name,value in [('House Keeping',10),('Shared',20),('Unassigned department',7)]:
        assert next(row for row in by_name[name] if row[0]=='Equipment')[1]==value
        assert next(row for row in by_name[name] if row[0]=='Prepaid rent')[1]==0
    assert by_name['Opening balances'][2]==['Hotel','Prepaid rent',Decimal(100),0]
    assert next(row for row in by_name['Account detail'] if row[0]=='Prepaid rent')[1]==100
    with ZipFile(BytesIO(build_xlsx(sheets))) as archive:
        workbook=ET.fromstring(archive.read('xl/workbook.xml'))
        ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        assert [sheet.attrib['name'] for sheet in workbook.findall('s:sheets/s:sheet',ns)]==names
        sheet=ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
        assert sheet.find('.//s:c[@r="B3"]/s:v',ns).text=='137.00'
    assert before==(db.query(JournalEntry).count(),db.query(OpeningBalance).count())


def test_export_endpoint_restricts_detail_sheets_to_login_department(db):
    setup_accounts(db);posting(db,'HK',10,1);posting(db,'SHARED',20,2);posting(db,'OUTSIDE',999,3,2,2)
    response=export_comparison(report_type='BALANCE_SHEET',as_of_date=date(2026,10,13),db=db,user=scoped_user(True))
    async def collect():return b''.join([chunk async for chunk in response.body_iterator])
    with ZipFile(BytesIO(asyncio.run(collect()))) as archive:
        xml=archive.read('xl/workbook.xml').decode()
        assert 'House Keeping' in xml
        assert 'Shared' not in xml and 'Opening balances' not in xml and 'Operational' not in xml
        assert all('999' not in archive.read(path).decode() for path in archive.namelist() if path.startswith('xl/worksheets/'))


def test_asset_search_category_dates_pagination_and_access(db):
    setup_accounts(db)
    cat=FixedAssetCategory(code='EQ',name='Equipment',default_useful_life_months=48,asset_account_id=4,accumulated_depreciation_account_id=3,depreciation_expense_account_id=2);db.add(cat);db.flush()
    for ident,location,unit in [(1,1,1),(2,1,1),(3,2,2)]:
        db.add(FixedAsset(asset_number=f'FA-{ident}',asset_name=f'Computer {ident}',asset_category_id=cat.id,acquisition_date=date(2026,ident,1),acquisition_cost=100,net_book_value=100,status='ACTIVE',business_unit_id=unit,location_id=location,asset_account_id=4,created_by_id=1,serial_number=f'SERIAL-{ident}'))
    db.commit()
    user=scoped_user();user.roles[0].permissions=[SimpleNamespace(code="finance.manage")]
    report=listing(search='SERIAL-2',category_id=cat.id,date_from=date(2026,2,1),date_to=date(2026,2,28),db=db,user=user)
    assert report['total_items']==1 and report['items'][0]['asset_number']=='FA-2'
    report=listing(page_size=1,search='computer',db=db,user=user)
    assert report['total_items']==2 and report['total_pages']==2
    with pytest.raises(HTTPException):listing(location_id=2,db=db,user=user)
    with pytest.raises(HTTPException):listing(date_from=date(2026,3,1),date_to=date(2026,1,1),db=db,user=ADMIN)

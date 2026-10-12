from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base
from app.models.business_unit import BusinessUnit
from app.models.location import Location
from app.models.department import Department
from app.models.location_department import LocationDepartment
from app.models.chart_of_account import ChartOfAccount
from app.models.fiscal_period import FiscalPeriod
from app.models.general_ledger import GeneralLedger
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.amortization import Amortization
from app.api.v1 import organization_dimensions as organization, amortizations
from app.schemas.amortization import AmortizationCreate
from app.services.organization_access import resolve_organization_access
from app.services.fixed_asset_service import FixedAssetService
from app.services.financial_reporting_service import FinancialReportingService
from app.services.general_ledger_report import build_ledger_query

ADMIN=SimpleNamespace(id=1,roles=[SimpleNamespace(name='SYSTEM_ADMINISTRATOR',permissions=[])])

@pytest.fixture
def db():
    engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
    session=sessionmaker(bind=engine,expire_on_commit=False)()
    units=[BusinessUnit(id=1,code='H',name='Hotel'),BusinessUnit(id=2,code='C',name='Catering')]
    locs=[Location(id=1,code='H',name='Hotel',business_unit_id=1),Location(id=2,code='C',name='Project',business_unit_id=2)]
    depts=[Department(id=1,code='HK',name='House Keeping',business_unit_id=1),Department(id=2,code='SH',name='Shared'),Department(id=3,code='OPS',name='Operational',business_unit_id=2)]
    session.add_all([*units,*locs,*depts]);session.flush()
    session.add_all([LocationDepartment(location_id=1,department_id=1),LocationDepartment(location_id=1,department_id=2),LocationDepartment(location_id=2,department_id=3)])
    session.add_all([ChartOfAccount(id=1,account_number='100-400-100',account_name='Prepaid rent',account_type='ASSET',normal_balance='DEBIT',is_posting=True),ChartOfAccount(id=2,account_number='700-500-133',account_name='Depreciation',account_type='EXPENSE',normal_balance='DEBIT',is_posting=True),ChartOfAccount(id=3,account_number='100-800-103',account_name='Accumulated depreciation',account_type='ASSET',normal_balance='CREDIT',is_posting=True)])
    session.add(FiscalPeriod(fiscal_year=2026,fiscal_month=10,period_name='October',start_date=date(2026,10,1),end_date=date(2026,10,31),is_open=True,is_closed=False,allow_backdated_entries=True))
    session.commit();yield session
    session.close();engine.dispose()


def scoped_user(department_role=False):
    return SimpleNamespace(id=2,roles=[SimpleNamespace(name='DEPARTMENT' if department_role else 'FINANCE',permissions=[])],default_location_id=1,location_id=1,default_department_id=1,department_id=1)


def test_organization_lookup_cannot_escape_assignment_by_flag_or_direct_id(db):
    user=scoped_user()
    assert [r['id'] for r in organization.list_locations(assigned_only=False,db=db,user=user)]==[1]
    assert [r['id'] for r in organization.list_business_units(db=db,user=user)]==[1]
    assert {r['id'] for r in organization.list_departments(db=db,user=user)}=={1,2}
    assert [r['id'] for r in organization.list_departments(db=db,user=scoped_user(True))]==[1]
    for operation in [lambda:organization.get_location(2,db,user),lambda:organization.get_department(3,db,user),lambda:organization.list_departments(location_id=2,db=db,user=user),lambda:resolve_organization_access(db,user,business_unit_id=2)]:
        with pytest.raises(HTTPException) as error:operation()
        assert error.value.status_code==404
    assert len(organization.list_locations(db=db,user=ADMIN))==2


def test_scoped_unit_report_includes_legacy_posting_without_unit_id(db):
    j=JournalEntry(journal_number='LEGACY',posting_date=date(2026,10,1),status='POSTED',reference_type='MANUAL',reference_id=0,location_id=1)
    j.lines=[JournalLine(account_id=2,debit=7,credit=0,location_id=1)]
    db.add(j);db.commit()
    result=FinancialReportingService(db).build(report_type='PROFIT_LOSS',as_of_date=date(2026,10,31),business_unit_id=1,location_id=1)
    assert result['section_totals']['EXPENSES']['MTD']['current']==7


def test_prepaid_amortization_posts_expense_and_direct_asset_credit_with_gl(db):
    data=AmortizationCreate(name='Prepaid rent',start_date=date(2026,10,1),original_cost=120,useful_life_months=12,business_unit_id=1,location_id=1,department_id=1,asset_account_id=1,accumulated_amortization_account_id=1,amortization_expense_account_id=2)
    created=amortizations.create_amortization(data,db,ADMIN)
    result=amortizations.post_next_amortization(created['id'],db,ADMIN)
    assert result['posted_amount']==10
    lines=db.query(GeneralLedger).order_by(GeneralLedger.id).all()
    assert [(r.account_id,r.debit,r.credit) for r in lines]==[(2,Decimal(10),Decimal(0)),(1,Decimal(0),Decimal(10))]
    assert len(build_ledger_query(db,location_id=1,department_id=1).all())==2
    assert db.query(Amortization).one().net_book_value==110
    assert db.query(JournalEntry).one().posted_at is not None


def test_closed_period_rolls_back_auto_asset_journal_and_gl(db):
    asset=SimpleNamespace(business_unit_id=1,location_id=1,department_id=1)
    period=db.query(FiscalPeriod).one();period.is_open=False;period.is_closed=True;db.commit()
    with pytest.raises(HTTPException):
        FixedAssetService(db)._journal(date(2026,10,31),'FIXED_ASSET_DEPRECIATION',1,'FADR-1',[(2,Decimal(10),Decimal(0)),(3,Decimal(0),Decimal(10))],asset,ADMIN)
    db.rollback()
    assert db.query(JournalEntry).count()==db.query(GeneralLedger).count()==0


def test_generated_depreciation_preserves_each_line_department_in_gl(db):
    header=SimpleNamespace(business_unit_id=1,location_id=1,department_id=None)
    first=SimpleNamespace(business_unit_id=1,location_id=1,department_id=1)
    second=SimpleNamespace(business_unit_id=1,location_id=1,department_id=2)
    entry=FixedAssetService(db)._journal(date(2026,10,31),'FIXED_ASSET_DEPRECIATION',1,'FADR-1',[(2,Decimal(10),Decimal(0),first),(3,Decimal(0),Decimal(10),first),(2,Decimal(20),Decimal(0),second),(3,Decimal(0),Decimal(20),second)],header,ADMIN)
    db.commit()
    assert entry.department_id is None
    assert [r.department_id for r in db.query(JournalLine).order_by(JournalLine.id)]==[1,1,2,2]
    assert [r.debit for r in build_ledger_query(db,department_id=2).all()]==[Decimal(20),Decimal(0)]
    assert db.query(GeneralLedger).count()==4
    assert sum(r.debit-r.credit for r in db.query(GeneralLedger))==0


def test_opening_balance_excel_preserves_entered_columns_and_login_scope(db):
    import asyncio
    from io import BytesIO
    from zipfile import ZipFile
    from xml.etree import ElementTree as ET
    from app.api.v1.opening_balances import export_excel
    from app.models.opening_balance import OpeningBalance
    db.add_all([
        OpeningBalance(fiscal_year=2026,account_id=1,location_id=1,balance_type='DEBIT',amount=123.45),
        OpeningBalance(fiscal_year=2026,account_id=1,location_id=1,balance_type='CREDIT',amount=20),
        OpeningBalance(fiscal_year=2026,account_id=1,location_id=2,balance_type='DEBIT',amount=999),
    ])
    db.commit()
    before=(db.query(OpeningBalance).count(),db.query(JournalEntry).count(),db.query(GeneralLedger).count())
    response=export_excel(fiscal_year=2026,location_id=None,db=db,user=scoped_user())
    async def collect():
        return b''.join([chunk async for chunk in response.body_iterator])
    with ZipFile(BytesIO(asyncio.run(collect()))) as archive:
        sheet=ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
        ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        numbers={cell.attrib['r']:cell.find('s:v',ns).text for cell in sheet.findall('.//s:c[@t="n"]',ns)}
        assert numbers['E3']=='123.45'
        assert numbers['F3']=='20.00'
        assert '999.00' not in numbers.values()
        assert numbers['E4']=='0'
    assert response.headers['content-disposition']=='attachment; filename="opening-balances-2026.xlsx"'
    assert before==(db.query(OpeningBalance).count(),db.query(JournalEntry).count(),db.query(GeneralLedger).count())
    with pytest.raises(HTTPException):
        export_excel(fiscal_year=2026,location_id=2,db=db,user=scoped_user())

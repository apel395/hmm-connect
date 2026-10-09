from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base
from app.models.business_unit import BusinessUnit
from app.models.location import Location
from app.models.department import Department
from app.models.location_department import LocationDepartment
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.budget import Budget, BudgetLine
from app.services.financial_reporting_service import FinancialReportingService
from app.services.general_ledger_report import build_ledger_query

@pytest.fixture
def data():
    engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
    db=sessionmaker(bind=engine,expire_on_commit=False)()
    unit=BusinessUnit(code='H',name='Hotel');db.add(unit);db.flush()
    loc=Location(code='H',name='Hotel',business_unit_id=unit.id)
    departments=[Department(code='HK',name='House Keeping',business_unit_id=unit.id),Department(code='FO',name='Front Office',business_unit_id=unit.id),Department(code='OLD',name='Former Department',business_unit_id=unit.id,is_active=False)]
    account=ChartOfAccount(account_number='700-500-119',account_name='Supplies',account_type='EXPENSE',normal_balance='DEBIT',financial_statement_group='OPERATING_EXPENSE',is_active=True,is_posting=True)
    db.add_all([loc,account,*departments]);db.flush()
    db.add_all([LocationDepartment(location_id=loc.id,department_id=d.id) for d in departments[:2]])
    for idx,(dept,amount) in enumerate([(departments[0].id,100),(departments[1].id,200),(None,50),(departments[2].id,25)]):
        j=JournalEntry(journal_number=f'DEPT-{idx}',posting_date=date(2026,10,5),status='POSTED',reference_type='MANUAL',reference_id=0,location_id=loc.id,business_unit_id=unit.id,department_id=dept)
        j.lines=[JournalLine(account_id=account.id,debit=amount,credit=0,location_id=loc.id,business_unit_id=unit.id)]
        db.add(j)
    budget=Budget(name='Hotel budget',budget_number='B-H',fiscal_year=2026,date_from=date(2026,1,1),date_to=date(2026,12,31),status='APPROVED');db.add(budget);db.flush()
    db.add_all([BudgetLine(budget_id=budget.id,month=10,account_id=account.id,budget_amount=80,department_id=departments[0].id,location_id=loc.id,business_unit_id=unit.id),BudgetLine(budget_id=budget.id,month=10,account_id=account.id,budget_amount=20,location_id=loc.id,business_unit_id=unit.id)])
    db.commit();yield db,loc,unit,departments
    db.close();engine.dispose()

def test_full_department_tables_reconcile_and_keep_unassigned_and_inactive(data):
    db,loc,unit,depts=data
    service=FinancialReportingService(db)
    parent=service.build(report_type='PROFIT_LOSS',as_of_date=date(2026,10,10),location_id=loc.id)
    tables=service.department_reports(parent)
    assert {t['department_name'] for t in tables}=={'House Keeping','Front Office','Former Department','Unassigned department'}
    for p in ['MTD','YTD']:
        assert sum(t['section_totals']['EXPENSES'][p]['current'] for t in tables)==parent['section_totals']['EXPENSES'][p]['current']==Decimal(375)
        assert sum(t['section_totals']['EXPENSES'][p]['budget'] or 0 for t in tables)==parent['section_totals']['EXPENSES'][p]['budget']==Decimal(100)
    unassigned=next(t for t in tables if t['department_id'] is None)
    assert unassigned['rows'][0]['periods']['MTD']['current']==Decimal(50)
    assert unassigned['rows'][0]['periods']['MTD']['budget']==Decimal(20)
    assert db.query(JournalEntry).count()==4

def test_selected_department_returns_only_its_statement(data):
    db,loc,unit,depts=data;service=FinancialReportingService(db)
    parent=service.build(report_type='PROFIT_LOSS',as_of_date=date(2026,10,10),location_id=loc.id,department_id=depts[1].id)
    tables=service.department_reports(parent)
    assert len(tables)==1 and tables[0]['department_name']=='Front Office'
    assert tables[0]['section_totals']['EXPENSES']['MTD']['current']==Decimal(200)


def test_unassigned_drilldown_filters_null_department_and_uses_header_fallback(data):
    db,loc,unit,depts=data
    unassigned=build_ledger_query(db,department_id=0,location_id=loc.id).all()
    assert len(unassigned)==1 and unassigned[0].debit==Decimal(50)
    assigned=build_ledger_query(db,department_id=depts[0].id,location_id=loc.id).all()
    assert len(assigned)==1 and assigned[0].debit==Decimal(100)

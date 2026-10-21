from datetime import date
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
import pytest
from openpyxl import load_workbook
from app.models.chart_of_account import ChartOfAccount
from app.models.department import Department
from app.models.location_department import LocationDepartment
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.general_ledger import GeneralLedger
from app.services.profit_loss_relevance import related
from app.services.profit_loss_delivery import category, deliver, workbook_sheets
from app.services.financial_reporting_service import FinancialReportingService
from app.services.xlsx_export import build_xlsx
from test_organization_and_asset_delivery import db

NAMES={'AG':'Admin and General','ACC':'Accounting','HR':'Human Resources','BOD':'Board of Directur'}


def account(code,name='Expense',kind='EXPENSE'):
    return SimpleNamespace(id=1,account_number=code,account_name=name,account_type=kind,financial_statement_group='OPERATING_EXPENSE')


def scope(dept,unit='Hotel'):
    return {'scope_labels':{'business_unit_id':unit,'department_id':NAMES[dept]}}


@pytest.mark.parametrize('code,expected',[
    ('700-500-110',{'HR'}),('700-500-128',{'HR'}),('700-500-129',{'HR'}),
    ('700-500-122',{'ACC'}),('700-500-131',{'ACC'}),('700-500-140',{'AG'}),
    ('750-100-104',{'BOD'}),('750-100-100',{'AG'}),
    ('700-500-103',set(NAMES)),('600-100-101',set(NAMES)),
    ('700-500-124',set()),('700-500-120',set()),
])
def test_unused_accounts_are_related_to_support_department_purpose(code,expected):
    a=account(code)
    assert {d for d in NAMES if related(a,scope(d),{},set())}==expected
    # Actual, offsetting posted activity and approved budget always survive.
    for dept in NAMES:
        assert related(a,scope(dept),{}, {1})
        assert related(a,scope(dept),{'MTD':{'budget':{1:Decimal('12')}}},set())
    # This policy never restricts Catering's account catalogue.
    assert related(a,scope('ACC','Project Catering'),{},set())


def test_bod_management_payroll_is_overhead_but_owner_cost_is_below_gop():
    assert category(account('600-100-100','Gaji'),{},scope('BOD'))=='OVERHEAD_PAYROLL'
    assert category(account('700-500-100','Business travel'),{},scope('BOD'))=='OVERHEAD_EXPENSE'
    assert category(account('750-100-104','Biaya Operasional Direksi'),{},scope('BOD'))=='UNDER_EXPENSE'
    assert category(account('700-OTHER','BOD - Owner Expenses'),{},scope('BOD'))=='UNDER_EXPENSE'
    assert category(account('750-100-104'),{},scope('BOD','Project Catering'))=='OVERHEAD_EXPENSE'
    # Explicit finance setup still takes precedence over automatic defaults.
    assert category(account('750-100-104'),{1:'OVERHEAD_EXPENSE'},scope('BOD'))=='OVERHEAD_EXPENSE'


def test_four_department_schedules_sum_once_and_keep_wrong_postings_visible(db):
    depts={}
    for offset,(key,name) in enumerate(NAMES.items(),10):
        depts[key]=Department(id=offset,code=key,name=name,business_unit_id=1)
        db.add(depts[key]);db.add(LocationDepartment(location_id=1,department_id=offset))
    specs=[(20,'600-100-100','Gaji'),(21,'700-500-110','Pelatihan / Training'),
        (22,'700-500-122','Biaya Admin Bank'),(23,'700-500-103','Alat Tulis Kantor (ATK)'),
        (24,'750-100-104','Biaya Operasional Direksi'),(25,'700-500-124','Perbaikan Gedung'),
        (26,'700-500-128','Recruitment/Medical check up/Housing')]
    for aid,code,name in specs:
        db.add(ChartOfAccount(id=aid,account_number=code,account_name=name,account_type='EXPENSE',normal_balance='DEBIT',is_posting=True,financial_statement_group='OPERATING_EXPENSE'))
    db.flush()
    for n,(dept,aid,amount) in enumerate([('AG',23,10),('ACC',22,20),('HR',21,30),('BOD',24,40),('BOD',20,50),('HR',25,7),('ACC',21,2),('ACC',21,-2)]):
        j=JournalEntry(journal_number=f'SUPPORT-{n}',posting_date=date(2026,1,5),status='POSTED',reference_type='MANUAL',reference_id=0,business_unit_id=1,location_id=1,department_id=depts[dept].id)
        j.lines=[JournalLine(line_number=1,account_id=aid,debit=max(amount,0),credit=max(-amount,0)),JournalLine(line_number=2,account_id=1,debit=max(-amount,0),credit=max(amount,0))]
        db.add(j)
    db.commit()
    before=(db.query(JournalEntry).count(),db.query(JournalLine).count(),db.query(GeneralLedger).count())
    report=deliver(FinancialReportingService(db),as_of_date=date(2026,1,31),report_scope='HOTEL')
    groups={g['department_name']:g for g in report['group_reports']}
    acct={r['account_code'] for r in groups['Accounting']['related_accounts']}
    assert '700-500-122' in acct and '700-500-110' in acct # real offsetting postings
    assert '700-500-128' not in acct
    hr=groups['Human Resources'];hr_codes={r['account_code'] for r in hr['related_accounts']}
    assert '700-500-128' in hr_codes and '700-500-124' in hr_codes # real cost retained
    assert '700-500-122' not in hr_codes
    def total(r,key):return next(x['periods']['YTD']['current'] for x in r['presentation_rows'] if x['key']==key)
    assert total(report,'GOP')==-117
    assert total(report,'UNDER_EXPENSE')==40
    assert total(report,'NOP')==-157
    for key in ('OVERHEAD_PAYROLL','OVERHEAD_EXPENSE','GOP','UNDER_EXPENSE','NOP'):
        assert total(report,key)==sum(total(g,key) for g in report['group_reports'] if not g.get('is_department_rollup'))
    assert all(v == 0 for period in report['split_control'].values() for v in period.values())
    assert groups['Admin and General']['is_department_rollup']
    assert total(groups['Admin and General'], 'NOP') == total(groups['Accounting'], 'NOP') + total(hr, 'NOP')
    wb=load_workbook(BytesIO(build_xlsx(workbook_sheets(report))))
    accounting=wb['Hotel · Accounting'];hr_sheet=wb['Hotel · Human Resources']
    def labels(sheet):return {str(row[0].value or '').strip() for row in sheet}
    assert 'Recruitment/Medical check up/Housing' not in labels(accounting)
    assert 'Recruitment/Medical check up/Housing' in labels(hr_sheet) # relevant zero stays
    assert 'Biaya Admin Bank' not in labels(hr_sheet)
    assert 'Perbaikan Gedung' in labels(hr_sheet) # actual unexpected cost stays
    assert 'Total Revenue' not in labels(accounting) and 'TOTAL DEPARTMENT EXPENSES' in labels(accounting)
    assert next(row[1].value for row in accounting if row[0].value=='TOTAL DEPARTMENT EXPENSES').startswith('=')
    cached=load_workbook(BytesIO(build_xlsx(workbook_sheets(report))),data_only=True)
    for name,expected in [('Admin and General',67),('Accounting',30),('Human Resources',37),('Board of Directur',90)]:
        sheet=cached[f'Hotel · {name}'[:31]]
        assert next(row[1].value for row in sheet if row[0].value=='TOTAL DEPARTMENT EXPENSES')==expected
    summary=cached['Summary']
    assert [r[1].value for r in summary if r[0].value=='Administration & General']==[0,67]
    assert next(r[1].value for r in summary if r[0].value=='Board of Directors')==50
    assert before==(db.query(JournalEntry).count(),db.query(JournalLine).count(),db.query(GeneralLedger).count())

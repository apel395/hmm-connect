from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from io import BytesIO
from openpyxl import load_workbook

from app.models.department import Department
from app.models.location_department import LocationDepartment
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.budget import Budget, BudgetLine
from app.services.financial_reporting_service import FinancialReportingService
from app.services.profit_loss_delivery import deliver, workbook_sheets
from app.services.xlsx_export import build_xlsx
from app.api.v1.financial_reports import comparison
from test_organization_and_asset_delivery import db


def setup(db):
    for did, code, name in [(10,'AG','Admin and General'),(12,'HR','Human Resources'),(13,'ACC','Accounting')]:
        db.add(Department(id=did, code=code, name=name, business_unit_id=1))
        db.add(LocationDepartment(location_id=1, department_id=did))
    db.add(ChartOfAccount(id=20,account_number='600-100-100',account_name='Gaji',account_type='EXPENSE',normal_balance='DEBIT',is_posting=True,financial_statement_group='OPERATING_EXPENSE'))
    db.flush()
    n=0
    for when, amounts in [(date(2026,1,10),[100,20,10]),(date(2025,12,10),[80,15,8]),(date(2025,1,10),[60,10,6])]:
        for did, amount in zip((10,12,13),amounts):
            n+=1
            entry=JournalEntry(journal_number=f'AG-{n}',posting_date=when,status='POSTED',reference_type='MANUAL',reference_id=0,location_id=1,business_unit_id=1,department_id=did)
            entry.lines=[JournalLine(line_number=1,account_id=20,debit=amount,credit=0),JournalLine(line_number=2,account_id=1,debit=0,credit=amount)]
            db.add(entry)
    budget=Budget(budget_number='AG-BUDGET',name='Hotel January',fiscal_year=2026,date_from=date(2026,1,1),date_to=date(2026,12,31),status='APPROVED')
    db.add(budget);db.flush()
    for did, value in [(10,120),(12,25),(13,12)]:
        db.add(BudgetLine(budget_id=budget.id,account_id=20,department_id=did,business_unit_id=1,location_id=1,month=1,budget_amount=value))
    db.commit()


def row(report, key='OVERHEAD_PAYROLL', period='MTD'):
    return next(r['periods'][period] for r in report['presentation_rows'] if r['key']==key)


def report(db, department_id=None):
    return deliver(FinancialReportingService(db),as_of_date=date(2026,1,31),report_scope='HOTEL',location_id=1,department_id=department_id)


def test_accounting_and_hr_roll_up_once_in_all_comparisons_and_workbook(db):
    setup(db)
    before=[(l.id,l.department_id,l.debit,l.credit) for l in db.query(JournalLine).order_by(JournalLine.id)]
    root=report(db)
    accounting, hr, ag=report(db,13),report(db,12),report(db,10)
    assert row(accounting)==dict(current=Decimal(110),budget=Decimal(132),last_month=Decimal(88),last_year=Decimal(66),variance=Decimal(-22))
    assert row(hr)['current']==20
    for period in ('MTD','YTD'):
        for metric in ('current','budget','last_month','last_year','variance'):
            assert row(ag,period=period)[metric]==row(accounting,period=period)[metric]+row(hr,period=period)[metric]
    assert row(ag,'NOP')['current']==row(root,'NOP')['current']==-130
    assert ag['is_department_rollup'] and not accounting['is_department_rollup']
    assert ag['metadata']['source_department_ids']==[10,13,12]
    assert accounting['metadata']['source_department_ids']==[10,13]
    assert accounting['related_accounts'][0]['source_departments']==[{'id':10,'name':'Admin and General'},{'id':13,'name':'Accounting'}]
    assert all(v==0 for period in root['split_control'].values() for v in period.values())
    cached=load_workbook(BytesIO(build_xlsx(workbook_sheets(root))),data_only=True)
    for title, expected in [('Hotel · Admin and General',130),('Hotel · Accounting',110),('Hotel · Human Resources',20)]:
        sheet=cached[title]
        assert next(r[1].value for r in sheet if r[0].value=='TOTAL DEPARTMENT EXPENSES')==expected
    summary=cached['Summary']
    assert next(r[1].value for r in summary if r[0].value=='GROSS OPERATING PROFIT')==-130
    assert before==[(l.id,l.department_id,l.debit,l.credit) for l in db.query(JournalLine).order_by(JournalLine.id)]


def test_department_login_cannot_expand_into_another_recorded_department(db):
    setup(db)
    for did, expected in [(13,10),(12,20),(10,100)]:
        user=SimpleNamespace(id=9,roles=[SimpleNamespace(name='DEPARTMENT',permissions=[])],default_location_id=1,default_department_id=did)
        result=comparison(report_type='PROFIT_LOSS',as_of_date=date(2026,1,31),location_id=1,business_unit_id=1,department_id=did,report_scope='HOTEL',db=db,user=user)
        assert Decimal(row(result)['current'])==expected
        assert result['metadata']['source_department_ids']==[did]
        assert not result['is_department_rollup']


def test_rollup_never_applies_to_balance_sheet_or_missing_accounting_department(db):
    setup(db)
    service=FinancialReportingService(db)
    balance=service.build(report_type='BALANCE_SHEET',as_of_date=date(2026,1,31),location_id=1,business_unit_id=1,department_id=10)
    assert balance['section_totals']['ASSETS']['MTD']['current']==-100
    db.query(LocationDepartment).filter(LocationDepartment.department_id==13).delete()
    # Missing/ambiguous configurations are not silently allocated.
    db.get(Department,13).name='Finance Review';db.commit()
    result=report(db,10)
    assert row(result)['current']==100
    assert not result['is_department_rollup']


def test_verified_import_categories_survive_merged_department_scope_and_cached_root(db):
    from app.models.import_batch import ImportBatch, ImportRow
    from app.services.hotel_pl_attribution import SOURCE_HASH
    setup(db)
    db.add(ChartOfAccount(id=21,account_number='700-500-122',account_name='Biaya Admin Bank',account_type='EXPENSE',normal_balance='DEBIT',is_posting=True,financial_statement_group='OPERATING_EXPENSE'))
    batch=ImportBatch(id=1,batch_number='ROLLUP-JAN',source='ACCOUNTING_IMPORT',batch_name='January',import_type='JOURNAL',status='IMPORTED')
    db.add(batch);db.flush()
    j=JournalEntry(journal_number='AG-LEGACY',posting_date=date(2026,1,5),status='POSTED',reference_type='MANUAL',reference_id=0,source_type='JOURNAL_IMPORT',external_reference='HOTEL-JAN2026-REG-TEST',import_batch_id=batch.id,business_unit_id=1,location_id=1,department_id=10)
    j.lines=[JournalLine(line_number=1,account_id=21,debit=3,credit=0),JournalLine(line_number=2,account_id=1,debit=0,credit=3)]
    db.add(j);db.flush()
    data=dict(account_id=21,department_id=10,legacy_code='602070',debit='3',credit='0')
    db.add(ImportRow(id=1,import_batch_id=batch.id,row_number=1,document_type='JOURNAL',raw_data_json={**data,'source_sha256':SOURCE_HASH},normalized_data_json=data,status='IMPORTED',entity_type='JOURNAL_ENTRY',entity_id=j.id))
    db.commit()
    service=FinancialReportingService(db)
    root=deliver(service,as_of_date=date(2026,1,31),report_scope='HOTEL',location_id=1)
    accounting=deliver(service,as_of_date=date(2026,1,31),report_scope='HOTEL',location_id=1,department_id=13)
    ag=deliver(service,as_of_date=date(2026,1,31),report_scope='HOTEL',location_id=1,department_id=10)
    for result in (root,accounting,ag):
        assert row(result,'UNDER_EXPENSE')['current']==3
    assert row(accounting,'GOP')['current']==-110
    assert row(accounting,'NOP')['current']==-113
    assert row(ag,'NOP')['current']==row(root,'NOP')['current']==-133
    assert accounting['metadata']['hotel_attribution']['verified_legacy_lines']==1


def test_catering_department_names_do_not_trigger_hotel_aggregation(db):
    db.add(ChartOfAccount(id=20,account_number='600-100-100',account_name='Gaji',account_type='EXPENSE',normal_balance='DEBIT',is_posting=True,financial_statement_group='OPERATING_EXPENSE'))
    for did, code, name in [(30,'C-AG','Admin and General'),(31,'C-ACC','Accounting')]:
        db.add(Department(id=did,code=code,name=name,business_unit_id=2))
        db.add(LocationDepartment(location_id=2,department_id=did))
    db.flush()
    for did, amount in [(30,50),(31,7)]:
        j=JournalEntry(journal_number=f'CAT-{did}',posting_date=date(2026,1,5),status='POSTED',reference_type='MANUAL',reference_id=0,business_unit_id=2,location_id=2,department_id=did)
        j.lines=[JournalLine(line_number=1,account_id=20,debit=amount,credit=0),JournalLine(line_number=2,account_id=1,debit=0,credit=amount)]
        db.add(j)
    db.commit()
    for did, expected in [(30,50),(31,7)]:
        result=deliver(FinancialReportingService(db),as_of_date=date(2026,1,31),report_scope='CATERING',location_id=2,department_id=did)
        assert row(result)['current']==expected
        assert not result['is_department_rollup']


def test_subtotal_retains_zero_accounts_for_both_accounting_and_hr(db):
    setup(db)
    db.add_all([ChartOfAccount(id=21,account_number='700-500-122',account_name='Biaya Admin Bank',account_type='EXPENSE',normal_balance='DEBIT',is_posting=True,financial_statement_group='OPERATING_EXPENSE'),ChartOfAccount(id=22,account_number='700-500-128',account_name='Recruitment',account_type='EXPENSE',normal_balance='DEBIT',is_posting=True,financial_statement_group='OPERATING_EXPENSE')])
    db.commit()
    ag=report(db,10)
    assert {21,22}.issubset({a['account_id'] for a in ag['related_accounts']})
    assert 22 not in {a['account_id'] for a in report(db,13)['related_accounts']}
    assert 21 not in {a['account_id'] for a in report(db,12)['related_accounts']}

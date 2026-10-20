"""Verified import semantics split shared COA amounts without accounting writes."""
from datetime import date
import pytest
from decimal import Decimal
from app.models import Base
from app.models.chart_of_account import ChartOfAccount
from app.models.department import Department
from app.models.import_batch import ImportBatch, ImportRow
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.financial_reporting_service import FinancialReportingService
from app.services.profit_loss_delivery import deliver
from app.services.profit_loss_template import summary_schedule, detail_rows
from app.services.hotel_pl_attribution import SOURCE_HASH
from test_organization_and_asset_delivery import db


def fixture(db):
    db.add_all([Department(id=10,code='BOD',name='Board of Directur',business_unit_id=1),
        Department(id=11,code='FB',name='Food and Beverage',business_unit_id=1)])
    definitions=[(20,'500-100-101','Beban Pokok Langsung','EXPENSE','COST_OF_REVENUE'),
        (21,'600-100-107','Makan Karyawan','EXPENSE','OPERATING_EXPENSE'),
        (22,'750-100-104','Biaya Operasional Direksi','EXPENSE','OPERATING_EXPENSE'),
        (23,'700-500-122','Biaya Admin Bank','EXPENSE','OPERATING_EXPENSE'),
        (24,'400-100-101','Food & Beverage','REVENUE','OPERATING_REVENUE'),
        (25,'760-100-100','Pendapatan Bunga Bank','REVENUE','OTHER_REVENUE')]
    for aid,code,name,kind,group in definitions:
        db.add(ChartOfAccount(id=aid,account_number=code,account_name=name,account_type=kind,normal_balance='CREDIT' if kind=='REVENUE' else 'DEBIT',is_posting=True,financial_statement_group=group))
    db.add(ImportBatch(id=1,batch_number='JAN',source='ACCOUNTING_IMPORT',batch_name='January',import_type='JOURNAL',status='IMPORTED'))
    db.flush()
    specs=[('401101',20,100,0,11),('522023',20,5,0,11),('591007',22,30,0,10),
           ('591050',21,7,0,10),('602070',23,2,0,None),('303001',24,0,1000,11),
           ('303002',24,0,200,11),('601001',25,0,10,None)]
    j=JournalEntry(id=100,journal_number='JAN-1',posting_date=date(2026,1,5),status='POSTED',reference_type='MANUAL',reference_id=0,source_type='JOURNAL_IMPORT',external_reference='HOTEL-JAN2026-REG-1',import_batch_id=1,business_unit_id=1,location_id=1)
    for number,(legacy,aid,debit,credit,dept) in enumerate(specs,1):
        j.lines.append(JournalLine(line_number=number,account_id=aid,debit=debit,credit=credit,business_unit_id=1,location_id=1,department_id=dept))
        n=dict(account_id=aid,department_id=dept,legacy_code=legacy,debit=str(debit),credit=str(credit))
        raw={**n,'source_sha256':SOURCE_HASH}
        db.add(ImportRow(id=number,import_batch_id=1,row_number=number,document_type='JOURNAL',raw_data_json=raw,normalized_data_json=n,status='IMPORTED',entity_type='JOURNAL_ENTRY',entity_id=100))
    db.add(j);db.commit()
    return j


def amounts(report,key):return next(r for r in report['presentation_rows'] if r['key']==key)['periods']['YTD']['current']


def test_nop_subtracts_expenses_net_of_income_and_reconciles_to_ledger(db):
    j=fixture(db)
    report=deliver(FinancialReportingService(db),as_of_date=date(2026,1,31),report_scope='HOTEL')
    assert amounts(report,'REVENUE')==1200
    assert amounts(report,'COST_OF_REVENUE')==100
    assert amounts(report,'OPERATING_EXPENSE')==5
    assert amounts(report,'UNDER_EXPENSE')==39
    assert amounts(report,'GOP')==1095
    assert amounts(report,'NONOPERATING_INCOME')==10
    assert amounts(report,'NOP')==1066
    assert amounts(report,'TOTAL_DEDUCTIONS')==29
    bridge=report['metadata']['nop_reconciliation']
    assert bridge['ledger_net']['YTD']['current']==1066
    assert bridge['report_net']['YTD']['current']==1066
    interest=next(a for a in report['related_accounts'] if a['account_name']=='Jasa Giro')
    assert interest['account_id']==25 and interest['periods']['YTD']['current']==10
    assert (j.lines[-1].account_id,j.lines[-1].debit,j.lines[-1].credit)==(25,0,10)
    assert report['metadata']['hotel_attribution']['verified_legacy_lines']==8
    cost=next(r for r in report['presentation_rows'] if r['key']=='COST_OF_REVENUE')
    selected=[a for a in report['related_accounts'] if a['presentation_key'] in cost['member_keys']]
    assert sum(a['periods']['YTD']['current'] for a in selected)==100
    assert any(a['account_id']==20 and a['account_name']=='Food Cost' for a in selected)
    fb=next(g for g in report['group_reports'] if g['department_name']=='Food and Beverage')
    rows=detail_rows(fb,'FB','2026-01-31')
    assert next(r[1] for r in rows if r and r[0].strip()=='Food Cost')==100
    assert next(r[1] for r in rows if r and r[0].strip()=='Food Revenue')==1000
    assert next(r[1] for r in rows if r and r[0].strip()=='Beverage Revenue')==200
    assert sum(amounts(g,'NOP') for g in report['group_reports'])==1066
    rows=summary_schedule(report,'Hotel',report['group_reports'],'2026-01-31')
    assert next(r[1] for r in rows if r and r[0]=='GROSS OPERATING PROFIT')==1095
    assert next(r[1] for r in rows if r and r[0]=='NETT OPERATING PROFIT')==1066
    assert len(j.lines)==8 and j.lines[0].account_id==20 and j.lines[0].debit==100


def test_edited_or_ambiguous_or_wrong_source_evidence_not_reused(db):
    j=fixture(db)
    j.lines[0].debit=101
    raw=db.get(ImportRow,2).raw_data_json.copy();raw['source_sha256']='different'
    db.get(ImportRow,2).raw_data_json=raw
    db.commit()
    r=deliver(FinancialReportingService(db),as_of_date=date(2026,1,31),report_scope='HOTEL')
    assert amounts(r,'COST_OF_REVENUE')==106
    assert amounts(r,'OPERATING_EXPENSE')==0
    assert amounts(r,'NOP')==1065
    assert not any(a.get('legacy_codes')==['401101'] for a in r['related_accounts'])


def test_draft_and_catering_never_use_hotel_evidence(db):
    j=fixture(db);j.status='DRAFT';db.commit()
    r=deliver(FinancialReportingService(db),as_of_date=date(2026,1,31),report_scope='HOTEL')
    assert amounts(r,'NOP')==0
    assert r['metadata']['hotel_attribution']['verified_legacy_lines']==0
    j.status='POSTED';j.business_unit_id=2;j.location_id=2
    for line in j.lines:line.business_unit_id=2;line.location_id=2;line.department_id=None
    db.commit()
    r=deliver(FinancialReportingService(db),as_of_date=date(2026,1,31),report_scope='CATERING')
    assert amounts(r,'COST_OF_REVENUE')==105
    assert r['metadata']['hotel_attribution']['verified_legacy_lines']==0


def test_identical_shared_coa_amounts_use_verified_line_order(db):
    j=fixture(db)
    j.lines[0].debit=5
    for name in ('raw_data_json','normalized_data_json'):
        data=getattr(db.get(ImportRow,1),name).copy();data['debit']='5'
        setattr(db.get(ImportRow,1),name,data)
    db.commit()
    r=deliver(FinancialReportingService(db),as_of_date=date(2026,1,31),report_scope='HOTEL')
    assert amounts(r,'COST_OF_REVENUE')==5
    assert amounts(r,'OPERATING_EXPENSE')==5
    assert amounts(r,'NOP')==1161


def test_owner_loan_asset_credit_is_never_reintroduced_as_expense(db):
    j=fixture(db)
    j.lines.append(JournalLine(line_number=9,account_id=1,debit=0,credit=25,business_unit_id=1,location_id=1,department_id=10))
    n=dict(account_id=1,department_id=10,legacy_code='591007',debit='0',credit='25')
    db.add(ImportRow(id=9,import_batch_id=1,row_number=9,document_type='JOURNAL',raw_data_json={**n,'source_sha256':SOURCE_HASH},normalized_data_json=n,status='IMPORTED',entity_type='JOURNAL_ENTRY',entity_id=100))
    db.commit()
    r=deliver(FinancialReportingService(db),as_of_date=date(2026,1,31),report_scope='HOTEL')
    assert amounts(r,'UNDER_EXPENSE')==39
    assert amounts(r,'NOP')==1066
    assert not any(a['account_id']==1 for a in r['related_accounts'])


@pytest.mark.parametrize('legacy,department_name,target,payroll', [
    ('512050','Front Office','OPERATING_EXPENSE','OPERATING_PAYROLL'),
    ('514050','House Keeping','OPERATING_EXPENSE','OPERATING_PAYROLL'),
    ('522050','Food and Beverage','OPERATING_EXPENSE','OPERATING_PAYROLL'),
    ('532050','Food and Beverage','OPERATING_EXPENSE','OPERATING_PAYROLL'),
    ('542050','Sales and Marketing','OVERHEAD_EXPENSE','OVERHEAD_PAYROLL'),
    ('544050','Admin and General','OVERHEAD_EXPENSE','OVERHEAD_PAYROLL'),
    ('546022','Human Resources','OVERHEAD_EXPENSE','OVERHEAD_PAYROLL'),
    ('548049','Pomec','OVERHEAD_EXPENSE','OVERHEAD_PAYROLL'),
])
def test_officer_check_is_other_expense_and_employee_meals_remain_payroll(db,legacy,department_name,target,payroll):
    fixture(db)
    department=db.query(Department).filter(Department.name==department_name).first()
    if department is None:
        department=Department(id=30,code='TEST',name=department_name,business_unit_id=1)
        db.add(department);db.flush()
    j=JournalEntry(id=101,journal_number='JAN-OFFICER',posting_date=date(2026,1,10),status='POSTED',reference_type='MANUAL',reference_id=0,source_type='JOURNAL_IMPORT',external_reference='HOTEL-JAN2026-REG-2',import_batch_id=1,business_unit_id=1,location_id=1)
    # Identical COA, amount and department must still distinguish Officer Check
    # from an ordinary employee meal using the verified import line identity.
    for number,code in enumerate((legacy,'511007'),1):
        j.lines.append(JournalLine(line_number=number,account_id=21,debit=50,credit=0,business_unit_id=1,location_id=1,department_id=department.id))
        n=dict(account_id=21,department_id=department.id,legacy_code=code,debit='50',credit='0')
        db.add(ImportRow(id=9+number,import_batch_id=1,row_number=9+number,document_type='JOURNAL',raw_data_json={**n,'source_sha256':SOURCE_HASH},normalized_data_json=n,status='IMPORTED',entity_type='JOURNAL_ENTRY',entity_id=101))
    db.add(j);db.commit()
    r=deliver(FinancialReportingService(db),as_of_date=date(2026,1,31),report_scope='HOTEL')
    officer=next(a for a in r['related_accounts'] if legacy in a.get('legacy_codes',[]))
    assert officer['category']==target
    assert officer['account_name']=='Officer Check Dept. Head'
    assert officer['periods']['YTD']['current']==50
    assert amounts(r,payroll)==50
    assert amounts(r,'GOP')==995 and amounts(r,'NOP')==966
    selected=next(row for row in r['presentation_rows'] if row['key']==target)['member_keys']
    assert officer['presentation_key'] in selected
    group=next(g for g in r['group_reports'] if g['department_id']==department.id)
    rows=detail_rows(group,department_name,'2026-01-31')
    assert next(row[1] for row in rows if row and row[0].strip()=='Officer Check Dept. Head')==50
    from test_profit_loss_formulas import verify_formulas
    from app.services.profit_loss_delivery import workbook_sheets
    verify_formulas(workbook_sheets(r))
    assert [(line.account_id,line.debit,line.credit) for line in j.lines]==[(21,Decimal(50),Decimal(0))]*2
    assert db.query(JournalEntry).count()==2


def test_unverified_interest_keeps_ordinary_income_sign(db):
    fixture(db)
    row=db.get(ImportRow,8)
    row.raw_data_json={**row.raw_data_json,'source_sha256':'unverified'}
    db.commit()
    report=deliver(FinancialReportingService(db),as_of_date=date(2026,1,31),report_scope='HOTEL')
    assert amounts(report,'GOP')==1095
    assert amounts(report,'TOTAL_DEDUCTIONS')==29
    assert amounts(report,'NOP')==1066
    assert not any(a.get('nop_deduction') for a in report['related_accounts'])


def test_excel_net_expense_totals_recalculate_and_consolidate(db):
    fixture(db)
    from test_profit_loss_formulas import verify_formulas
    from app.services.profit_loss_delivery import workbook_sheets
    service=FinancialReportingService(db)
    report=deliver(service,as_of_date=date(2026,1,31),report_scope='HOTEL')
    verify_formulas(workbook_sheets(report))
    consolidated=deliver(service,as_of_date=date(2026,1,31))
    verify_formulas(workbook_sheets(consolidated))
    assert amounts(consolidated,'NOP')==1066
    assert sum(amounts(g,'NOP') for g in report['group_reports'])==1066
    assert all(v==0 for period in consolidated['split_control'].values() for v in period.values())
    assert amounts(report,'GOP')-amounts(report,'TOTAL_DEDUCTIONS')==amounts(report,'NOP')

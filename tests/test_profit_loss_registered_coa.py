"""Regression cases from the registered MMH chart and January report."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import pytest
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.financial_reporting_service import FinancialReportingService
from app.services.profit_loss_delivery import category, deliver
from app.services.profit_loss_template import detail_rows, summary_schedule
from app.services.profit_loss_relevance import related, department_key
from test_profit_loss_delivery import records, subtotal
from test_profit_loss_exact_template import hotel

@pytest.mark.parametrize('code,name,kind,group,expected', [
 ('760-100-100','Pendapatan Bunga Bank','REVENUE','OTHER_REVENUE','NONOPERATING_INCOME'),
 ('760-100-101','Pendaptan Lain-lain','REVENUE','OTHER_REVENUE','NONOPERATING_INCOME'),
 ('760-100-102','Pajak Pendapatan Bunga Bank','EXPENSE','OTHER_EXPENSE','UNDER_EXPENSE'),
 ('600-100-101','BPJS TK','EXPENSE','OPERATING_EXPENSE','OPERATING_PAYROLL'),
 ('600-100-106','PPH 21','EXPENSE','OPERATING_EXPENSE','OPERATING_PAYROLL'),
 ('600-100-200','Casusal Worker','EXPENSE','OPERATING_EXPENSE','OPERATING_PAYROLL'),
 ('500-100-101','Beban Pokok Langsung','EXPENSE','COST_OF_REVENUE','COST_OF_REVENUE'),
 ('700-500-111','Pajak Iklan','EXPENSE','OPERATING_EXPENSE','OPERATING_EXPENSE'),
 ('750-100-100','Gaji Head Office','EXPENSE','OPERATING_EXPENSE','OVERHEAD_PAYROLL'),
])
def test_exact_registered_categories(code,name,kind,group,expected):
 a=SimpleNamespace(id=1,account_number=code,account_name=name,account_type=kind,financial_statement_group=group)
 assert category(a,{})==expected
 if code.startswith('600-'):
  assert category(a,{}, {'scope_labels':{'department_id':'Board of Directur'}})=='OVERHEAD_PAYROLL'


def test_bank_interest_below_gop_with_unchanged_net_and_no_writes(records):
 db,h,*_=records
 a=ChartOfAccount(account_number='760-100-100',account_name='Pendapatan Bunga Bank',account_type='REVENUE',normal_balance='CREDIT',is_posting=True,financial_statement_group='OTHER_REVENUE')
 db.add(a);db.flush()
 j=JournalEntry(journal_number='INTEREST',posting_date=date(2026,10,5),status='POSTED',reference_type='MANUAL',reference_id=0,location_id=h.id,business_unit_id=h.business_unit_id)
 j.lines=[JournalLine(account_id=a.id,debit=0,credit=100)]
 db.add(j);db.commit()
 r=deliver(FinancialReportingService(db),as_of_date=date(2026,10,10),report_scope='HOTEL')
 assert subtotal(r,'REVENUE')==1000
 assert subtotal(r,'NONOPERATING_INCOME')==100
 assert subtotal(r,'GOP')==760
 assert subtotal(r,'NOP')==845
 assert a.id in next(x for x in r['presentation_rows'] if x['key']=='NOP')['account_ids']
 from app.services.executive_dashboard import dashboard_visuals
 visuals=dashboard_visuals(db,FinancialReportingService(db),r,{},date(2026,10,10),r['scope'])
 assert visuals['monthly'][-1]['revenue']==1000
 assert visuals['monthly'][-1]['nonoperating_income']==100
 assert visuals['monthly'][-1]['net_profit']==845
 assert db.query(JournalEntry).count()==4
 rows=summary_schedule(r,'Hotel',r['group_reports'],'2026-10-10')
 assert next(x[1] for x in rows if x and x[0]=='NETT OPERATING PROFIT')==845


def test_registered_aliases_and_separate_direct_cost():
 assert department_key('Board of Directur')=='BOD'
 a=SimpleNamespace(id=1,account_number='400-110-100',account_name='Pendapatan Project Catering',account_type='REVENUE')
 assert not related(a,{'scope_labels':{'business_unit_id':'Hotel'}},{},set())
 a.account_number='400-100-106';a.account_name='Outsite Catering'
 assert related(a,{'scope_labels':{'business_unit_id':'Hotel'}},{},set())
 pool=hotel('Swimming Pool',[('Kolam renang','REVENUE',16342)])
 rows=detail_rows(pool,'Pool','2026-01-31')
 assert next(x[1] for x in rows if x and x[0].strip()=='Swimming Pool')==16342
 fb=hotel('Food and Beverage',[('Food & Beverage','REVENUE',1000),('Beban Pokok Langsung','COST_OF_REVENUE',200)])
 fb['related_accounts'][1]['account_code']='500-100-101'
 rows=detail_rows(fb,'FB','2026-01-31')
 assert next(x[1] for x in rows if x and x[0].strip()=='Beban Pokok Langsung')==200
 assert next(x[1] for x in rows if x and x[0].strip()=='Food Cost')==0

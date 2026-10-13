"""Summary and complete account evidence, preserving organization scope."""
import re
from datetime import date
from sqlalchemy.orm import joinedload
from app.models.opening_balance import OpeningBalance
from app.models.location import Location

PERIODS=('MTD','YTD')
METRICS=('current','budget','last_month','last_year','variance','movement')
LABELS=('Current','Budget','Last month','Same period last year','Variance','Movement')
SECTIONS={'ASSETS':'Assets','LIABILITIES':'Liabilities','EQUITY':'Equity'}


def rows_for(report, title, details):
    rows=[[title,str(report['as_of_date']),report['scope_labels']['location_id'],report['scope_labels']['business_unit_id']],
          ['Account',*[f'{p} {label}' for p in PERIODS for label in LABELS]]]
    for section,label in SECTIONS.items():
        rows.append([label,*[report['section_totals'][section][p][m] for p in PERIODS for m in METRICS]])
        for row in details:
            if row['section']==section:
                rows.append([row['account_name'],*[row['periods'][p][m] for p in PERIODS for m in METRICS]])
    return rows


def workbook_sheets(service, report, *, budget_id=None):
    sheets=[('Summary',rows_for(report,'Balance Sheet',report['executive_rows']))]
    scope=report['scope']
    complete=service.build(report_type='BALANCE_SHEET',as_of_date=report['as_of_date'],**scope,
                           budget_id=budget_id,kap=False,include_zero=True,detail=True,all_accounts=True)
    sheets.append(('Account detail',rows_for(complete,'Balance Sheet account detail',complete['rows'])))
    used={'summary','account detail','opening balances'}
    for child in service.department_reports(complete,budget_id=budget_id,kap=False,include_zero=True,detail=True,all_accounts=True):
        name=re.sub(r'[\\/*?:\[\]\x00-\x1f]',' ',child['department_name']).strip().strip("'") or 'Department'
        name=name[:31];candidate=name;counter=1
        while candidate.casefold() in used:
            counter+=1;candidate=f'{name[:26]} {counter}'
        used.add(candidate.casefold())
        child={**child,'as_of_date':report['as_of_date'],'scope_labels':report['scope_labels']}
        sheets.append((candidate,rows_for(child,child['department_name'],child['rows'])))
    # Opening records have no department dimension. Never distribute them.
    if scope['department_id'] is None:
        q=service.db.query(OpeningBalance).options(joinedload(OpeningBalance.account)).filter(OpeningBalance.fiscal_year==report['as_of_date'].year)
        if scope['location_id'] is not None:q=q.filter(OpeningBalance.location_id==scope['location_id'])
        if scope['business_unit_id'] is not None:q=q.join(Location,Location.id==OpeningBalance.location_id).filter(Location.business_unit_id==scope['business_unit_id'])
        openings=q.order_by(OpeningBalance.location_id,OpeningBalance.account_id,OpeningBalance.id).all()
        locations={loc.id:loc.name for loc in service.db.query(Location).filter(Location.id.in_({x.location_id for x in openings if x.location_id})).all()}
        rows=[['Opening balances',str(date(report['as_of_date'].year,1,1))],['Location','Account','Debit','Credit']]
        for item in openings:
            if item.account.account_type not in ('ASSET','LIABILITY','EQUITY'):continue
            rows.append([locations.get(item.location_id,'Unassigned location'),item.account.account_name,
                         item.amount if item.balance_type=='DEBIT' else 0,item.amount if item.balance_type=='CREDIT' else 0])
        if len(rows)>2:sheets.append(('Opening balances',rows))
    return sheets

"""Aggregate owner dashboard evidence from posted financial activity."""
from collections import defaultdict
from datetime import date
from decimal import Decimal
from sqlalchemy import func
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.location import Location
from app.models.department import Department
from app.models.business_unit import BusinessUnit
from app.services.organization_access import effective_business_unit

ZERO=Decimal('0')


def dashboard_visuals(db, service, pnl, balance, as_of_date, scope):
    location=func.coalesce(JournalLine.location_id,JournalEntry.location_id)
    unit=effective_business_unit(func.coalesce(JournalLine.business_unit_id,JournalEntry.business_unit_id),location)
    department=func.coalesce(JournalLine.department_id,JournalEntry.department_id)
    month=func.extract('month',JournalEntry.posting_date)
    q=db.query(month,unit,location,department,ChartOfAccount.account_type,func.sum(JournalLine.debit-JournalLine.credit)).join(JournalEntry,JournalEntry.id==JournalLine.journal_entry_id).join(ChartOfAccount,ChartOfAccount.id==JournalLine.account_id).filter(JournalEntry.status=='POSTED',JournalEntry.posting_date.between(date(as_of_date.year,1,1),as_of_date),ChartOfAccount.account_type.in_(('REVENUE','INCOME','EXPENSE')),func.coalesce(JournalEntry.reference_type,'').notin_(('OPENING_BALANCE','OPENING_BALANCE_ADJUSTMENT','PERIOD_CLOSE','YEAR_END')))
    for key,column in (('location_id',location),('business_unit_id',unit),('department_id',department)):
        if scope[key] is not None:q=q.filter(column.is_(None) if key=='department_id' and scope[key]==0 else column==scope[key])
    rows=q.group_by(month,unit,location,department,ChartOfAccount.account_type).all()
    def metrics(values):
        revenue=sum((-Decimal(r[5] or 0) for r in values if r[4] in ('REVENUE','INCOME')),ZERO)
        expenses=sum((Decimal(r[5] or 0) for r in values if r[4]=='EXPENSE'),ZERO)
        return {'revenue':revenue,'expenses':expenses,'net_profit':revenue-expenses}
    trend=[{'month':f'{as_of_date.year}-{m:02d}',**metrics([r for r in rows if int(r[0])==m])} for m in range(1,as_of_date.month+1)]
    units={u.id:u for u in db.query(BusinessUnit).all()}
    locations={x.id:x.name for x in db.query(Location).all()}
    departments={x.id:x.name for x in db.query(Department).all()}
    groups=defaultdict(list)
    for row in rows:
        u=units.get(row[1]);hotel=u and 'HOTEL' in f'{u.code} {u.name}'.upper()
        groups[(row[1],'Department' if hotel else 'Location',row[3] if hotel else row[2])].append(row)
    performance=[]
    for (uid,dimension,ident),values in groups.items():
        name=(departments if dimension=='Department' else locations).get(ident,f'Unassigned {dimension.lower()}')
        performance.append({'name':name,'unit':units[uid].name if uid in units else 'Unassigned unit','dimension':dimension,
                            'MTD':metrics([r for r in values if int(r[0])==as_of_date.month]),'YTD':metrics(values)})
    performance.sort(key=lambda r:(r['unit'],r['name']))
    expenses={p:[{'name':r['label'],'amount':r['periods'][p]['current']} for r in pnl['presentation_rows'] if r['kind']=='category' and r['key'] not in ('BEBAN','REVENUE','NONOPERATING_INCOME')] for p in ('MTD','YTD')}
    cash_ids={a.id for a in db.query(ChartOfAccount).filter(ChartOfAccount.account_type=='ASSET',ChartOfAccount.account_subtype.in_(('CASH','BANK','PETTY_CASH','CASH_AND_BANK'))).all()}
    actual,_=service._actual('BALANCE_SHEET',as_of_date,as_of_date,scope)
    cash=sum((r['amount'] for r in actual.values() if r.get('account_id') in cash_ids),ZERO) if cash_ids else None
    return {'monthly':trend,'performance':performance,'expense_breakdown':expenses,'cash_balance':cash,'activity_count':len(rows)}

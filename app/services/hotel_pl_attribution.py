"""Read-only Hotel P&L attribution from verified January import evidence.

A legacy mapping never changes the ledger or revives an edited import line.
Amounts always come from current posted journal lines, not from workbook totals.
"""
from collections import defaultdict
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
from sqlalchemy import func
from app.models.business_unit import BusinessUnit
from app.models.chart_of_account import ChartOfAccount
from app.models.department import Department
from app.models.import_batch import ImportRow
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.organization_access import effective_business_unit

SOURCE_HASH = '045a54343005ee0c3cbd130838dd292c594ae434452abbf9b19578f99bc22507'
ZERO = Decimal(0)
# Exact legacy meanings established by the January Hotel trial balance.
LEGACY = {
    **{c: ('COST_OF_REVENUE', 'Food Cost') for c in ('401101','401159','401301','401401')},
    **{c: ('COST_OF_REVENUE', 'Beverage Cost') for c in ('401102','401160','401402')},
    **{c: ('COST_OF_REVENUE', 'Others Cost') for c in ('401309','401602')},
    '512037': ('OPERATING_EXPENSE','Fruit Basket, Welcome Drink, Birthday Cake'),
    '522023': ('OPERATING_EXPENSE','Food Testing'),
    '532023': ('OPERATING_EXPENSE','Food Test'),
    **{c: ('OPERATING_EXPENSE', 'Officer Check Dept. Head') for c in ('512050','514050','522050','532050')},
    **{c: ('OVERHEAD_EXPENSE', 'Officer Check Dept. Head') for c in ('542050','544050','546022','548049')},
    '591007': ('UNDER_EXPENSE','BOD - Owner Expenses'),
    '591050': ('UNDER_EXPENSE','BOD - Officer Check / Complimentary BOD'),
    '602070': ('UNDER_EXPENSE','Bank administration'),
    '601001': ('NONOPERATING_INCOME','Jasa Giro'),
    **{c: ('REVENUE','Room Sales') for c in ('301001','301002','301005','301006')},
    **{c: ('REVENUE','Food Revenue') for c in ('303001','303004','304001','305001')},
    **{c: ('REVENUE','Beverage Revenue') for c in ('303002','304002')},
    **{c: ('REVENUE','Miscellaneous Revenue') for c in ('303003','304003','305002','305009')},
    **{c: ('REVENUE','Swimming Pool') for c in ('306001','306002','306009')},
}


def signature(account_id, debit, credit, unit, location, department):
    return (int(account_id), Decimal(str(debit or 0)), Decimal(str(credit or 0)), unit, location, department)


def load_evidence(service, as_of, scope):
    """Two bounded reads, reused across periods and detail sheets in a request."""
    cache = getattr(service, '_hotel_pl_attribution_cache', None)
    if cache is None:
        cache = service._hotel_pl_attribution_cache = {}
    # A broad root read can serve its child reports without re-reading journals.
    for (end, dimensions), value in cache.items():
        parent = dict(dimensions)
        if end == as_of and all(parent[k] is None or parent[k] == v for k,v in scope.items()):
            return value
    location = func.coalesce(JournalLine.location_id,JournalEntry.location_id)
    unit = effective_business_unit(func.coalesce(JournalLine.business_unit_id,JournalEntry.business_unit_id),location)
    department = func.coalesce(JournalLine.department_id,JournalEntry.department_id)
    query = service.db.query(JournalLine,JournalEntry,ChartOfAccount,unit,location,department,Department.name).join(
        JournalEntry,JournalEntry.id==JournalLine.journal_entry_id).join(
        ChartOfAccount,ChartOfAccount.id==JournalLine.account_id).outerjoin(Department,Department.id==department).filter(
        JournalEntry.status=='POSTED',JournalEntry.posting_date.between(date(as_of.year-1,1,1),as_of),
        ChartOfAccount.account_type.in_(('REVENUE','INCOME','EXPENSE')),
        func.coalesce(JournalEntry.reference_type,'').notin_(('OPENING_BALANCE','OPENING_BALANCE_ADJUSTMENT','PERIOD_CLOSE','YEAR_END')))
    from app.services.hotel_support_rollup import department_ids
    source_departments = department_ids(service, scope)
    for k,col in (('business_unit_id',unit),('location_id',location),('department_id',department)):
        if scope[k] is not None:
            query=query.filter(col.is_(None) if k=='department_id' and scope[k]==0 else col.in_(source_departments) if k=='department_id' else col==scope[k])
    lines=query.all()
    journal_ids={j.id for _,j,_,_,_,_,_ in lines if j.source_type=='JOURNAL_IMPORT' and (j.external_reference or '').startswith('HOTEL-JAN2026-REG-')}
    journals={j.id:j for _,j,_,_,_,_,_ in lines}
    evidence=defaultdict(lambda:defaultdict(set))
    if journal_ids and service._schema.has_table('import_rows'):
        # Subquery avoids a large PostgreSQL/SQLite bind-parameter list.
        ids=query.with_entities(JournalEntry.id).filter(JournalEntry.source_type=='JOURNAL_IMPORT',JournalEntry.external_reference.like('HOTEL-JAN2026-REG-%')).distinct()
        rows=service.db.query(ImportRow).filter(ImportRow.entity_id.in_(ids),ImportRow.entity_type=='JOURNAL_ENTRY',ImportRow.status=='IMPORTED').order_by(ImportRow.entity_id,ImportRow.import_batch_id,ImportRow.row_number,ImportRow.id).all()
        ordinals=defaultdict(int)
        for row in rows:
            raw,n=row.raw_data_json or {},row.normalized_data_json or {}
            if n.get('omit_zero_value'):
                continue
            try:
                journal=journals[row.entity_id]
                key=signature(n['account_id'],n['debit'],n['credit'],n.get('business_unit_id',journal.business_unit_id),n.get('location_id',journal.location_id),n.get('department_id',journal.department_id))
                if key[1]==0 and key[2]==0: continue
                ordinals[(row.entity_id,row.import_batch_id)]+=1
                if raw.get('source_sha256')!=SOURCE_HASH:continue
                # The legacy code and both amounts must agree in the two saved snapshots.
                if n.get('legacy_code')!=raw.get('legacy_code') or Decimal(str(raw['debit']))!=key[1] or Decimal(str(raw['credit']))!=key[2]:continue
            except (KeyError,ValueError,TypeError,InvalidOperation):continue
            evidence[(row.entity_id,row.import_batch_id)][(ordinals[(row.entity_id,row.import_batch_id)],key)].add(str(raw['legacy_code']))
    result=(lines,evidence)
    cache[(as_of,tuple(scope.items()))]=result
    return result


def attribute(service, report, records, mappings):
    from app.services.profit_loss_delivery import category
    from datetime import date as date_type
    as_of=report['as_of_date']
    if not isinstance(as_of,date_type):as_of=date_type.fromisoformat(as_of)
    lines,evidence=load_evidence(service,as_of,report['scope'])
    result=deepcopy(records)
    bases={r['account_id']:r for r in result}
    slices={}
    if not hasattr(service,'_hotel_pl_unit_ids'):
        service._hotel_pl_unit_ids={u.id for u in service.db.query(BusinessUnit).all() if 'hotel' in f'{u.code} {u.name}'.lower()}
    from app.services.hotel_support_rollup import department_ids
    source_departments = department_ids(service, report['scope'])
    matched=0
    for line,journal,account,unit,location,department,department_name in lines:
        actual_scope=dict(business_unit_id=unit,location_id=location,department_id=department)
        if any(v is not None and (actual_scope[k] not in source_departments if k=='department_id' and v != 0 else actual_scope[k] != (None if k=='department_id' and v==0 else v)) for k,v in report['scope'].items()):continue
        base=bases.get(account.id)
        if base is None:continue
        # Hotel policy is scoped to the actual unit, never applied to Catering.
        if unit not in service._hotel_pl_unit_ids:continue
        target=category(account,mappings,{'scope_labels':{'department_id':department_name,'business_unit_id':'Hotel'}})
        if target=='UNCLASSIFIED':target='UNDER_EXPENSE'
        label=account.account_name
        key=signature(account.id,line.debit,line.credit,unit,location,department)
        codes=evidence.get((journal.id,journal.import_batch_id),{}).get((line.line_number,key),set())
        legacy=next(iter(codes)) if len(codes)==1 else None
        if legacy in LEGACY:
            target,label=LEGACY[legacy]
            matched+=1
        if (target,label)==(base['category'],base['account_name']):continue
        token=f'{account.id}:{target}:{label}'
        if token not in slices:
            item=deepcopy(base)
            item.update(category=target,account_name=label,coa_account_name=account.account_name,
                        presentation_key=token,source_slice=True,legacy_codes=[])
            item['periods']={p:{m:None if v is None or m in ('budget','variance') else ZERO for m,v in amounts.items()} for p,amounts in base['periods'].items()}
            slices[token]=item
        item=slices[token]
        if legacy and legacy not in item['legacy_codes']:item['legacy_codes'].append(legacy)
        amount=Decimal(line.credit-line.debit) if account.account_type in ('REVENUE','INCOME') else Decimal(line.debit-line.credit)
        for p,dates in report['periods'].items():
            for metric in ('current','last_month','last_year'):
                start,end=dates[metric]
                if isinstance(start,str):start,end=date_type.fromisoformat(start),date_type.fromisoformat(end)
                if start<=journal.posting_date<=end and base['periods'][p][metric] is not None:
                    base['periods'][p][metric]-=amount
                    item['periods'][p][metric]+=amount
        item['has_posted_activity']=True
    for base in result:
        base['presentation_key']=str(base['account_id'])
        for amounts in base['periods'].values():amounts['variance']=amounts['current']-amounts['budget'] if amounts['budget'] is not None else None
    report['metadata']['hotel_attribution']={'basis':'VERIFIED_IMPORT_AND_CURRENT_POSTED_LINES','verified_legacy_lines':matched,'ledger_unchanged':True}
    return [*result,*slices.values()]

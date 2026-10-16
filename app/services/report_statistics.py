"""Read-only operational statistics for P&L; never a financial posting."""
from collections import defaultdict
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import joinedload
from fastapi import HTTPException
from app.models.accounting_setting import AccountingSetting
from app.models.business_unit import BusinessUnit
from app.models.chart_of_account import ChartOfAccount
from app.models.location import Location
from app.models.statistical_value import StatisticalValue

PREFIX = 'PL_STAT:'
# Exact codes supplied by Finance. Overrides are saved through Report Setup.
SOURCES = {
    'ROOM_AVAILABLE': ('Room Available', '900-100-100', 'sum'),
    'ROOM_SALEABLE': ('Room Saleable', None, 'sum'),
    'ROOM_OCCUPIED': ('Room Occupied', '900-100-101', 'sum'),
    'ROOM_SOLD': ('Paid Room Nights Sold', None, 'sum'),
    'GUESTS': ('Number of Guest', '900-100-103', 'sum'),
    'FOOD_COVERS': ('Food Cover', '900-200-100', 'sum'),
    'BEVERAGE_COVERS': ('Beverage Cover', '900-200-101', 'sum'),
    'BOOKKEEPING_RATE': ('Bookkeeping Rate', '900-100-102', 'latest'),
    'ROOM_REVENUE': ('Room Revenue for ADR', '400-100-100', 'financial'),
}
METRICS = ('current', 'budget', 'last_month', 'last_year')
ZERO = Decimal(0)


def mappings(db):
    accounts = {a.id: a for a in db.query(ChartOfAccount).all()}
    overrides = {s.setting_key[len(PREFIX):]: s.account_id for s in db.query(AccountingSetting).filter(AccountingSetting.setting_key.startswith(PREFIX)).all()}
    resolved = {}
    for key, (_, code, _) in SOURCES.items():
        account = accounts.get(overrides.get(key)) if key in overrides else next((a for a in accounts.values() if code and a.account_number == code), None)
        if account and eligible(account, key, accounts):
            resolved[key] = account.id
    return overrides, resolved, accounts


def eligible(account, key, accounts):
    if not account.is_active:
        return False
    if key == 'ROOM_REVENUE':
        return account.account_type in ('REVENUE', 'INCOME')
    return (account.account_type == 'STATISTIC' and account.account_number != '900'
            and not any(a.parent_account_id == account.id and a.is_active for a in accounts.values()))


def save_mappings(db, selected):
    _, _, accounts = mappings(db)
    for key, aid in selected.items():
        if key not in SOURCES or aid not in accounts or not eligible(accounts[aid], key, accounts):
            raise HTTPException(422, 'Choose a statistical detail account, or a revenue account for ADR')
    rows = {r.setting_key[len(PREFIX):]: r for r in db.query(AccountingSetting).filter(AccountingSetting.setting_key.startswith(PREFIX)).with_for_update().all()}
    for key, row in rows.items():
        if key not in selected:
            db.delete(row)
    for key, aid in selected.items():
        row = rows.get(key)
        if row is None:
            row = AccountingSetting(setting_key=PREFIX+key)
            db.add(row)
        row.account_id, row.description = aid, SOURCES[key][0]


def aggregate(records, start, end, field, mode, department_scoped=False):
    """Location totals take precedence over their departmental components."""
    selected = [r for r in records if start <= r.period <= end and getattr(r, field) is not None]
    if not selected:
        return None, None, None
    if mode == 'latest':
        latest = {}
        for r in selected:
            latest[r.location_id] = max(latest.get(r.location_id, r.period), r.period)
        selected = [r for r in selected if r.period == latest[r.location_id]]
    groups = defaultdict(list)
    for row in selected:
        groups[(row.location_id, row.period)].append(row)
    chosen = []
    for group in groups.values():
        location_total = [r for r in group if r.department_id is None]
        chosen.extend(group if department_scoped or not location_total else location_total)
    units = {r.unit.strip().upper() for r in chosen}
    if len(units) != 1:
        return None, None, 'Mixed units or currency pairs'
    unit = next(iter(units))
    amounts = [getattr(r, field) for r in chosen]
    if mode == 'latest':
        # Rates are not additive, including across locations or departments.
        return (amounts[0], unit, None) if len(set(amounts)) == 1 else (None, unit, 'Different rates in the selected scope')
    return sum(amounts, ZERO), unit, None


def ratio(numerator, denominator):
    return None if numerator is None or denominator in (None, ZERO) else numerator / denominator


def build_statistics(service, report, budget_id=None):
    if not hasattr(service, '_statistic_sources'):
        service._statistic_sources = mappings(service.db)
    _, selected, all_accounts = service._statistic_sources
    if not selected or not service._schema.has_table('statistical_values'):
        return {'rows': [], 'available': False}
    scope, calendar = report['scope'], report['periods']
    cache_key = (tuple(scope.items()), report['as_of_date'])
    if not hasattr(service, '_statistic_records'):
        service._statistic_records = {}
    if cache_key not in service._statistic_records:
        query = service.db.query(StatisticalValue).join(Location).options(joinedload(StatisticalValue.location)).filter(
            StatisticalValue.account_id.in_(selected.values()),
            StatisticalValue.period >= date(max(2026, report['as_of_date'].year-1), 1, 1),
            StatisticalValue.period <= report['as_of_date'])
        if scope['location_id'] is not None:
            query = query.filter(StatisticalValue.location_id == scope['location_id'])
        if scope['business_unit_id'] is not None:
            query = query.filter(Location.business_unit_id == scope['business_unit_id'])
        if scope['department_id'] is not None:
            query = query.filter(StatisticalValue.department_id.is_(None) if scope['department_id'] == 0 else StatisticalValue.department_id == scope['department_id'])
        service._statistic_records[cache_key] = query.all()
    records = service._statistic_records[cache_key]
    units = service.db.query(BusinessUnit).all()
    hotel_ids = {u.id for u in units if 'HOTEL' in f'{u.code} {u.name}'.upper()}
    results = {}
    for key, (label, _, mode) in SOURCES.items():
        if key == 'ROOM_REVENUE':
            continue
        source = [r for r in records if r.account_id == selected.get(key)]
        if key not in ('FOOD_COVERS', 'BEVERAGE_COVERS'):
            source = [r for r in source if r.location.business_unit_id in hotel_ids]
        periods, issues, source_units = {}, {}, {}
        for p, windows in calendar.items():
            periods[p], issues[p], source_units[p] = {}, {}, {}
            for metric in METRICS:
                start, end = windows['current' if metric == 'budget' else metric]
                amount, unit, issue = aggregate(source, start, end, 'budget' if metric == 'budget' else 'actual', mode, scope['department_id'] is not None)
                periods[p][metric], source_units[p][metric] = amount, unit
                if issue:
                    issues[p][metric] = issue
            v = periods[p]
            v['variance'] = v['current']-v['budget'] if v['current'] is not None and v['budget'] is not None and source_units[p]['current'] == source_units[p]['budget'] else None
        canonical = source_units['MTD']['current'] or source_units['YTD']['current'] or next((u for units_ in source_units.values() for u in units_.values() if u), None)
        for p in periods:
            for metric in METRICS:
                if source_units[p][metric] not in (None, canonical):
                    periods[p][metric] = None
                    issues[p][metric] = 'Comparison uses a different unit or currency pair'
            v = periods[p]
            v['variance'] = v['current']-v['budget'] if v['current'] is not None and v['budget'] is not None else None
        results[key] = dict(key=key, label=label, format='number', aggregation=mode,
            account_id=selected.get(key), unit=canonical,
            periods=periods, source_units=source_units, issues=issues)

    revenue_ids = set()
    root_id = selected.get('ROOM_REVENUE')
    if root_id:
        pending = [root_id]
        while pending:
            aid = pending.pop()
            if aid in revenue_ids:
                continue
            revenue_ids.add(aid)
            pending.extend(a.id for a in all_accounts.values() if a.parent_account_id == aid)
    # The numerator is financial Room Revenue, scoped to Hotel; Catering revenue
    # is never pulled in by a consolidated report using the same COA.
    room_revenue = {p: {} for p in calendar}
    for p, windows in calendar.items():
        for metric in METRICS:
            amounts = []
            if not root_id or not selected.get('ROOM_SOLD'):
                room_revenue[p][metric] = None
                continue
            start, end = windows['current' if metric == 'budget' else metric]
            for unit_id in hotel_ids:
                if scope['business_unit_id'] is not None and scope['business_unit_id'] != unit_id:
                    continue
                if scope['location_id'] is not None:
                    loc = service.db.get(Location, scope['location_id'])
                    if not loc or loc.business_unit_id != unit_id:
                        continue
                hotel_scope = {**scope, 'business_unit_id': unit_id}
                if metric == 'budget':
                    balances, available = service.budget(start, end, hotel_scope, budget_id, 'PROFIT_LOSS')
                else:
                    available = end.year == report['as_of_date'].year or service._has_year_evidence('PROFIT_LOSS', end.year, hotel_scope)
                    actual, _ = service._actual('PROFIT_LOSS', start, end, hotel_scope) if available else ({}, None)
                    balances = {aid: row['amount'] for aid, row in actual.items()}
                if available and root_id:
                    amounts.append(sum((balances.get(aid, ZERO) for aid in revenue_ids), ZERO))
            room_revenue[p][metric] = sum(amounts, ZERO) if amounts else None

    for key, label, kind in [('OCCUPANCY','Occupancy','percent'), ('ADR','Average Room Rate / ADR','money')]:
        values = {p: {} for p in calendar}
        for p in calendar:
            for metric in METRICS:
                if key == 'OCCUPANCY':
                    numerator = results['ROOM_OCCUPIED']['periods'][p][metric]
                    denominator = results['ROOM_AVAILABLE']['periods'][p][metric]
                    a = results['ROOM_OCCUPIED']['source_units'][p][metric]
                    b = results['ROOM_AVAILABLE']['source_units'][p][metric]
                    values[p][metric] = ratio(numerator, denominator) if a == b else None
                else:
                    # A separate paid-room definition avoids treating all
                    # occupied (possibly complimentary) rooms as sold rooms.
                    values[p][metric] = ratio(room_revenue[p][metric], results['ROOM_SOLD']['periods'][p][metric])
            v = values[p]
            v['variance'] = v['current']-v['budget'] if v['current'] is not None and v['budget'] is not None else None
        results[key] = dict(key=key, label=label, format=kind, aggregation='ratio', unit='%' if kind == 'percent' else 'IDR', periods=values, issues={})
    order = ('ROOM_AVAILABLE','ROOM_SALEABLE','ROOM_OCCUPIED','ROOM_SOLD','OCCUPANCY','ADR','GUESTS','FOOD_COVERS','BEVERAGE_COVERS','BOOKKEEPING_RATE')
    scoped_hotel = any(scope['business_unit_id'] in (None, uid) and (scope['location_id'] is None or (service.db.get(Location, scope['location_id']) and service.db.get(Location, scope['location_id']).business_unit_id == uid)) for uid in hotel_ids)
    has_room_data = any(r.account_id in {selected.get(k) for k in ('ROOM_AVAILABLE','ROOM_OCCUPIED','ROOM_SALEABLE','ROOM_SOLD','GUESTS')} and r.location.business_unit_id in hotel_ids for r in records)
    show_rooms = scoped_hotel and (scope['department_id'] is None or has_room_data)
    output = [results[k] for k in order if (show_rooms or k in ('FOOD_COVERS','BEVERAGE_COVERS') or any(v is not None for p in results[k]['periods'].values() for v in p.values()))]
    return {'available': True, 'rows': output,
            'source': 'STATISTICAL_VALUES', 'budget_source': 'STATISTICAL_VALUES',
            'room_revenue_account_id': root_id}

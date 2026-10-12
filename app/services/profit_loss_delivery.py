"""Read-only management P&L presentation and organization workbook delivery."""
from decimal import Decimal
import re
from fastapi import HTTPException
from app.models.accounting_setting import AccountingSetting
from app.models.business_unit import BusinessUnit
from app.models.location import Location

ZERO = Decimal('0')
METRICS = ('current', 'budget', 'last_month', 'last_year', 'variance')
CATEGORIES = {
    'REVENUE': 'Pendapatan', 'COST_OF_REVENUE': 'HPP',
    'OPERATING_PAYROLL': 'Gaji operasional', 'OPERATING_EXPENSE': 'Beban operasional',
    'OVERHEAD_PAYROLL': 'Gaji overhead', 'OVERHEAD_EXPENSE': 'Beban overhead',
    'UNDER_EXPENSE': 'Under expenses', 'UNCLASSIFIED': 'Beban belum diklasifikasikan',
}
SETTING_PREFIX = 'PL_CATEGORY:'


def category(account, mappings):
    if account.account_type in ('REVENUE', 'INCOME'):
        return 'REVENUE'
    configured = mappings.get(account.id)
    if configured in CATEGORIES:
        return configured
    group = account.financial_statement_group
    if group in CATEGORIES:
        return group
    return 'UNDER_EXPENSE' if group == 'OTHER_EXPENSE' else 'UNCLASSIFIED'


def presentation(report, originals, values, accounts, mappings, selected):
    """All ledger values determine totals; display choices only hide details."""
    members = {key: [] for key in CATEGORIES}
    for aid, original in originals.items():
        account = accounts.get(aid)
        if account:
            members[category(account, mappings)].append((aid, account))
    result, totals = [], {}
    for code, label in CATEGORIES.items():
        totals[code] = {}
        for period in ('MTD', 'YTD'):
            totals[code][period] = {}
            for metric in METRICS[:-1]:
                unavailable = (metric == 'budget' and not report['budget_available'][period]) or report['comparison_available'][period].get(metric) is False
                totals[code][period][metric] = None if unavailable else sum((values[period][metric].get(aid, ZERO) for aid, _ in members[code]), ZERO)
            v = totals[code][period]
            v['variance'] = v['current'] - v['budget'] if v['budget'] is not None else None
        result.append(dict(key=code, label=label, kind='category', periods=totals[code], account_ids=[aid for aid, _ in members[code]]))
        visible = {}
        for aid, account in members[code]:
            ancestors, current = set(), account
            while current and current.id not in ancestors:
                ancestors.add(current.id)
                current = accounts.get(current.parent_account_id)
            if selected is not None and not selected.intersection(ancestors):
                continue
            parent = accounts.get(account.parent_account_id) if report['header_only'] else None
            name = label if code == 'REVENUE' else parent.account_name if parent else label if report['header_only'] else account.account_name
            row = visible.setdefault(name, dict(key=f'{code}:{name}', label=name, kind='detail', account_ids=[], periods={p: {m: ZERO for m in METRICS} for p in ('MTD', 'YTD')}))
            row['account_ids'].append(aid)
            for period in ('MTD', 'YTD'):
                for metric in METRICS[:-1]:
                    row['periods'][period][metric] += values[period][metric].get(aid, ZERO)
        for row in sorted(visible.values(), key=lambda r: r['label']):
            for period in ('MTD', 'YTD'):
                for metric in METRICS[:-1]:
                    if totals[code][period][metric] is None:
                        row['periods'][period][metric] = None
                v = row['periods'][period]
                v['variance'] = v['current'] - v['budget'] if v['budget'] is not None else None
            if report.get('include_zero') or any(v not in (ZERO, None) for amounts in row['periods'].values() for v in amounts.values()):
                result.append(row)
        if code in ('OPERATING_EXPENSE', 'OVERHEAD_EXPENSE', 'UNCLASSIFIED'):
            deductions = ['COST_OF_REVENUE', 'OPERATING_PAYROLL', 'OPERATING_EXPENSE']
            key, title = 'GOI', 'Gross Operating Income / Loss'
            if code in ('OVERHEAD_EXPENSE', 'UNCLASSIFIED'):
                deductions += ['OVERHEAD_PAYROLL', 'OVERHEAD_EXPENSE']
                key, title = 'GOP', 'GOP / GOL'
            if code == 'UNCLASSIFIED':
                deductions += ['UNDER_EXPENSE', 'UNCLASSIFIED']
                key, title = 'NOP', 'Net Operating Profit / Loss'
            amounts = {p: {} for p in ('MTD', 'YTD')}
            for p in amounts:
                for m in METRICS:
                    vs = [totals[c][p][m] for c in ['REVENUE', *deductions]]
                    amounts[p][m] = None if any(v is None for v in vs) else vs[0] - sum(vs[1:])
            result.append(dict(key=key, label=title, kind='subtotal', account_ids=[], periods=amounts))
    return result


def unit_kind(unit):
    name = f'{unit.code} {unit.name}'.upper()
    return 'HOTEL' if 'HOTEL' in name else 'CATERING' if 'CATERING' in name else 'OTHER'


def deliver(service, *, as_of_date, report_scope='CONSOLIDATED', location_id=None,
            business_unit_id=None, department_id=None, budget_id=None, kap=False, include_zero=False, detail=False, include_breakdown=True):
    if report_scope not in ("HOTEL", "CATERING", "CONSOLIDATED"):
        raise HTTPException(422, "Choose Hotel, Catering or Consolidated")
    units = service.db.query(BusinessUnit).all()
    if report_scope != 'CONSOLIDATED':
        candidates = [u for u in units if unit_kind(u) == report_scope]
        if business_unit_id is not None:
            candidates = [u for u in candidates if u.id == business_unit_id]
        if location_id is not None:
            location = service.db.get(Location, location_id)
            candidates = [u for u in candidates if location and u.id == location.business_unit_id]
        if len(candidates) != 1:
            raise HTTPException(422, f'{report_scope.title()} report requires a matching business unit and location')
        business_unit_id = candidates[0].id
    options = dict(report_type='PROFIT_LOSS', as_of_date=as_of_date, location_id=location_id,
                   business_unit_id=business_unit_id, department_id=department_id,
                   budget_id=budget_id, kap=kap, include_zero=include_zero, detail=detail)
    report = service.build(**options)
    report['report_scope'] = report_scope
    report['unit_reports'], report['group_reports'] = [], []
    for unit in sorted(units, key=lambda u: u.name) if include_breakdown else []:
        if business_unit_id is not None and unit.id != business_unit_id:
            continue
        if location_id is not None:
            location = service.db.get(Location, location_id)
            if not location or location.business_unit_id != unit.id:
                continue
        child_options = {**options, 'business_unit_id': unit.id}
        child = service.build(**child_options)
        child['title'] = unit.name
        child['report_scope'] = unit_kind(unit)
        report['unit_reports'].append(child)
        if unit_kind(unit) == 'HOTEL':
            for department in service.department_reports(child, budget_id=budget_id, kap=kap, include_zero=include_zero, detail=detail):
                report['group_reports'].append({**department, 'title': f"{unit.name} · {department['department_name']}", 'scope': {**child['scope'], 'department_id': department['department_id'] or 0}})
        else:
            query = service.db.query(Location).filter(Location.business_unit_id == unit.id)
            if location_id is not None:
                query = query.filter(Location.id == location_id)
            for location in query.order_by(Location.name).all():
                location_report = service.build(**{**child_options, 'location_id': location.id})
                report['group_reports'].append({**location_report, 'title': f'{unit.name} · {location.name}'})
    # Surface missing organizational attribution rather than silently distributing it.
    report['split_control'] = {}
    for p in ('MTD', 'YTD') if include_breakdown else ():
        report['split_control'][p] = {}
        for section in ('REVENUE', 'COST_OF_REVENUE', 'EXPENSES'):
            total = sum((r['section_totals'][section][p]['current'] for r in report['group_reports']), ZERO)
            report['split_control'][p][section] = report['section_totals'][section][p]['current'] - total
    position = service.build(report_type='BALANCE_SHEET', as_of_date=as_of_date,
                             location_id=location_id, business_unit_id=business_unit_id, detail=True)
    amounts = position['section_totals']
    gap = amounts['ASSETS']['YTD']['current'] - amounts['LIABILITIES']['YTD']['current'] - amounts['EQUITY']['YTD']['current']
    report['balance_control'] = dict(difference=gap, is_balanced=gap == ZERO, department_id=None)
    return report


def workbook_sheets(report):
    columns = ['Name', *[f'{p} {m.replace("_", " ").title()}' for p in ('MTD', 'YTD') for m in METRICS]]
    def rows(statement, title):
        result = [[title, str(report['as_of_date'])], columns]
        for row in statement['presentation_rows']:
            result.append([row['label'], *[row['periods'][p][m] for p in ('MTD', 'YTD') for m in METRICS]])
        return result
    summary = rows(report, f"Profit & Loss · {report['report_scope']}")
    summary += [[], ['Balance control', report['balance_control']['difference']], [], ['Unit summary']]
    for unit in report['unit_reports']:
        summary += rows(unit, unit['title'])
        summary += [[]]
    summary += [['Split control', *[f'{p} {s}' for p in ('MTD', 'YTD') for s in ('REVENUE', 'COST_OF_REVENUE', 'EXPENSES')]], ['Unassigned / unmatched difference', *[report['split_control'][p][s] for p in ('MTD', 'YTD') for s in ('REVENUE', 'COST_OF_REVENUE', 'EXPENSES')]], [], ['Department / location summary', *columns[1:]]]
    for group in report['group_reports']:
        nop = next(r for r in group['presentation_rows'] if r['key'] == 'NOP')
        summary.append([group['title'], *[nop['periods'][p][m] for p in ('MTD', 'YTD') for m in METRICS]])
    used = {'summary'}
    sheets = [('Summary', summary)]
    for index, group in enumerate(report['group_reports'], 1):
        name = re.sub(r'[\\/*?:\[\]]', '-', group['title']).strip(" '")[:31] or f'Report {index}'
        base, count = name, 1
        while name.casefold() in used:
            count += 1
            suffix = f' ({count})'
            name = base[:31-len(suffix)] + suffix
        used.add(name.casefold())
        sheets.append((name, rows(group, group['title'])))
    return sheets

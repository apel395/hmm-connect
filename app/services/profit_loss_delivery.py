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
    if group == 'OPERATING_EXPENSE' and re.search(r'\b(gaji|salary|salaries|payroll)\b', account.account_name, re.I):
        return 'OPERATING_PAYROLL'
    if group in CATEGORIES:
        return group
    return 'UNDER_EXPENSE' if group == 'OTHER_EXPENSE' else 'UNCLASSIFIED'


def presentation(report, originals, values, accounts, mappings, selected, evidence=frozenset()):
    """Summary layout plus complete related accounts, including zero values."""
    from app.services.profit_loss_relevance import related
    members = {key: [] for key in CATEGORIES if key != 'UNCLASSIFIED'}
    for aid in originals:
        account = accounts.get(aid)
        if account and related(account, report, values, evidence):
            code = category(account, mappings)
            members['UNDER_EXPENSE' if code == 'UNCLASSIFIED' else code].append((aid, account))
    def amounts(ids):
        result = {}
        for period in ('MTD', 'YTD'):
            result[period] = {}
            for metric in METRICS[:-1]:
                unavailable = (metric == 'budget' and not report['budget_available'][period]) or report['comparison_available'][period].get(metric) is False
                result[period][metric] = None if unavailable else sum((values[period][metric].get(aid, ZERO) for aid in ids), ZERO)
            v = result[period]
            v['variance'] = v['current'] - v['budget'] if v['budget'] is not None else None
        return result
    totals = {code: amounts([aid for aid, _ in group]) for code, group in members.items()}
    related = []
    for code, group in members.items():
        for aid, account in group:
            related.append(dict(account_id=aid, account_code=account.account_number,
                account_name=account.account_name, category=code, periods=amounts([aid])))
    report['related_accounts'] = sorted(related, key=lambda r: r['account_code'])
    result = []
    for code, group in members.items():
        if code == 'COST_OF_REVENUE':
            expense_ids = [aid for c, rows in members.items() if c != 'REVENUE' for aid, _ in rows]
            result.append(dict(key='BEBAN', label='Beban', kind='category', account_ids=expense_ids, periods=amounts(expense_ids)))
        result.append(dict(key=code, label=CATEGORIES[code], kind='category',
            account_ids=[aid for aid, _ in group], periods=totals[code]))
        visible = {}
        for aid, account in group:
            ancestors, current = set(), account
            while current and current.id not in ancestors:
                ancestors.add(current.id); current = accounts.get(current.parent_account_id)
            if selected is not None and not selected.intersection(ancestors):
                continue
            parent = accounts.get(account.parent_account_id) if report['header_only'] else None
            name = CATEGORIES[code] if code == 'REVENUE' else parent.account_name if parent else CATEGORIES[code] if report['header_only'] else account.account_name
            visible.setdefault(name, []).append(aid)
        for name, ids in sorted(visible.items()):
            data = amounts(ids)
            if report.get('include_zero') or any(v not in (ZERO, None) for p in data.values() for v in p.values()):
                result.append(dict(key=f'{code}:{name}', label=name, kind='detail', account_ids=ids, periods=data))
        if code in ('OPERATING_EXPENSE', 'OVERHEAD_EXPENSE', 'UNDER_EXPENSE'):
            deductions = ['COST_OF_REVENUE', 'OPERATING_PAYROLL', 'OPERATING_EXPENSE']
            key, label = 'GOI', 'Gross Operating Income / Profit / Loss'
            if code in ('OVERHEAD_EXPENSE', 'UNDER_EXPENSE'):
                deductions += ['OVERHEAD_PAYROLL', 'OVERHEAD_EXPENSE']; key, label = 'GOP', 'GOP / GOL'
            if code == 'UNDER_EXPENSE':
                deductions += ['UNDER_EXPENSE']; key, label = 'NOP', 'NOP'
            data = {p: {} for p in ('MTD', 'YTD')}
            for p in data:
                for m in METRICS:
                    vs = [totals[c][p][m] for c in ['REVENUE', *deductions]]
                    data[p][m] = None if any(v is None for v in vs) else vs[0] - sum(vs[1:])
            result.append(dict(key=key, label=label, kind='subtotal', periods=data,
                account_ids=[aid for c in ['REVENUE', *deductions] for aid, _ in members[c]]))
    return result


def unit_kind(unit):
    name = f'{unit.code} {unit.name}'.upper()
    return 'HOTEL' if 'HOTEL' in name else 'CATERING' if 'CATERING' in name else 'OTHER'


def deliver(service, *, as_of_date, report_scope='CONSOLIDATED', location_id=None,
            business_unit_id=None, department_id=None, budget_id=None, kap=False, include_zero=False, detail=False, include_breakdown=True, all_accounts=False):
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
                   budget_id=budget_id, kap=kap, include_zero=include_zero, detail=detail, all_accounts=all_accounts)
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
            for department in service.department_reports(child, budget_id=budget_id, kap=kap, include_zero=include_zero, detail=detail, all_accounts=all_accounts):
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
    from app.services.profit_loss_workbook import workbook_sheets as template_sheets
    return template_sheets(report)

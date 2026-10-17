"""Render the supplied PL schedules using computed, scoped report data only."""
from datetime import date
from decimal import Decimal
from functools import lru_cache
import json
from pathlib import Path
import re

from app.services.profit_loss_workbook import values, combine, service_charge, normalized, PERIODS, METRICS
from app.services.profit_loss_relevance import department_key

ROOT = Path(__file__).resolve().parents[1] / 'report_templates'


@lru_cache(maxsize=1)
def layouts():
    return json.loads((ROOT / 'pl_layouts.json').read_text())['profiles']


def col_number(name):
    result = 0
    for char in name:
        result = result * 26 + ord(char) - 64
    return result


class TemplateRows(list):
    def __init__(self, statement, profile, title, as_of):
        super().__init__()
        self.template_profile = layouts()[profile]
        self.cell_styles, self.row_heights = {}, {}
        self.headers = [c.get('label', '') for _, c in sorted(self.template_profile['rows']['6']['cells'].items(), key=lambda pair: col_number(pair[0]))]
        self.headers = self.headers[:max(i + 1 for i, label in enumerate(self.headers) if label)]
        self.statement = statement
        self.revenue = statement.get('template_revenue') or values(statement, [a for a in statement.get('related_accounts', []) if a['category'] == 'REVENUE'])
        month = date.fromisoformat(str(as_of)).strftime('%m - %Y')
        for index, row in enumerate([['PT. Mutiara Merdeka Hotel'], ['INCOME AND EXPENDITURE ACCOUNT'], [title], [month], [], self.headers], 1):
            self.add(row, index)

    def add(self, row, source_row):
        self.append(row)
        source = self.template_profile['rows'].get(str(source_row), {})
        self.cell_styles[len(self)] = {col_number(c): v['style'] for c, v in source.get('cells', {}).items()}
        self.row_heights[len(self)] = source.get('height', 15)

    def line(self, label, amounts, source_row, *, statistic=False, denominator=None):
        row, last = [label], None
        for header in self.headers[1:]:
            if header == '%':
                p, metric = last
                amount, base = amounts[p][metric], (denominator or self.revenue)[p][metric]
                row.append(None if statistic or amount is None or base in (None, 0) else amount / base)
                continue
            period = 'YTD' if header.startswith('YTD') else 'MTD'
            metric = 'budget' if 'Budget' in header else 'last_month' if 'Last Month' in header else 'last_year' if 'Last Year' in header else 'current'
            if 'Variance' in header:
                a, b = amounts[period]['current'], amounts[period]['last_month']
                row.append(a - b if a is not None and b is not None else None)
            else:
                row.append(amounts[period][metric])
            last = period, metric
        self.add(row, source_row)


def profile_for(statement):
    name = statement.get('department_name') or statement.get('scope_labels', {}).get('department_id') or ''
    if statement.get('report_scope') == 'CATERING':
        location = statement.get('scope_labels', {}).get('location_id', '')
        heading = 'PROJECT CATERING DEPARTEMEN'
        if location:
            heading += ' — ' + str(location).upper()
        return 'PROJECT', statement.get('template_title') or heading
    key = department_key(name) or {'room': 'FO', 'pool': 'SWP', 'utilities': 'UTILITY', 'utility': 'UTILITY'}.get(normalized(name))
    if key == 'FO': return 'ROOM', 'ROOM DIVISION DEPARTEMEN'
    if key == 'FB': return 'FB', 'F&B DIVISION DEPARTEMEN'
    if key == 'SWP': return 'POOL', 'SWIMMING POOL DEPARTEMEN'
    if key == 'UTILITY': return 'UTILITY', 'UTILITIES'
    return 'OVERHEAD', (name.upper() + ' DEPARTEMEN') if name else 'UNASSIGNED DEPARTEMEN'


def account_label(account):
    return re.sub(r'^\s*(FO|FBS|FBP|FB|HK|LDY|SWP|A&G|ACC|H&R|HR|S&M|PMC|BOD)\s*[-–—]\s*', '', account['account_name'], flags=re.I).strip()


def nonzero(account):
    return account.get('has_posted_activity') or any(v not in (None, 0) for p in account['periods'].values() for v in p.values())


def detail_rows(statement, title, as_of):
    profile, heading = profile_for(statement)
    rows = TemplateRows(statement, profile, heading, as_of)
    source = rows.template_profile['rows']
    labels = {int(i): record['cells'].get('A', {}).get('label', '') for i, record in source.items() if int(i) >= 7}
    members = statement.get('related_accounts', [])
    groups = {
        'revenue': [a for a in members if a['category'] == 'REVENUE' and not service_charge(a)],
        'sc_revenue': [a for a in members if a['category'] == 'REVENUE' and service_charge(a)],
        'cost': [a for a in members if a['category'] == 'COST_OF_REVENUE'],
        'payroll': [a for a in members if a['category'] in ('OPERATING_PAYROLL', 'OVERHEAD_PAYROLL') and not service_charge(a)],
        'sc_payroll': [a for a in members if a['category'] in ('OPERATING_PAYROLL', 'OVERHEAD_PAYROLL') and service_charge(a)],
        'expense': [a for a in members if a['category'] not in ('REVENUE', 'COST_OF_REVENUE', 'OPERATING_PAYROLL', 'OVERHEAD_PAYROLL')],
    }
    section, slots, section_rows = None, {}, {}
    totals = {}
    for index, label in labels.items():
        key = normalized(label)
        if not key: continue
        if key in ('roomstatistic',): section = 'statistics'; continue
        if key in ('revenue', 'foodbeveragerevenue'): section = 'revenue'; continue
        if key in ('foodbeveragecost',): section = 'cost'; continue
        if key == 'payrollrelatedexpenses': section = 'payroll'; continue
        if key in ('otherexpenses', 'energycost'): section = 'expense'; continue
        role = None
        if key in ('netrevenuewithoutsc',): role = 'revenue'
        elif key in ('netrevenuewithsc',): role = 'all_revenue'
        elif key in ('otherrevenueservicecharge',): role = 'sc_revenue'
        elif key in ('totalfoodbeveragecost',): role = 'cost'
        elif 'totalpayroll' in key and 'withoutsc' in key: role = 'payroll'
        elif key == 'servicechargedistribution': role = 'sc_payroll'
        elif 'totalpayroll' in key and 'withsc' in key: role = 'all_payroll'
        elif key in ('totalotherexpenses', 'totalenergycost'): role = 'expense'
        elif key == 'grossprofit': role = 'gross'
        elif key == 'grossoperatingincomeprofitloss': role = 'net'
        elif key == 'totalrevenue': role = 'all_revenue'
        if role:
            totals[index] = role
            if role in ('revenue', 'cost', 'payroll', 'expense'): section_rows.setdefault(role, index)
        elif section in ('revenue', 'cost', 'payroll', 'expense'):
            slots[index] = section
    assignments = {index: [] for index in slots}
    unassigned = {kind: [] for kind in ('revenue', 'cost', 'payroll', 'expense')}
    for kind in unassigned:
        for account in groups[kind]:
            name = normalized(account_label(account))
            candidates = [i for i, section in slots.items() if section == kind]
            match = next((i for i in candidates if normalized(labels[i]) == name), None)
            if match is None and kind == 'payroll':
                benefit = re.search(r'benefit|tunjangan|bpjs|thr\b|bonus', account_label(account), re.I)
                salary = re.search(r'salar|wages|gaji|casual', account_label(account), re.I)
                target = 'employeebenefit' if benefit else 'salarieswages' if salary else None
                match = next((i for i in candidates if normalized(labels[i]) == target), None)
            if match is None and kind == 'cost':
                code = account['account_code']
                target = 'foodcost' if code == '500-100-100' or 'makanan' in name else 'beveragecost' if code == '500-100-102' or 'minuman' in name else 'otherscost'
                match = next((i for i in candidates if normalized(labels[i]) == target), None)
            if match is None and kind == 'revenue':
                aliases = {'pendapatankamar': 'roomsales', 'roomrevenue': 'roomsales',
                           'pendapatanmakanan': 'foodrevenue', 'pendapatanminuman': 'beveragerevenue',
                           'pendapatanlaundry': 'laundry', 'pendapatankolamrenang': 'swimmingpool'}
                match = next((i for i in candidates if normalized(labels[i]) == aliases.get(name)), None)
            (assignments[match] if match is not None else unassigned[kind]).append(account)
    sums = {kind: values(statement, accounts_) for kind, accounts_ in groups.items()}
    sums['all_revenue'] = combine((1, sums['revenue']), (1, sums['sc_revenue']))
    if profile == 'UTILITY':
        sums['all_revenue'] = rows.revenue
    sums['all_payroll'] = combine((1, sums['payroll']), (1, sums['sc_payroll']))
    sums['gross'] = combine((1, sums['all_revenue']), (-1, sums['cost']))
    sums['net'] = combine((1, sums['gross']), (-1, sums['all_payroll']), (-1, sums['expense']))
    stats = {r['key']: r for r in (statement.get('statistics') or {}).get('rows', [])}
    stats_keys = {'totalroomavailable': 'ROOM_AVAILABLE', 'totalroomsaleable': 'ROOM_SALEABLE',
                  'totalroomoccupied': 'ROOM_OCCUPIED', 'percentageofoccupancy': 'OCCUPANCY',
                  'averageroomraterp': 'ADR', 'numberofguest': 'GUESTS'}
    empty = {p: {m: None for m in METRICS} for p in PERIODS}
    detail_style = next(iter(slots), 8)
    emitted = set()
    # Unusual real accounts never disappear just because the reference has no slot.
    def extras(kind, before):
        if kind in emitted: return
        emitted.add(kind)
        missing = unassigned[kind]
        if missing and kind not in section_rows:
            missing = [a for a in missing if nonzero(a)]
            if missing:
                rows.add([{'revenue': 'REVENUE', 'cost': 'COST OF SALES', 'payroll': 'Payroll & Related Expenses', 'expense': 'Other Expenses'}[kind]], before)
        for account in missing:
            rows.line('   ' + account['account_name'], values(statement, [account]), detail_style)
        if missing and kind not in section_rows:
            rows.line('Total ' + {'revenue': 'Revenue', 'cost': 'Cost of Sales', 'payroll': 'Payroll', 'expense': 'Other Expenses'}[kind], values(statement, missing), before)
    for index in range(7, max(labels) + 1):
        label = labels.get(index, '')
        key = normalized(label)
        if key == 'payrollrelatedexpenses':
            for kind in ('revenue', 'cost'):
                if kind not in section_rows: extras(kind, index)
        role = totals.get(index)
        if role in ('revenue', 'cost', 'payroll', 'expense'): extras(role, index)
        if role:
            base = sums['revenue'] if role in ('revenue', 'sc_revenue', 'payroll', 'cost') else sums['sc_revenue'] if role == 'sc_payroll' else sums['all_revenue']
            rows.line(label, sums[role], index, denominator=base)
        elif index in slots:
            base = sums['revenue'] if slots[index] in ('revenue', 'payroll') else sums['all_revenue']
            rows.line(label, values(statement, assignments[index]), index, denominator=base)
        elif key in stats_keys:
            item = stats.get(stats_keys[key])
            rows.line(label, item['periods'] if item else empty, index, statistic=True)
        else:
            rows.add([label] if label else [], index)
    return rows


def utility_account(account):
    return normalized(account_label(account)) in {
        'electricity', 'listrik', 'listrikgassolar', 'water', 'air', 'gaslpg', 'gas',
        'lpg', 'solar', 'otherfuel', 'bahanbakarlain', 'sewage',
    } and account['category'] not in ('REVENUE', 'COST_OF_REVENUE', 'OPERATING_PAYROLL', 'OVERHEAD_PAYROLL')


def summary_schedule(statement, title, groups, as_of):
    if statement.get('report_scope') == 'CATERING':
        rows = TemplateRows(statement, 'PROJECT', title, as_of)
        for item in statement.get('presentation_rows', []):
            if item['kind'] != 'detail':
                rows.line(item['label'], item['periods'], 82 if item['kind'] == 'subtotal' else 80)
        return rows
    hotel_only = statement.get('report_scope') == 'HOTEL'
    rows = TemplateRows(statement, 'SUMMARY_HOTEL' if hotel_only else 'SUMMARY', title, as_of)
    root_members = statement.get('related_accounts', [])
    buckets = {key: [] for key in ('room', 'fb', 'other', 'rental', 'project', 'ag', 'sm', 'pmc', 'energy')}
    for group in groups:
        if group.get('report_scope') == 'CATERING': bucket = 'project'
        else:
            key = department_key(group.get('department_name'))
            bucket = {'FO':'room','HK':'room','FB':'fb','AG':'ag','ACC':'ag','HR':'ag','BOD':'ag','SM':'sm','PMC':'pmc'}.get(key,'other')
        for account in group.get('related_accounts', []):
            target = bucket
            if group.get('report_scope') != 'CATERING' and utility_account(account): target = 'energy'
            if account['category'] == 'REVENUE' and re.search(r'rental|sewa',account['account_name'],re.I): target='rental'
            buckets[target].append(account)
    def aggregate(bucket_names, category):
        return values(statement, [a for b in bucket_names for a in buckets[b] if category(a)])
    revenue = lambda a:a['category']=='REVENUE' and not service_charge(a)
    payroll = lambda a:a['category'] in ('OPERATING_PAYROLL','OVERHEAD_PAYROLL') and not service_charge(a)
    sc_payroll = lambda a:a['category'] in ('OPERATING_PAYROLL','OVERHEAD_PAYROLL') and service_charge(a)
    cost = lambda a:a['category']=='COST_OF_REVENUE'
    expense = lambda a:a['category'] in ('OPERATING_EXPENSE','OVERHEAD_EXPENSE')
    op=('room','fb','other','rental','project'); overhead=('ag','sm','pmc','energy')
    amounts={
        'revenue':values(statement,[a for a in root_members if revenue(a)]),
        'sc_revenue':values(statement,[a for a in root_members if a['category']=='REVENUE' and service_charge(a)]),
        'cost':values(statement,[a for a in root_members if cost(a)]),
        'op_payroll':aggregate(op,payroll),'op_sc':aggregate(op,sc_payroll),'op_expense':aggregate(op,expense),
        'oh_payroll':aggregate(overhead,payroll),'oh_sc':aggregate(overhead,sc_payroll),'oh_expense':aggregate(overhead,expense),
        'under':values(statement,[a for a in root_members if a['category']=='UNDER_EXPENSE']),
    }
    amounts['all_revenue']=combine((1,amounts['revenue']),(1,amounts['sc_revenue']))
    amounts['op_all_payroll']=combine((1,amounts['op_payroll']),(1,amounts['op_sc']))
    amounts['oh_all_payroll']=combine((1,amounts['oh_payroll']),(1,amounts['oh_sc']))
    amounts['op_costs']=combine((1,amounts['op_all_payroll']),(1,amounts['op_expense']))
    amounts['department_income']=combine((1,amounts['all_revenue']),(-1,amounts['cost']),(-1,amounts['op_costs']))
    amounts['overhead_costs']=combine((1,amounts['oh_all_payroll']),(1,amounts['oh_expense']))
    # Root controls use the report's complete categories, including unassigned activity.
    all_payroll=values(statement,[a for a in root_members if a['category'] in ('OPERATING_PAYROLL','OVERHEAD_PAYROLL')])
    all_expenses=values(statement,[a for a in root_members if expense(a)])
    amounts['gop']=combine((1,amounts['all_revenue']),(-1,amounts['cost']),(-1,all_payroll),(-1,all_expenses))
    amounts['nop']=combine((1,amounts['gop']),(-1,amounts['under']))
    section, is_overhead = None, False
    displayed = []
    stats={r['key']:r for r in (statement.get('statistics') or {}).get('rows',[])}
    stat_keys={'totalroomavailable':'ROOM_AVAILABLE','totalroomsaleable':'ROOM_SALEABLE','totalroomoccupied':'ROOM_OCCUPIED','percentageofoccupancy':'OCCUPANCY','averageroomraterp':'ADR','numberofguest':'GUESTS'}
    empty={p:{m:None for m in METRICS} for p in PERIODS}
    for index in range(7,max(map(int,rows.template_profile['rows']))+1):
        label=rows.template_profile['rows'].get(str(index),{}).get('cells',{}).get('A',{}).get('label','')
        key=normalized(label)
        if key=='overheaddepartments':is_overhead=True
        headings={'revenue':'revenue','costofsales':'cost','payrollandrelatedexpenses':'payroll','otherexpenses':'expense','departmentalincome':'income','otherdeductionsheadoffice':'under'}
        if key in headings:
            section = headings[key]
            displayed = []
            rows.add([label], index)
            continue
        totals={'netrevenuewithoutservicecharge':'revenue','netrevenuewithservicecharge':'all_revenue','totalcostofsales':'cost',
            'totalotherexpenses':'oh_expense' if is_overhead else 'op_expense','totaldeptcostandexpenses':'op_costs','totaldepartmentalincome':'department_income',
            'totalundistributeddepartments':'overhead_costs','grossoperatingprofit':'gop','totalotherdeductionsheadoffice':'under','nettoperatingprofit':'nop'}
        role=totals.get(key)
        if 'totalpayroll' in key:
            role=('oh_' if is_overhead else 'op_')+('payroll' if 'withoutsc' in key else 'all_payroll')
        if key=='servicecharge':
            if section=='income':
                value = combine((1,amounts['sc_revenue']),(-1,amounts['op_sc']))
                displayed.append(value)
                rows.line(label,value,index)
                continue
            role='sc_revenue' if section=='revenue' else None
        if key=='servicechargeexpenses':role='oh_sc' if is_overhead else 'op_sc'
        if role:
            if role in ('revenue', 'cost', 'op_payroll', 'oh_payroll', 'op_expense', 'oh_expense', 'department_income'):
                difference = combine((1, amounts[role]), *[(-1, value) for value in displayed])
                if any(v not in (None, 0) for period in difference.values() for v in period.values()):
                    rows.line('   Other / unassigned ' + section, difference, index)
            rows.line(label,amounts[role],index,denominator=amounts['sc_revenue'] if role in ('oh_sc','op_sc') else amounts['all_revenue']);continue
        if key in stat_keys:
            rows.line(label,stats.get(stat_keys[key],{}).get('periods',empty),index,statistic=True);continue
        names={'room':'room','rooms':'room','foodandbeverage':'fb','otheroperateddepartements':'other','otheroperateddepartement':'other','rentalsotherincome':'rental','projectcateringincome':'project','projectcatering':'project',
               'administrationgeneral':'ag','salesmarketing':'sm','pomec':'pmc','energycost':'energy'}
        bucket=names.get(key)
        if bucket and section in ('revenue','cost','payroll','expense','income'):
            selected=tuple([bucket])
            if section=='revenue': value=aggregate(selected,revenue)
            elif section=='cost': value=aggregate(selected,cost)
            elif section=='payroll': value=aggregate(selected,payroll)
            elif section=='expense': value=aggregate(selected,expense)
            else:
                value=combine((1,aggregate(selected,revenue)),(-1,aggregate(selected,cost)),(-1,aggregate(selected,payroll)),(-1,aggregate(selected,expense)))
            displayed.append(value)
            rows.line(label,value,index);continue
        if section=='under' and key and key not in headings:
            aliases={'directorexpenses':r'director|direksi|bod','pajakpendapatanbungabank':r'pajak.*bunga','bebanbunga':r'beban.*bunga|interest','biayakorporasi':r'korporasi|corporat','biayalainlainnya':r'.*'}
            if key in aliases:
                match=[a for a in root_members if a['category']=='UNDER_EXPENSE' and re.search(aliases[key],a['account_name'],re.I)]
                if key=='biayalainlainnya':match=[a for a in match if not re.search(r'director|direksi|bod|pajak.*bunga|beban.*bunga|interest|korporasi|corporat',a['account_name'],re.I)]
                rows.line(label,values(statement,match),index);continue
        rows.add([label] if label else [],index)
    # Hotel's source schedule ends at GOP. Include real under-expense evidence so
    # the final export still exposes the complete NOP when such postings exist.
    if hotel_only and any(v not in (None,0) for p in amounts['under'].values() for v in p.values()):
        rows.line('OTHER DEDUCTIONS',amounts['under'],73)
        rows.line('NETT OPERATING PROFIT',amounts['nop'],73)
    return rows

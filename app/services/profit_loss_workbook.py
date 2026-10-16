"""Template PL REV layout, using the report's authorized, computed figures.

No accounting reclassification, allocation, or source correction happens here.
Missing comparisons remain blank. Every posting account stays in its configured
P&L category, including accounts that have no activity in this scope.
"""
from decimal import Decimal
import re

ZERO = Decimal('0')
PERIODS = ('MTD', 'YTD')
METRICS = ('current', 'budget', 'last_month', 'last_year')
EXPENSE_ORDER = (
    'Transportasi dan Perjalanan Dinas', 'Pakaian seragam', 'Entertainment',
    'Alat Tulis Kantor (ATK)', 'Kebersihan dan Pest Control',
    'Perbaikan dan Perawatan Kendaraan', 'Perbaikan Peralatan Operasional',
    'Koran,Telepone,TV dan Internet', 'Alat Pemadam dan Keselamatan',
    'Pajak Kendaraan', 'Pelatihan / Training', 'Pajak Iklan',
    'Asuransi Gedung/Kendaraan', 'Pajak Bumi dan Bangunan',
    'Listrik/Gas/Solar', 'Air', 'Sewa Peralatan/Kendaraan/Transportasi',
    'Asuransi Kontrak Kerja', 'Pemeliharaan Taman', 'Alat & Perlengkapan',
    'Iklan,Promosi dan Marketing', 'Perangkat Lunak/Keras Komputer',
    'Biaya Admin Bank', 'Laundry dan Dry Cleaning', 'Perbaikan Gedung',
    'Kurir dan Post', 'Legal/Audit Fee', 'Donasi',
    'Recruitment/Medical check up/Housing', 'Sosial/Olahraga/Rekreasi',
    'Operasional Lapangan - Project', 'Kelebihan/Kekurangan Transaksi',
    'Biaya Pra Operasi Project', 'Penyusutan aktiva tetap',
    'Beban amortisasi HGB', 'Perbaikan Air Conditioning',
    'Travel Agents Commissions', 'Perbaikan Elevator',
    'Material Cleaning Supplies', 'Maintenance Hotel System (IHS)',
    'Contract Service', 'Lain-lain', 'Alat Tulis Kantor',
    'Telepon dan Internet', 'Transportasi', 'Biaya Operasional Direksi',
    'Beban Admin lainnya',
)


def normalized(value):
    return re.sub(r'[^a-z0-9]', '', value.casefold())


def service_charge(account):
    # Only identifiable P&L accounts. Never infer an expense from a liability,
    # or split a combined "Salary, Wages & Service Charge" payroll account.
    name = account['account_name'].strip().casefold()
    return (name.startswith(('service charge', 'beban service charge', 'pendapatan service charge',
                             'distribusi service charge'))
            and not re.search(r'\b(salary|salaries|wages|gaji)\b', name))


def accounts(statement, *categories):
    return [a for a in statement.get('related_accounts', []) if a['category'] in categories]


def values(statement, members):
    """Sum four independent comparisons, never add monthly rates or variances."""
    result = {}
    reference = next(iter(statement.get('presentation_rows', [])), None)
    for period in PERIODS:
        result[period] = {}
        for metric in METRICS:
            unavailable = (reference is not None and reference['periods'][period][metric] is None)
            entries = [a['periods'][period][metric] for a in members]
            result[period][metric] = None if unavailable or any(v is None for v in entries) else sum(entries, ZERO)
    return result


def combine(*terms):
    return {p: {m: None if any(v[p][m] is None for _, v in terms)
                     else sum((sign * v[p][m] for sign, v in terms), ZERO)
                for m in METRICS} for p in PERIODS}


class StatementRows(list):
    """Rows with print styles. Kept compatible with the normal XLSX writer."""
    def __init__(self, statement, title, as_of):
        super().__init__()
        self.styles = {}
        self.percent_rows = set()
        self.statement = statement
        self.revenue = values(statement, accounts(statement, 'REVENUE'))
        self.extend([
            ['PT. Mutiara Merdeka Hotel'], ['INCOME AND EXPENDITURE ACCOUNT'],
            [title], [str(as_of)], [],
            ['Name', 'MTD Current', '%', 'MTD Budget', '%', 'MTD Last Month', '%',
             'MTD Last Year', '%', 'MTD Variance vs Last Month',
             'YTD Current', 'YTD Budget', 'YTD Last Month', 'YTD Last Year',
             'YTD Variance vs Last Month'],
        ])
        self.styles.update({1: 'title', 2: 'title', 3: 'title', 6: 'header'})

    def statistics(self):
        statistics = self.statement.get('statistics') or {}
        if not statistics.get('rows'):
            return
        self.heading('OPERATING STATISTICS')
        for item in statistics['rows']:
            unit = item.get('unit')
            label = item['label'] + (f' ({unit})' if unit and item['format'] != 'percent' else ' (%)' if item['format'] == 'percent' else '')
            row = [label]
            for metric in METRICS:
                row += [item['periods']['MTD'][metric], None]
            m, y = item['periods']['MTD'], item['periods']['YTD']
            row += [m['current']-m['last_month'] if m['current'] is not None and m['last_month'] is not None else None]
            row += [y[k] for k in METRICS]
            row += [y['current']-y['last_month'] if y['current'] is not None and y['last_month'] is not None else None]
            self.append(row)
            if item['format'] == 'percent':
                self.percent_rows.add(len(self))

    def heading(self, label):
        self.append([])
        self.append([label])
        self.styles[len(self)] = 'section'

    def line(self, label, amounts, style=None):
        mtd, ytd = amounts['MTD'], amounts['YTD']
        row = [label]
        for metric in METRICS:
            amount, revenue = mtd[metric], self.revenue['MTD'][metric]
            row += [amount, amount / revenue if amount is not None and revenue not in (None, ZERO) else None]
        row += [mtd['current'] - mtd['last_month'] if mtd['last_month'] is not None and mtd['current'] is not None else None]
        row += [ytd[m] for m in METRICS]
        row += [ytd['current'] - ytd['last_month'] if ytd['last_month'] is not None and ytd['current'] is not None else None]
        self.append(row)
        if style:
            self.styles[len(self)] = style

    def detail(self, members):
        order = {normalized(name): i for i, name in enumerate(EXPENSE_ORDER)}
        for account in sorted(members, key=lambda a: (order.get(normalized(a['account_name']), len(order)), a['account_code'])):
            self.line('   ' + account['account_name'], values(self.statement, [account]))


def department_rows(statement, title, as_of):
    rows = StatementRows(statement, title, as_of)
    rows.statistics()
    revenue = accounts(statement, 'REVENUE')
    sc_revenue = [a for a in revenue if service_charge(a)]
    rows.heading('REVENUE')
    rows.detail([a for a in revenue if not service_charge(a)])
    rows.line('Net Revenue Without Service Charge', values(statement, [a for a in revenue if not service_charge(a)]), 'total')
    rows.detail(sc_revenue)
    rows.line('Service Charge Revenue', values(statement, sc_revenue))
    rows.line('Net Revenue With Service Charge', rows.revenue, 'total')
    rows.heading('COST OF SALES')
    cogs = values(statement, accounts(statement, 'COST_OF_REVENUE'))
    rows.detail(accounts(statement, 'COST_OF_REVENUE'))
    rows.line('Total Cost of Sales', cogs, 'total')
    rows.line('Gross Profit', combine((1, rows.revenue), (-1, cogs)), 'total')
    deductions = [(1, rows.revenue), (-1, cogs)]
    for category, title_, total in (
        ('OPERATING_PAYROLL', 'PAYROLL AND RELATED EXPENSES', 'Total Payroll & Related Expenses With Service Charge'),
        ('OPERATING_EXPENSE', 'OTHER OPERATING EXPENSES', 'Total Other Operating Expenses'),
        ('OVERHEAD_PAYROLL', 'OVERHEAD PAYROLL AND RELATED EXPENSES', 'Total Overhead Payroll With Service Charge'),
        ('OVERHEAD_EXPENSE', 'OTHER OVERHEAD EXPENSES', 'Total Other Overhead Expenses'),
        ('UNDER_EXPENSE', 'OTHER DEDUCTIONS / UNDER EXPENSES', 'Total Other Deductions'),
    ):
        rows.heading(title_)
        members = accounts(statement, category)
        if category.endswith('PAYROLL'):
            regular = [a for a in members if not service_charge(a)]
            rows.detail(regular)
            rows.line('Total Payroll & Related Expenses Without Service Charge', values(statement, regular), 'total')
            rows.line('Service Charge Distribution', values(statement, [a for a in members if service_charge(a)]))
            rows.detail([a for a in members if service_charge(a)])
        else:
            rows.detail(members)
        amount = values(statement, members)
        rows.line(total, amount, 'total')
        deductions.append((-1, amount))
        if category in ('OPERATING_EXPENSE', 'OVERHEAD_EXPENSE', 'UNDER_EXPENSE'):
            label = {'OPERATING_EXPENSE': 'Gross Operating Income / Profit / Loss',
                     'OVERHEAD_EXPENSE': 'Gross Operating Profit / Loss',
                     'UNDER_EXPENSE': 'Net Operating Profit / Loss'}[category]
            rows.line(label, combine(*deductions), 'grand')
    return rows


def summary_rows(statement, title, groups, as_of):
    rows = StatementRows(statement, title, as_of)
    # Same header/subtotal rows as the P&L page; departmental detail belongs
    # exclusively on its own sheet. Use computed rows, not new allocations.
    for row in statement.get('presentation_rows', []):
        if row['kind'] == 'detail':
            continue
        rows.line(row['label'], row['periods'], 'grand' if row['kind'] == 'subtotal' else 'total')
    return rows


def workbook_sheets(report):
    as_of = report['as_of_date']
    scope = report['report_scope']
    used, sheets = set(), []

    def add(title, rows):
        name = re.sub(r'[\\/*?:\[\]]', '-', title).strip(" '")[:31] or 'Report'
        base, n = name, 1
        while name.casefold() in used:
            n += 1
            suffix = f' ({n})'
            name = base[:31-len(suffix)] + suffix
        used.add(name.casefold())
        sheets.append((name, rows))

    groups = report.get('group_reports', [])
    add('Summary', summary_rows(report, f'{scope.title()} Income Statement', groups, as_of))
    for unit in report.get('unit_reports', []):
        unit_groups = [g for g in groups if g['scope']['business_unit_id'] == unit['scope']['business_unit_id']]
        # A scoped export already has this unit's summary as its first sheet.
        if scope == 'CONSOLIDATED' and len(report['unit_reports']) > 1:
            add(f"Summary {unit['title']}", summary_rows(unit, unit['title'], unit_groups, as_of))
    # Stable Hotel order is independent of this month's revenue or erroneous
    # postings. Catering keeps its existing location order pending its design.
    from app.services.profit_loss_relevance import department_sort
    ordered = sorted(enumerate(groups), key=lambda pair: (
        0 if 'department_name' in pair[1] else 1,
        department_sort(pair[1]) if 'department_name' in pair[1] else (0, pair[0], '')))
    for _, group in ordered:
        add(group['title'], department_rows(group, group['title'], as_of))
    return sheets

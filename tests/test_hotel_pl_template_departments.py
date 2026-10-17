from copy import deepcopy
from decimal import Decimal

from app.services.profit_loss_workbook import department_rows


def amounts(value):
    return {p: {'current': Decimal(value), 'budget': None, 'last_month': Decimal(value), 'last_year': None}
            for p in ('MTD', 'YTD')}


def statement(department, members):
    return {'department_name': department, 'scope_labels': {},
            'presentation_rows': [{'periods': amounts(0)}],
            'related_accounts': [dict(account_id=i, account_code=str(i), account_name=name,
                                      category=category, periods=amounts(value))
                                 for i, (name, category, value) in enumerate(members, 1)],
            'statistics': {'rows': [{'label': 'Total Room Occupied', 'format': 'number', 'unit': 'Rooms',
                                     'periods': amounts(4)}]}}


def test_room_statistics_only_on_room_schedule_and_fb_gets_own_heading():
    source = statement('Front Office', [('Room sales', 'REVENUE', 100)])
    room = department_rows(source, 'Hotel Room', '2026-10-31')
    assert any(r and r[0] == 'ROOM STATISTIC' for r in room)
    assert any(r and r[0] == 'ROOM REVENUE' for r in room)
    fb = statement('Food and Beverage', [('Food sales', 'REVENUE', 100), ('Food cost', 'COST_OF_REVENUE', 20), ('Unused expense', 'OPERATING_EXPENSE', 0)])
    before = deepcopy(fb)
    rows = department_rows(fb, 'Hotel F&B', '2026-10-31')
    labels = [r[0] for r in rows if r]
    assert 'FOOD & BEVERAGE REVENUE' in labels and 'FOOD & BEVERAGE COST' in labels
    assert 'Total Room Occupied (Rooms)' not in labels
    assert any(r and r[0].strip() == 'Unused expense' and r[1] == 0 for r in rows)
    assert next(r for r in rows if r and r[0] == 'Net Operating Profit / Loss')[1] == 80
    assert fb == before


def test_overhead_omits_inapplicable_sections_without_hiding_real_revenue():
    source = statement('Admin and General', [('Salaries', 'OVERHEAD_PAYROLL', 10), ('Office supplies', 'OVERHEAD_EXPENSE', 20)])
    rows = department_rows(source, 'Hotel A&G', '2026-10-31')
    labels = [r[0] for r in rows if r]
    assert 'REVENUE' not in labels and 'COST OF SALES' not in labels
    assert 'OPERATING STATISTICS' not in labels
    assert 'OVERHEAD PAYROLL AND RELATED EXPENSES' in labels
    assert next(r for r in rows if r and r[0] == 'Net Operating Profit / Loss')[1] == -30
    source['related_accounts'].append(dict(account_id=9, account_code='400', account_name='Actual miscellaneous revenue', category='REVENUE', periods=amounts(5)))
    rows = department_rows(source, 'Hotel A&G', '2026-10-31')
    assert any(r and r[0].strip() == 'Actual miscellaneous revenue' and r[1] == 5 for r in rows)
    assert next(r for r in rows if r and r[0] == 'Net Operating Profit / Loss')[1] == -25

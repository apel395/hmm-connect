"""Hotel template contract: actual data, comparison columns and original layout."""
from copy import deepcopy
from decimal import Decimal
from io import BytesIO

from openpyxl import load_workbook
from app.services.profit_loss_template import detail_rows, summary_schedule, layouts
from app.services.xlsx_export import build_xlsx
from test_hotel_pl_template_departments import statement, amounts


def hotel(name, members):
    result = statement(name, members)
    result['report_scope'] = 'HOTEL'
    result['statistics'] = {'rows': []}
    return result


def test_room_exact_template_order_and_statistics_do_not_use_food_covers():
    source = hotel('Front Office', [('Room Sales', 'REVENUE', 1000), ('FO - Casual Worker', 'OPERATING_PAYROLL', 80)])
    source['statistics']['rows'] = [dict(key='FOOD_COVERS', periods=amounts(999)), dict(key='ROOM_OCCUPIED', periods=amounts(85))]
    before = deepcopy(source)
    rows = detail_rows(source, 'Front Office', '2026-01-31')
    expected = [r['cells'].get('A', {}).get('label', '') for i, r in layouts()['ROOM']['rows'].items() if int(i) >= 7]
    assert [r[0] if r else '' for r in rows[6:]] == expected
    assert next(r[1] for r in rows if r and r[0].strip() == 'Total Room Occupied') == 85
    assert next(r[1] for r in rows if r and r[0].strip() == 'Number Of Guest') is None
    assert next(r[1] for r in rows if r and r[0].strip() == 'Salaries & Wages') == 80
    assert rows[3] == ['01 - 2026']
    assert source == before


def test_fb_columns_real_account_extensions_and_service_charge_once():
    source = hotel('Food and Beverage', [('Food Revenue', 'REVENUE', 1000), ('Service Charge Revenue', 'REVENUE', 100), ('Food Cost', 'COST_OF_REVENUE', 200), ('FB - Salaries', 'OPERATING_PAYROLL', 80), ('Service Charge Distribution', 'OPERATING_PAYROLL', 60), ('New actual expense', 'OPERATING_EXPENSE', 30)])
    rows = detail_rows(source, 'FB', '2026-01-31')
    assert len(rows.headers) == 13
    final = next(r for r in rows if r and r[0] == 'Gross Operating Income / Profit / Loss')
    assert final[1] == 730 and final[rows.headers.index('YTD Current')] == 730
    sc = next(r for r in rows if r and r[0] == 'Service Charge Distribution')
    assert sc[1:3] == [60, Decimal('0.6')]
    labels = [r[0] if r else '' for r in rows]
    assert labels.index('   New actual expense') < labels.index('Total Other Expenses')
    wb = load_workbook(BytesIO(build_xlsx([('FB', rows)])))
    sheet = wb.active
    assert sheet.freeze_panes == 'B7'
    assert sheet.sheet_view.zoomScale == 100
    assert sheet.row_dimensions[1].height == 30
    assert sheet.row_dimensions[6].height == 42
    assert sheet.sheet_view.showGridLines is False
    assert str(sheet.merged_cells) == "A1:M1 A2:M2 A3:M3 A4:M4"
    for row in sheet:
        for cell in row:
            assert cell.data_type != 'e'
            if cell.column > 1 and rows.headers[cell.column - 1] == '%' and cell.value is not None:
                assert '%' in cell.number_format


def test_hotel_summary_dept_subtotals_and_sc_bridge_reconcile():
    room = hotel('Front Office', [('Room Sales','REVENUE',1000),('Service Charge Revenue','REVENUE',100),('Salary','OPERATING_PAYROLL',80),('Service Charge Distribution','OPERATING_PAYROLL',60),('Actual expense','OPERATING_EXPENSE',20)])
    admin = hotel('Admin and General', [('Admin salary','OVERHEAD_PAYROLL',50),('Other deduction','UNDER_EXPENSE',10)])
    root = hotel('', [])
    root['related_accounts'] = room['related_accounts'] + admin['related_accounts']
    rows = summary_schedule(root, 'HOTEL', [room, admin], '2026-01-31')
    def value(label): return next(r[1] for r in rows if r and r[0] == label)
    assert value('TOTAL DEPARTMENTAL INCOME') == 940
    assert value('TOTAL UNDISTRIBUTED DEPARTMENTS') == 50
    assert value('GROSS OPERATING PROFIT') == 890
    assert value('NETT OPERATING PROFIT') == 880
    income_start = next(i for i,r in enumerate(rows) if r and r[0] == 'DEPARTMENTAL INCOME')
    income = rows[income_start + 1:]
    components = [r[1] for r in income[:5] if r and len(r)>1]
    assert sum(components) == 940


def test_utility_preserves_combined_actual_without_inventing_split():
    source = hotel('Utilities', [('Listrik/Gas/Solar','OPERATING_EXPENSE',100)])
    source['template_revenue'] = amounts(1000)
    rows = detail_rows(source, 'Utilities', '2026-01-31')
    assert next(r[1] for r in rows if r and r[0] == 'Total Energy Cost') == 100
    assert next(r[1] for r in rows if r and r[0] == 'Total Revenue') == 1000
    assert next(r[1] for r in rows if r and r[0] == '   Listrik/Gas/Solar') == 100


def test_summary_unassigned_actual_cost_is_explicit_before_total():
    # Show Rooms cost explicitly without creating an unassigned remainder.
    room = hotel('Front Office', [('Room Sales','REVENUE',1000), ('Unexpected room cost','COST_OF_REVENUE',20)])
    rows = summary_schedule(room, 'Hotel', [room], '2026-01-31')
    labels = [r[0] if r else '' for r in rows]
    residual = next(i for i,r in enumerate(rows) if r and r[0] == 'Rooms' and r[1] == 20)
    assert rows[residual][1] == 20
    assert residual < labels.index('TOTAL COST OF SALES')
    assert next(r[1] for r in rows if r and r[0] == 'GROSS OPERATING PROFIT') == 980


def test_zero_revenue_ownership_preserves_real_offsetting_evidence():
    from types import SimpleNamespace
    from app.services.profit_loss_relevance import related
    account = SimpleNamespace(id=1, account_number='400-100-102', account_name='Project Catering Revenue', account_type='REVENUE')
    report = {'scope_labels': {'business_unit_id':'Hotel','department_id':'Front Office'}}
    assert not related(account, report, {}, set())
    assert related(account, report, {}, {1})
    account.account_number = '400-OTHER'
    account.account_name = 'FO - Other Revenue'
    assert related(account, report, {}, set())

"""Presentation-only ownership of zero P&L accounts; never change postings.

Registered hotel revenue families and explicit department prefixes are display
rules, not allocations. Actual/budget evidence always overrides these defaults.
Unassigned and unknown/shared accounts remain visible for finance review.
"""
import re
from sqlalchemy import func
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.organization_access import effective_business_unit


def normalized(value):
    return re.sub(r'[^a-z0-9]', '', (value or '').casefold())


DEPARTMENTS = {
    'frontoffice': 'FO', 'rooms': 'FO', 'roomsdivision': 'FO',
    'foodandbeverage': 'FB', 'foodbeverage': 'FB',
    'housekeeping': 'HK', 'laundry': 'LDY', 'swimmingpool': 'SWP',
    'adminandgeneral': 'AG', 'administrativeandgeneral': 'AG',
    'accounting': 'ACC', 'humanresources': 'HR', 'salesandmarketing': 'SM',
    'pomec': 'PMC', 'boardofdirectors': 'BOD', 'boardofdirectur': 'BOD', 'bod': 'BOD',
}
PREFIXES = {'FO': 'FO', 'FBS': 'FB', 'FBP': 'FB', 'FB': 'FB', 'HK': 'HK',
            'LDY': 'LDY', 'SWP': 'SWP', 'A&G': 'AG', 'ACC': 'ACC',
            'H&R': 'HR', 'HR': 'HR', 'S&M': 'SM', 'PMC': 'PMC', 'BOD': 'BOD'}
# These exact registered revenue codes are also used by the January import.
REVENUE_DEPARTMENTS = {'400-100-100': 'FO', '400-100-101': 'FB',
                       '400-100-102': 'LDY', '400-100-103': 'SWP'}
DEPARTMENT_ORDER = ('FO', 'FB', 'SWP', 'LDY', 'HK', 'AG', 'ACC', 'HR', 'SM', 'PMC', 'BOD')


def department_key(name):
    return DEPARTMENTS.get(normalized((name or "").split(" / ",1)[0]))


def department_sort(group):
    name = group.get('department_name', '')
    key = department_key(name)
    if key in DEPARTMENT_ORDER:
        return (0, DEPARTMENT_ORDER.index(key), name.casefold())
    return (2 if not group.get('department_id') else 1, 0, name.casefold())


def scoped_usage(db, scope, as_of):
    """Gross posted evidence includes offsetting/zero-net activity in this scope."""
    query = db.query(JournalLine.account_id).join(JournalEntry).filter(
        JournalEntry.status == 'POSTED', JournalEntry.posting_date <= as_of,
        JournalEntry.reference_type.notin_(('OPENING_BALANCE', 'OPENING_BALANCE_ADJUSTMENT', 'PERIOD_CLOSE', 'YEAR_END')))
    for name, value in scope.items():
        if value is None:
            continue
        dimension = func.coalesce(getattr(JournalLine, name), getattr(JournalEntry, name))
        if name == 'business_unit_id':
            dimension = effective_business_unit(dimension, func.coalesce(JournalLine.location_id, JournalEntry.location_id))
        query = query.filter(dimension.is_(None) if name == 'department_id' and value == 0 else dimension == value)
    return {row[0] for row in query.distinct().all()}


def related(account, report, values, evidence):
    aid = account.id
    if aid in evidence or any(v.get(aid, 0) != 0 for p in values.values() for v in p.values()):
        return True
    labels = report.get('scope_labels', {})
    unit = normalized(labels.get('business_unit_id'))
    code = account.account_number
    # Unit-specific revenue families must not leak into another unit's zeros.
    if 'catering' in unit and (code == '400-100' or code.startswith('400-100-')):
        return False
    name = normalized(account.account_name)
    if 'hotel' in unit and (code == '400-110' or code.startswith('400-110-') or code == '400-200' or code.startswith('400-200-') or ('catering' in name and 'outsidecatering' not in name and 'outsitecatering' not in name)):
        return False
    dept = department_key(labels.get('department_id'))
    if dept is None:
        return True
    owner = REVENUE_DEPARTMENTS.get(code)
    if account.account_type in ('REVENUE', 'INCOME'):
        owner = owner or {'roomsales': 'FO', 'roomrebate': 'FO', 'pendapatankamar': 'FO',
            'foodrevenue': 'FB', 'beveragerevenue': 'FB', 'foodbeveragerevenue': 'FB',
            'pendapatanmakanan': 'FB', 'pendapatanminuman': 'FB', 'laundry': 'LDY',
            'swimmingpool': 'SWP'}.get(name)
    prefix = re.match(r'^\s*([A-Za-z&]+)\s*[-–—]\s*', account.account_name)
    if prefix:
        owner = PREFIXES.get(prefix[1].upper(), owner)
    if account.account_type in ("REVENUE", "INCOME") and owner is None:
        return False
    if code.startswith("500-100-") and owner is None and dept != "FB":
        return False
    return owner is None or owner == dept

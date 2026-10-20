"""MMH Hotel presentation defaults; never allocate or modify source postings."""
import re

SUPPORT_DEPARTMENTS = frozenset(('AG', 'ACC', 'HR', 'BOD'))
COMMON = SUPPORT_DEPARTMENTS
# Which department schedules may display an unused account. Actual and budget
# evidence always override these defaults in profit_loss_relevance.related.
EXPENSE_DEPARTMENTS = {
    '100': COMMON, '101': {'HR'}, '102': {'AG'}, '103': COMMON,
    '104': {'HK'}, '105': {'PMC'}, '106': {'PMC'}, '107': COMMON,
    '108': {'PMC'}, '109': {'AG'}, '110': {'HR'}, '111': {'SM'},
    '112': {'AG'}, '113': {'AG'}, '114': {'PMC'}, '115': {'PMC'},
    '116': {'AG'}, '117': {'AG'}, '118': {'PMC'}, '119': COMMON,
    '120': {'SM'}, '121': {'AG', 'ACC'}, '122': {'ACC'},
    '123': {'HK', 'LDY'}, '124': {'PMC'}, '125': COMMON,
    '126': {'AG', 'ACC'}, '127': {'AG'}, '128': {'HR'}, '129': {'HR'},
    '130': set(), '131': {'ACC'}, '132': set(), '133': COMMON,
    '134': {'AG'}, '135': {'PMC'}, '136': {'SM', 'FO'}, '137': {'PMC'},
    '138': {'HK'}, '140': {'AG'}, '141': {'AG'}, '999': COMMON,
}


def is_hotel_report(report):
    unit = str((report or {}).get('scope_labels', {}).get('business_unit_id') or '').casefold()
    return 'hotel' in unit or (report or {}).get('report_scope') == 'HOTEL'


def zero_account_departments(account):
    code = account.account_number
    if code.startswith('600-100-'): return COMMON
    if code.startswith('700-500-'): return EXPENSE_DEPARTMENTS.get(code[8:], frozenset())
    if code == '750-100-104': return {'BOD'}
    if code.startswith('750-100-'): return {'AG'}
    if code.startswith('760-100-'): return {'ACC'}
    return frozenset()


def owner_expense(account):
    if account.account_type != 'EXPENSE': return False
    if account.account_number == '750-100-104': return True
    return bool(re.search(r'\b(?:owner expenses?|biaya pemilik|beban pemilik|complimentary\s+(?:bod|direksi)|officer check.*\bbod)\b', account.account_name, re.I))

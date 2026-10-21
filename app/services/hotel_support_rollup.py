"""Hotel responsibility reports: Accounting plus HR form the A&G subtotal.

Legacy A&G postings are the accounting schedule, not a third cost department.
This is a read-only presentation rule; original journal dimensions are retained.
"""
from app.models.department import Department
from app.services.profit_loss_relevance import department_key


def source_scopes(service, scope, kind='PROFIT_LOSS'):
    cache = getattr(service, '_hotel_support_scope_cache', None)
    if cache is None:
        cache = service._hotel_support_scope_cache = {}
    key = (kind, tuple(sorted(scope.items())))
    if key not in cache:
        cache[key] = _source_scopes(service, scope, kind)
    return cache[key]


def _source_scopes(service, scope, kind):
    if kind != 'PROFIT_LOSS' or not service.hotel_support_rollup:
        return [scope]
    selected = service.db.get(Department, scope['department_id']) if scope['department_id'] else None
    if selected is None or department_key(selected.name) not in ('AG', 'ACC'):
        return [scope]
    from app.models.business_unit import BusinessUnit
    from app.services.profit_loss_delivery import unit_kind
    unit = service.db.get(BusinessUnit, selected.business_unit_id) if selected.business_unit_id else None
    if unit is None or unit_kind(unit) != 'HOTEL' or scope['business_unit_id'] not in (None, unit.id):
        return [scope]
    # Resolve registered IDs, never assume production IDs or cross unit boundaries.
    groups = {}
    for department in service.db.query(Department).filter(Department.business_unit_id == unit.id):
        groups.setdefault(department_key(department.name), []).append(department.id)
    if len(groups.get('ACC', [])) != 1 or len(groups.get('AG', [])) != 1:
        return [scope]
    keys = ('AG', 'ACC', 'HR') if department_key(selected.name) == 'AG' else ('AG', 'ACC')
    return [{**scope, 'business_unit_id': unit.id, 'department_id': did}
            for key in keys for did in groups.get(key, [])]


def department_ids(service, scope):
    return {s['department_id'] for s in source_scopes(service, scope)}


def is_rollup(service, scope, kind):
    selected = service.db.get(Department, scope['department_id']) if scope['department_id'] else None
    return bool(selected and department_key(selected.name) == 'AG'
                and len(source_scopes(service, scope, kind)) > 1)

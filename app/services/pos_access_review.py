"""Read-only explanation of POS permission and organization/menu visibility."""
from fastapi import HTTPException
from app.dependencies.authorization import has_permission, is_superuser
from app.api.v1.sales import sale_options, list_pos_products


def review_pos_access(db, user):
    result = {
        'user_id': user.id, 'username': user.username, 'is_active': user.is_active,
        'roles': sorted(role.name for role in user.roles), 'canonical_admin': is_superuser(user),
        'pos_permissions': {code: has_permission(user, code) for code in ('pos.view', 'pos.sell', 'pos.manage')},
        'scope': {field: getattr(user, field, None) for field in ('default_business_unit_id', 'default_location_id', 'location_id', 'default_department_id', 'department_id')},
        'locations': [], 'findings': [],
    }
    if not user.is_active:
        result['findings'].append('ACCOUNT_INACTIVE')
    if not result['pos_permissions']['pos.view']:
        result['findings'].append('POS_VIEW_PERMISSION_MISSING')
        return result
    options = sale_options(db, user)
    if not options['locations']:
        result['findings'].append('NO_ACCESSIBLE_ACTIVE_SALES_LOCATIONS')
    for location in options['locations']:
        row = {'id': location['id'], 'name': location['name'], 'catalog_type': location['catalog_type'], 'contexts': []}
        departments = [d for d in options['departments'] if d['location_id'] == location['id']]
        if location['catalog_type'] == 'HOTEL':
            departments = [d for d in departments if d['is_outlet'] and d['is_fnb_outlet']]
            if not departments:
                row['finding'] = 'NO_ACTIVE_FNB_OUTLET'
        # Include the optional Catering department context and each configured department.
        contexts = departments if location['catalog_type'] == 'HOTEL' else [None, *departments]
        for department in contexts:
            department_id = department['id'] if department else None
            try:
                menu = list_pos_products(location_id=location['id'], department_id=department_id,
                    transaction_type='INVOICE' if location['catalog_type'] == 'CATERING' else 'POS',
                    search=None, group_name=None, page=1, page_size=200, db=db, user=user)
                row['contexts'].append({'department_id': department_id, 'menu_count': menu['total_items'],
                    'first_page_available': sum(bool(p['sale_available']) for p in menu['items']),
                    'unavailable_reasons': sorted({p['unavailable_reason'] for p in menu['items'] if p.get('unavailable_reason')})})
            except HTTPException as exc:
                row['contexts'].append({'department_id': department_id, 'error': exc.detail, 'status': exc.status_code})
        result['locations'].append(row)
    if not any(row['catalog_type'] == 'CATERING' for row in result['locations']):
        result['findings'].append('NO_CATERING_LOCATION_IN_ACCOUNT_SCOPE')
    return result

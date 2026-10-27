"""Small POS setup over the existing Department/DepartmentOutlet master."""
import re
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from app.models.business_unit import BusinessUnit
from app.models.department import Department
from app.models.department_outlet import DepartmentOutlet
from app.models.location import Location
from app.models.location_department import LocationDepartment
from app.models.pos_operations import PosOutletPolicy, PosCashierSession
from app.models.sales_transaction import SalesTransaction
from app.services.organization_access import resolve_organization_access, department_scope
from app.services.activity_service import ActivityService


def is_food_beverage(department):
    if not department:
        return False
    def key(value):
        return re.sub(r'[^a-z]', '', (value or '').casefold().replace('&', 'and'))
    return key(department.name) in {'foodandbeverage', 'foodbeverage', 'fnb', 'fandb'} or key(department.code) in {'fnb', 'fandb'}


def hotel_location(db, user, location_id):
    resolve_organization_access(db, user, location_id=location_id)
    location = db.get(Location, location_id)
    unit = db.get(BusinessUnit, location.business_unit_id) if location else None
    if not location or not location.is_active or not unit or not unit.is_active or 'hotel' not in unit.name.casefold():
        raise HTTPException(422, 'Choose an active Hotel location')
    return location


def parents(db, location):
    return [d for d in db.query(Department).join(LocationDepartment, LocationDepartment.department_id == Department.id)
            .filter(LocationDepartment.location_id == location.id, Department.business_unit_id == location.business_unit_id,
                    Department.is_active.is_(True)).order_by(Department.name)
            if is_food_beverage(d) and not db.get(DepartmentOutlet, d.id)]


def list_outlets(db, user, location_id):
    location = hotel_location(db, user, location_id)
    roots = parents(db, location)
    rows = db.query(Department, DepartmentOutlet, PosOutletPolicy).join(DepartmentOutlet, DepartmentOutlet.department_id == Department.id).join(
        LocationDepartment, LocationDepartment.department_id == Department.id).outerjoin(PosOutletPolicy,
        (PosOutletPolicy.department_id == Department.id) & (PosOutletPolicy.location_id == location_id)).filter(
        LocationDepartment.location_id == location_id, DepartmentOutlet.parent_department_id.in_([p.id for p in roots]))
    assigned = department_scope(user)
    if assigned is not None:
        rows = rows.filter(Department.id == assigned)
    return {'parents': [{'id': p.id, 'name': p.name} for p in roots], 'outlets': [
        {'id': d.id, 'name': d.name, 'code': d.code, 'parent_department_id': link.parent_department_id,
         'is_active': d.is_active, 'order_mode': policy.order_mode if policy else None} for d, link, policy in rows.order_by(Department.name)]}


def save_outlet(db, user, data, outlet_id=None):
    # Reuse master-data permission; a cashier cannot create organization dimensions.
    from app.services.sales_transaction_service import SalesTransactionService as Sales
    Sales._require(user, 'admin.settings.manage')
    Sales._require(user, 'pos.view')
    location = hotel_location(db, user, data.location_id)
    if department_scope(user) is not None:
        raise HTTPException(403, 'Outlet setup requires location-level master-data access')
    root = next((p for p in parents(db, location) if p.id == data.parent_department_id), None)
    if not root:
        raise HTTPException(422, 'Choose Food & Beverage assigned to this Hotel location')
    db.query(Department).filter_by(id=root.id).with_for_update(key_share=True).one()
    row = db.query(Department).filter_by(id=outlet_id).with_for_update(key_share=True).first() if outlet_id else None
    if outlet_id:
        link = db.get(DepartmentOutlet, outlet_id)
        if not row or not link or link.parent_department_id != root.id or not db.query(LocationDepartment).filter_by(location_id=location.id, department_id=outlet_id).first():
            raise HTTPException(404, 'Outlet not found in this Food & Beverage department')
        # Department identity is shared master data. Do not edit another location indirectly.
        if db.query(LocationDepartment).filter(LocationDepartment.department_id == outlet_id, LocationDepartment.location_id != location.id).first():
            raise HTTPException(409, 'This outlet is shared across locations; edit it in Department Master')
        busy = db.query(PosCashierSession).filter_by(location_id=location.id, department_id=outlet_id, status='OPEN').first() or db.query(SalesTransaction).filter_by(location_id=location.id, department_id=outlet_id, status='DRAFT', transaction_type='POS').first()
        if busy:
            raise HTTPException(409, 'Close shifts and complete open orders before changing this outlet')
    duplicate = db.query(Department).filter((func.lower(Department.code) == data.code.lower()) | (func.lower(Department.name) == data.name.lower()))
    if row:
        duplicate = duplicate.filter(Department.id != row.id)
    if duplicate.first():
        raise HTTPException(409, 'Outlet code or name already exists. Choose a different three-letter code or name')
    before = {'name': row.name, 'code': row.code, 'is_active': row.is_active} if row else None
    try:
        if not row:
            row = Department(business_unit_id=location.business_unit_id)
            db.add(row)
        row.name, row.code, row.is_active = data.name, data.code, data.is_active
        db.flush()
        if not outlet_id:
            # Link only this location; do not inherit all parent locations.
            db.add(DepartmentOutlet(department_id=row.id, parent_department_id=root.id))
            db.add(LocationDepartment(location_id=location.id, department_id=row.id))
        policy = db.query(PosOutletPolicy).filter_by(location_id=location.id, department_id=row.id).first()
        old_mode = policy.order_mode if policy else None
        if not policy:
            policy = PosOutletPolicy(location_id=location.id, department_id=row.id)
            db.add(policy)
        policy.order_mode = data.order_mode
        db.flush()
        ActivityService.log(db=db, user=user, action='UPDATE' if outlet_id else 'CREATE', entity_type='POS_OUTLET', entity_id=row.id,
            summary=f'Configured Hotel F&B outlet {row.code}', details={'location_id': location.id, 'parent_department_id': root.id,
                'before': before, 'name': row.name, 'code': row.code, 'is_active': row.is_active,
                'previous_order_mode': old_mode, 'order_mode': policy.order_mode})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Outlet code or name was already used. Refresh and choose another code or name')
    db.info.pop('department_outlet_labels', None)
    return {'id': row.id, 'code': row.code, 'name': row.name, 'is_active': row.is_active,
            'parent_department_id': root.id, 'order_mode': policy.order_mode, 'location_id': location.id}

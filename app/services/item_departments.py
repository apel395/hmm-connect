from fastapi import HTTPException
from sqlalchemy import inspect
from app.models.item_department import ItemDepartment
from app.models.department import Department
from app.models.business_unit import BusinessUnit
from app.models.location_department import LocationDepartment
from app.services.location_access import assigned_location_id


def available(db):
    if 'item_departments_available' not in db.info:
        db.info['item_departments_available'] = inspect(db.connection()).has_table('item_departments')
    return db.info['item_departments_available']


def options(db, user, catalog):
    query = db.query(Department).join(BusinessUnit, BusinessUnit.id == Department.business_unit_id).filter(Department.is_active.is_(True), BusinessUnit.is_active.is_(True))
    query = query.filter(BusinessUnit.name.ilike('%hotel%' if catalog == 'HOTEL' else '%catering%'))
    loc = assigned_location_id(user)
    if loc:
        query = query.join(LocationDepartment, LocationDepartment.department_id == Department.id).filter(LocationDepartment.location_id == loc)
    return query.order_by(Department.name).all()


def payloads(db, ids):
    if not ids or not available(db):
        return {}
    rows = db.query(ItemDepartment.product_id, Department.id, Department.name).join(Department, Department.id == ItemDepartment.department_id).filter(ItemDepartment.product_id.in_(ids)).all()
    return {pid: {'department_id': did, 'department_name': name} for pid, did, name in rows}


def assign(db, product, department_id, user):
    if not available(db):
        if department_id is None:
            return
        raise HTTPException(503, 'Item department setup requires the Item Master migration on EC2')
    if department_id is not None and department_id not in {d.id for d in options(db, user, product.catalog_type)}:
        raise HTTPException(422, 'Choose an active department in this item catalog and your location access')
    current = db.get(ItemDepartment, product.id)
    if department_id is None:
        if current:
            db.delete(current)
    elif current:
        current.department_id = department_id
    else:
        db.add(ItemDepartment(product_id=product.id, department_id=department_id))

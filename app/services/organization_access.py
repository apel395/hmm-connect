"""Organization lookup and report scope from the signed-in user."""
from fastapi import HTTPException
from app.dependencies.authorization import is_superuser, role_names
from app.models.location import Location
from app.models.location_department import LocationDepartment
from app.models.department import Department
from app.services.location_access import assigned_location_id


def business_unit_scope(db, user):
    if is_superuser(user):
        return None
    loc_id = assigned_location_id(user)
    if loc_id:
        location = db.get(Location, loc_id)
        return location.business_unit_id if location else None
    return getattr(user, 'default_business_unit_id', None)


def department_scope(user):
    if is_superuser(user) or 'DEPARTMENT' not in role_names(user):
        return None
    return getattr(user, 'default_department_id', None) or getattr(user, 'department_id', None)


def resolve_organization_access(db, user, *, location_id=None, business_unit_id=None, department_id=None):
    assigned = assigned_location_id(user)
    if assigned is not None:
        if location_id is not None and location_id != assigned:
            raise HTTPException(404, 'Location not found')
        location_id = assigned
    unit = business_unit_scope(db, user)
    if unit is not None:
        if business_unit_id is not None and business_unit_id != unit:
            raise HTTPException(404, 'Business unit not found')
        business_unit_id = unit
    location = db.get(Location, location_id) if location_id else None
    if location and business_unit_id is not None and location.business_unit_id != business_unit_id:
        raise HTTPException(404, 'Location not found')
    assigned_department = department_scope(user)
    if assigned_department is not None:
        if department_id is not None and department_id != assigned_department:
            raise HTTPException(404, 'Department not found')
        department_id = assigned_department
    if department_id not in (None, 0):
        department = db.get(Department, department_id)
        if not department or (business_unit_id is not None and department.business_unit_id not in (None, business_unit_id)):
            raise HTTPException(404, 'Department not found')
        if location_id and not db.query(LocationDepartment).filter_by(location_id=location_id, department_id=department_id).first():
            raise HTTPException(404, 'Department not found')
    return dict(location_id=location_id, business_unit_id=business_unit_id, department_id=department_id)


def effective_business_unit(unit_column, location_column):
    """Legacy rows inherit their unit from the recorded work location."""
    from sqlalchemy import func, select
    return func.coalesce(unit_column, select(Location.business_unit_id).where(
        Location.id == location_column).correlate_except(Location).scalar_subquery())

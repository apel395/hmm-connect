from fastapi import HTTPException
from sqlalchemy import and_

from app.models.business_unit import BusinessUnit
from app.models.location import Location
from app.models.department import Department
from app.models.location_department import LocationDepartment


def validate_dimensions(db, business_unit_id=None, location_id=None, department_id=None, required=False):
    if required and not business_unit_id:
        raise HTTPException(422, "Business Unit is required")

    business_unit = db.get(BusinessUnit, business_unit_id) if business_unit_id else None
    if business_unit_id and not business_unit:
        raise HTTPException(422, "Business Unit does not exist")

    location = db.get(Location, location_id) if location_id else None
    if location_id:
        if not location:
            raise HTTPException(422, "Location does not exist")
        if business_unit_id and location.business_unit_id != business_unit_id:
            raise HTTPException(422, "Location does not belong to selected Business Unit")

    department = db.get(Department, department_id) if department_id else None
    if department_id:
        if not department:
            raise HTTPException(422, "Department does not exist")
        if business_unit_id and department.business_unit_id not in (None, business_unit_id):
            raise HTTPException(422, "Department does not belong to selected Business Unit")
        if location_id:
            mapped = (
                db.query(LocationDepartment)
                .filter(
                    LocationDepartment.location_id == location_id,
                    LocationDepartment.department_id == department_id,
                )
                .first()
            )
            if not mapped:
                raise HTTPException(422, "Department is not available for selected Location")

    return business_unit_id, location_id, department_id

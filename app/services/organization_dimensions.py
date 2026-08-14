from fastapi import HTTPException
from app.models.business_unit import BusinessUnit
from app.models.location import Location
from app.models.department import Department
def validate_dimensions(db,business_unit_id=None,location_id=None,department_id=None,required=False):
 if required and not business_unit_id:raise HTTPException(422,"Business Unit is required")
 if business_unit_id and not db.get(BusinessUnit,business_unit_id):raise HTTPException(422,"Business Unit does not exist")
 if location_id:
  location=db.get(Location,location_id)
  if not location:raise HTTPException(422,"Location does not exist")
  if business_unit_id and location.business_unit_id!=business_unit_id:raise HTTPException(422,"Location does not belong to selected Business Unit")
 if department_id:
  department=db.get(Department,department_id)
  if not department:raise HTTPException(422,"Department does not exist")
  if business_unit_id and department.business_unit_id not in (None,business_unit_id):raise HTTPException(422,"Department does not belong to selected Business Unit")
 return business_unit_id,location_id,department_id

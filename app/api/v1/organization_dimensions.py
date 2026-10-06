from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission, is_superuser
from app.models.business_unit import BusinessUnit
from app.models.department import Department
from app.models.location import Location
from app.models.location_department import LocationDepartment
from app.schemas.organization_dimensions import (
    BusinessUnitCreate, BusinessUnitUpdate, DepartmentCreate, DepartmentUpdate,
    LocationCreate, LocationUpdate,
)
from app.services.audit import record_audit
from app.services.location_access import assigned_location_id


router = APIRouter(tags=["Organization Dimensions"])
Search = Annotated[str | None, Query(max_length=100)]
MANAGE_PERMISSION = "organization_dimensions.manage"


def require_access(user, *, manage: bool = False) -> None:
    # Organization dimensions are shared operational lookup data used by
    # Purchasing, Warehouse, Finance and reporting forms. Authentication is
    # already enforced by the endpoint dependency, so reads are available to
    # every authenticated user. Mutations remain restricted.
    if not manage:
        return
    if is_superuser(user) or has_permission(user, MANAGE_PERMISSION):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "INSUFFICIENT_PERMISSION", "required_permission": MANAGE_PERMISSION},
    )


def normalize_code(value: str) -> str:
    return "-".join(value.strip().upper().split())


def normalize_name(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_location_type(value: str) -> str:
    return "_".join(value.strip().upper().split())


def validate_business_unit(db: Session, business_unit_id: int | None, *, required: bool) -> BusinessUnit | None:
    if business_unit_id is None:
        if required:
            raise HTTPException(422, "Business Unit is required")
        return None
    business_unit = db.get(BusinessUnit, business_unit_id)
    if not business_unit:
        raise HTTPException(422, "Business Unit does not exist")
    return business_unit


def reject_duplicate(db: Session, model, code: str | None, name: str | None, entity_id: int | None = None) -> None:
    conditions = []
    if code is not None:
        conditions.append(func.upper(model.code) == code.upper())
    if name is not None:
        conditions.append(func.lower(model.name) == name.lower())
    if not conditions:
        return
    query = db.query(model).filter(or_(*conditions))
    if entity_id is not None:
        query = query.filter(model.id != entity_id)
    duplicate = query.first()
    if duplicate:
        field = "code" if code and duplicate.code.upper() == code.upper() else "name"
        raise HTTPException(409, f"{model.__name__} {field} already exists")


def commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Code or name already exists") from exc


def business_unit_row(value: BusinessUnit) -> dict:
    return {"id": value.id, "code": value.code, "name": value.name, "description": value.description, "is_active": value.is_active, "created_at": value.created_at, "updated_at": value.updated_at}


def department_row(value: Department) -> dict:
    return {"id": value.id, "code": value.code, "name": value.name, "business_unit_id": value.business_unit_id, "business_unit_name": value.business_unit.name if value.business_unit else None, "is_active": value.is_active, "created_at": value.created_at, "updated_at": value.updated_at}


def location_row(value: Location) -> dict:
    return {"id": value.id, "code": value.code, "name": value.name, "business_unit_id": value.business_unit_id, "business_unit_name": value.business_unit.name if value.business_unit else None, "department_ids": sorted(link.department_id for link in value.department_links), "location_type": value.location_type, "address": value.address, "city": value.city, "province": value.province, "postal_code": value.postal_code, "is_active": value.is_active, "created_at": value.created_at, "updated_at": value.updated_at}


def validate_location_departments(db, business_unit_id, department_ids, existing_ids=()):
    ids = sorted(set(department_ids))
    departments = db.query(Department).filter(Department.id.in_(ids)).all() if ids else []
    if len(departments) != len(ids):
        raise HTTPException(422, "A selected Department does not exist")
    for department in departments:
        if department.business_unit_id not in (None, business_unit_id):
            raise HTTPException(422, "Department does not belong to selected Business Unit")
        if not department.is_active and department.id not in existing_ids:
            raise HTTPException(422, "A selected Department is inactive")
    return ids


def replace_location_departments(db, location, department_ids):
    existing_ids = {link.department_id for link in location.department_links}
    ids = validate_location_departments(db, location.business_unit_id, department_ids, existing_ids)
    location.department_links = [LocationDepartment(department_id=did) for did in ids]


@router.get("/business-units")
def list_business_units(is_active: bool | None = None, active_only: bool = False, search: Search = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_access(user); query = db.query(BusinessUnit); active_filter = True if active_only else is_active
    if active_filter is not None: query = query.filter(BusinessUnit.is_active.is_(active_filter))
    if search:
        term = f"%{search.strip()}%"; query = query.filter(or_(BusinessUnit.code.ilike(term), BusinessUnit.name.ilike(term)))
    return [business_unit_row(value) for value in query.order_by(BusinessUnit.code)]


@router.post("/business-units", status_code=201)
def create_business_unit(data: BusinessUnitCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_access(user, manage=True); values = data.model_dump(); values["code"] = normalize_code(data.code); values["name"] = normalize_name(data.name); reject_duplicate(db, BusinessUnit, values["code"], values["name"]); value = BusinessUnit(**values); db.add(value); db.flush(); record_audit(db, user, "BUSINESS_UNIT_CREATED", "BUSINESS_UNIT", f"Created {value.code}", entity_id=value.id); commit_or_conflict(db); db.refresh(value); return business_unit_row(value)


@router.get("/business-units/{business_unit_id}")
def get_business_unit(business_unit_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_access(user); value = db.get(BusinessUnit, business_unit_id)
    if not value: raise HTTPException(404, "Business Unit not found")
    return business_unit_row(value)


@router.patch("/business-units/{business_unit_id}")
def update_business_unit(business_unit_id: int, data: BusinessUnitUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_access(user, manage=True); value = db.get(BusinessUnit, business_unit_id)
    if not value: raise HTTPException(404, "Business Unit not found")
    changes = data.model_dump(exclude_unset=True)
    if "code" in changes: changes["code"] = normalize_code(changes["code"])
    if "name" in changes: changes["name"] = normalize_name(changes["name"])
    reject_duplicate(db, BusinessUnit, changes.get("code"), changes.get("name"), value.id); deactivated = changes.get("is_active") is False and value.is_active
    for key, item in changes.items(): setattr(value, key, item)
    action = "BUSINESS_UNIT_DEACTIVATED" if deactivated else "BUSINESS_UNIT_UPDATED"; record_audit(db, user, action, "BUSINESS_UNIT", f"{'Deactivated' if deactivated else 'Updated'} {value.code}", entity_id=value.id); commit_or_conflict(db); db.refresh(value); return business_unit_row(value)


@router.get("/departments")
def list_departments(business_unit_id: int | None = None, location_id: int | None = None, is_active: bool | None = None, include_shared: bool = True, search: Search = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_access(user); query = db.query(Department).options(joinedload(Department.business_unit))
    if location_id is not None:
        location = db.get(Location, location_id)
        if not location:
            raise HTTPException(422, "Location does not exist")
        if business_unit_id is not None and location.business_unit_id != business_unit_id:
            raise HTTPException(422, "Location does not belong to selected Business Unit")
        business_unit_id = location.business_unit_id
        query = query.join(LocationDepartment, LocationDepartment.department_id == Department.id).filter(LocationDepartment.location_id == location_id)
    if business_unit_id is not None:
        validate_business_unit(db, business_unit_id, required=True); dimension_filter = Department.business_unit_id == business_unit_id
        if include_shared: dimension_filter = or_(dimension_filter, Department.business_unit_id.is_(None))
        query = query.filter(dimension_filter)
    if is_active is not None: query = query.filter(Department.is_active.is_(is_active))
    if search:
        term = f"%{search.strip()}%"; query = query.filter(or_(Department.code.ilike(term), Department.name.ilike(term)))
    return [department_row(value) for value in query.order_by(Department.code)]


@router.post("/departments", status_code=201)
def create_department(data: DepartmentCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_access(user, manage=True); validate_business_unit(db, data.business_unit_id, required=False); values=data.model_dump(); values["code"]=normalize_code(data.code); values["name"]=normalize_name(data.name); reject_duplicate(db, Department, values["code"], values["name"]); value=Department(**values); db.add(value); db.flush(); record_audit(db,user,"DEPARTMENT_CREATED","DEPARTMENT",f"Created {value.code}",entity_id=value.id); commit_or_conflict(db); return department_row(db.query(Department).options(joinedload(Department.business_unit)).filter(Department.id==value.id).one())


@router.get("/departments/{department_id}")
def get_department(department_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    require_access(user); value=db.query(Department).options(joinedload(Department.business_unit)).filter(Department.id==department_id).first()
    if not value: raise HTTPException(404,"Department not found")
    return department_row(value)


@router.patch("/departments/{department_id}")
def update_department(department_id:int,data:DepartmentUpdate,db:Session=Depends(get_db),user=Depends(get_current_user)):
    require_access(user,manage=True); value=db.get(Department,department_id)
    if not value: raise HTTPException(404,"Department not found")
    changes=data.model_dump(exclude_unset=True)
    if "business_unit_id" in changes: validate_business_unit(db,changes["business_unit_id"],required=False)
    if "code" in changes: changes["code"]=normalize_code(changes["code"])
    if "name" in changes: changes["name"]=normalize_name(changes["name"])
    reject_duplicate(db,Department,changes.get("code"),changes.get("name"),value.id); deactivated=changes.get("is_active") is False and value.is_active
    for key,item in changes.items(): setattr(value,key,item)
    action="DEPARTMENT_DEACTIVATED" if deactivated else "DEPARTMENT_UPDATED"; record_audit(db,user,action,"DEPARTMENT",f"{'Deactivated' if deactivated else 'Updated'} {value.code}",entity_id=value.id); commit_or_conflict(db); return get_department(value.id,db,user)


@router.delete("/departments/{department_id}")
def deactivate_department(department_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    require_access(user,manage=True); value=db.get(Department,department_id)
    if not value: raise HTTPException(404,"Department not found")
    if value.is_active: value.is_active=False; record_audit(db,user,"DEPARTMENT_DEACTIVATED","DEPARTMENT",f"Deactivated {value.code}",entity_id=value.id); db.commit()
    return get_department(value.id,db,user)


@router.get("/locations")
def list_locations(
    business_unit_id:int|None=None,
    location_type:str|None=None,
    is_active:bool|None=None,
    search:Search=None,
    assigned_only:bool=False,
    db:Session=Depends(get_db),
    user=Depends(get_current_user),
):
    require_access(user)
    query=db.query(Location).options(joinedload(Location.business_unit))
    if business_unit_id is not None:
        validate_business_unit(db,business_unit_id,required=True)
        query=query.filter(Location.business_unit_id==business_unit_id)
    if assigned_only:
        location_id=assigned_location_id(user)
        if location_id is not None:
            query=query.filter(Location.id==location_id)
    if location_type:
        query=query.filter(Location.location_type==normalize_location_type(location_type))
    if is_active is not None:
        query=query.filter(Location.is_active.is_(is_active))
    if search:
        term=f"%{search.strip()}%"
        query=query.filter(or_(Location.code.ilike(term),Location.name.ilike(term)))
    return [location_row(value) for value in query.order_by(Location.code)]


@router.post("/locations",status_code=201)
def create_location(data:LocationCreate,db:Session=Depends(get_db),user=Depends(get_current_user)):
    require_access(user,manage=True); validate_business_unit(db,data.business_unit_id,required=True); values=data.model_dump(); department_ids=validate_location_departments(db,data.business_unit_id,values.pop("department_ids")); values["code"]=normalize_code(data.code); values["name"]=normalize_name(data.name); values["location_type"]=normalize_location_type(data.location_type); reject_duplicate(db,Location,values["code"],values["name"]); value=Location(**values); db.add(value); db.flush(); replace_location_departments(db,value,department_ids); record_audit(db,user,"LOCATION_CREATED","LOCATION",f"Created {value.code}",entity_id=value.id); commit_or_conflict(db); return get_location(value.id,db,user)


@router.get("/locations/{location_id}")
def get_location(location_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    require_access(user); value=db.query(Location).options(joinedload(Location.business_unit)).filter(Location.id==location_id).first()
    if not value: raise HTTPException(404,"Location not found")
    return location_row(value)


@router.patch("/locations/{location_id}")
def update_location(location_id:int,data:LocationUpdate,db:Session=Depends(get_db),user=Depends(get_current_user)):
    require_access(user,manage=True); value=db.get(Location,location_id)
    if not value: raise HTTPException(404,"Location not found")
    changes=data.model_dump(exclude_unset=True)
    department_ids = changes.pop("department_ids", None)
    existing_ids = [link.department_id for link in value.department_links]
    target_unit = changes.get("business_unit_id", value.business_unit_id)
    validate_business_unit(db, target_unit, required=True)
    validate_location_departments(db, target_unit, department_ids if department_ids is not None else existing_ids, existing_ids)
    if "code" in changes: changes["code"]=normalize_code(changes["code"])
    if "name" in changes: changes["name"]=normalize_name(changes["name"])
    if "location_type" in changes: changes["location_type"]=normalize_location_type(changes["location_type"])
    reject_duplicate(db,Location,changes.get("code"),changes.get("name"),value.id); deactivated=changes.get("is_active") is False and value.is_active
    for key,item in changes.items(): setattr(value,key,item)
    if department_ids is not None: replace_location_departments(db,value,department_ids)
    action="LOCATION_DEACTIVATED" if deactivated else "LOCATION_UPDATED"; record_audit(db,user,action,"LOCATION",f"{'Deactivated' if deactivated else 'Updated'} {value.code}",entity_id=value.id); commit_or_conflict(db); return get_location(value.id,db,user)


@router.delete("/locations/{location_id}")
def deactivate_location(location_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    require_access(user,manage=True); value=db.get(Location,location_id)
    if not value: raise HTTPException(404,"Location not found")
    if value.is_active: value.is_active=False; record_audit(db,user,"LOCATION_DEACTIVATED","LOCATION",f"Deactivated {value.code}",entity_id=value.id); db.commit()
    return get_location(value.id,db,user)

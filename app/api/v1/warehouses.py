from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.models.warehouse import Warehouse
from app.models.location import Location
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate
from app.services.activity_service import ActivityService
from app.services.location_access import apply_warehouse_scope

router = APIRouter(prefix="/warehouses", tags=["Warehouses"])


def _active_location(db: Session, location_id: int | None) -> Location:
    if location_id is not None:
        location = db.get(Location, location_id)
        if not location or not location.is_active:
            raise HTTPException(status_code=422, detail="Active warehouse location is required")
        return location
    locations = db.query(Location).filter(Location.is_active.is_(True)).order_by(Location.id).all()
    if len(locations) != 1:
        raise HTTPException(
            status_code=422,
            detail="Warehouse location is required when more than one active location exists",
        )
    return locations[0]

@router.get("")
def list_warehouses(response: Response, active_only: bool = True, search: str | None = Query(default=None, max_length=100), page: int | None = Query(default=None, ge=1), page_size: int = Query(default=25, ge=1, le=250), db: Session = Depends(get_db), _=Depends(get_current_user)):
    user = _
    query = apply_warehouse_scope(db.query(Warehouse), user)
    if active_only: query = query.filter(Warehouse.is_active.is_(True))
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(Warehouse.code.ilike(term), Warehouse.name.ilike(term), Warehouse.address.ilike(term)))
    total = query.count(); response.headers["X-Total-Count"] = str(total); query = query.order_by(Warehouse.code)
    if page is not None: query = query.offset((page - 1) * page_size).limit(page_size)
    return query.all()

@router.post("", status_code=201)
def create_warehouse(data: WarehouseCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not has_permission(user, "warehouse.manage"): raise HTTPException(status_code=403, detail="Warehouse manage permission required")
    code = data.code.strip().upper()
    if db.query(Warehouse).filter(Warehouse.code == code).first(): raise HTTPException(status_code=409, detail="Warehouse code already exists")
    location = _active_location(db, data.location_id)
    warehouse = Warehouse(code=code, name=data.name.strip(), address=data.address, location_id=location.id, is_active=True)
    db.add(warehouse); db.flush()
    ActivityService.log(db=db, user=user, action="CREATE", entity_type="WAREHOUSE", entity_id=warehouse.id, summary=f"Created warehouse {warehouse.code}", details={"name": warehouse.name})
    db.commit(); db.refresh(warehouse); return warehouse

@router.patch("/{warehouse_id}")
def update_warehouse(warehouse_id: int, data: WarehouseUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not has_permission(user, "warehouse.manage"): raise HTTPException(status_code=403, detail="Warehouse manage permission required")
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse: raise HTTPException(status_code=404, detail="Warehouse not found")
    changes = {}
    if data.name is not None:
        value = data.name.strip()
        if not value: raise HTTPException(status_code=422, detail="Warehouse name is required")
        changes["name"] = {"from": warehouse.name, "to": value}; warehouse.name = value
    if "address" in data.model_fields_set:
        changes["address"] = {"from": warehouse.address, "to": data.address}; warehouse.address = data.address
    if "location_id" in data.model_fields_set:
        location = _active_location(db, data.location_id)
        changes["location_id"] = {"from": warehouse.location_id, "to": location.id}; warehouse.location_id = location.id
    if data.is_active is not None:
        changes["is_active"] = {"from": warehouse.is_active, "to": data.is_active}; warehouse.is_active = data.is_active
    ActivityService.log(db=db, user=user, action="UPDATE", entity_type="WAREHOUSE", entity_id=warehouse.id, summary=f"Updated warehouse {warehouse.code}", details=changes)
    db.commit(); db.refresh(warehouse); return warehouse

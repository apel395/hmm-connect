from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import is_superuser
from app.models.warehouse import Warehouse
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate
from app.services.activity_service import ActivityService

router = APIRouter(prefix="/warehouses", tags=["Warehouses"])

@router.get("")
def list_warehouses(response: Response, active_only: bool = True, search: str | None = Query(default=None, max_length=100), page: int | None = Query(default=None, ge=1), page_size: int = Query(default=25, ge=1, le=250), db: Session = Depends(get_db), _=Depends(get_current_user)):
    query = db.query(Warehouse)
    if active_only: query = query.filter(Warehouse.is_active.is_(True))
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(Warehouse.code.ilike(term), Warehouse.name.ilike(term), Warehouse.address.ilike(term)))
    total = query.count(); response.headers["X-Total-Count"] = str(total); query = query.order_by(Warehouse.code)
    if page is not None: query = query.offset((page - 1) * page_size).limit(page_size)
    return query.all()

@router.post("", status_code=201)
def create_warehouse(data: WarehouseCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not is_superuser(user): raise HTTPException(status_code=403, detail="Administrator access required")
    code = data.code.strip().upper()
    if db.query(Warehouse).filter(Warehouse.code == code).first(): raise HTTPException(status_code=409, detail="Warehouse code already exists")
    warehouse = Warehouse(code=code, name=data.name.strip(), address=data.address, is_active=True)
    db.add(warehouse); db.flush()
    ActivityService.log(db=db, user=user, action="CREATE", entity_type="WAREHOUSE", entity_id=warehouse.id, summary=f"Created warehouse {warehouse.code}", details={"name": warehouse.name})
    db.commit(); db.refresh(warehouse); return warehouse

@router.patch("/{warehouse_id}")
def update_warehouse(warehouse_id: int, data: WarehouseUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not is_superuser(user): raise HTTPException(status_code=403, detail="Administrator access required")
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse: raise HTTPException(status_code=404, detail="Warehouse not found")
    changes = {}
    if data.name is not None:
        value = data.name.strip()
        if not value: raise HTTPException(status_code=422, detail="Warehouse name is required")
        changes["name"] = {"from": warehouse.name, "to": value}; warehouse.name = value
    if "address" in data.model_fields_set:
        changes["address"] = {"from": warehouse.address, "to": data.address}; warehouse.address = data.address
    if data.is_active is not None:
        changes["is_active"] = {"from": warehouse.is_active, "to": data.is_active}; warehouse.is_active = data.is_active
    ActivityService.log(db=db, user=user, action="UPDATE", entity_type="WAREHOUSE", entity_id=warehouse.id, summary=f"Updated warehouse {warehouse.code}", details=changes)
    db.commit(); db.refresh(warehouse); return warehouse

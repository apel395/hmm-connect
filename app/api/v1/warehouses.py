from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.warehouse import Warehouse
from app.schemas.warehouse import WarehouseCreate
from app.services.activity_service import ActivityService


router = APIRouter(prefix="/warehouses", tags=["Warehouses"])


def _is_admin(user) -> bool:
    return any(role.name == "ADMIN" for role in user.roles)


@router.get("")
def list_warehouses(
    active_only: bool = True,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(Warehouse)
    if active_only:
        query = query.filter(Warehouse.is_active.is_(True))
    return query.order_by(Warehouse.code).all()


@router.post("", status_code=201)
def create_warehouse(
    data: WarehouseCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Administrator access required")
    code = data.code.strip().upper()
    if db.query(Warehouse).filter(Warehouse.code == code).first():
        raise HTTPException(status_code=409, detail="Warehouse code already exists")
    warehouse = Warehouse(
        code=code,
        name=data.name.strip(),
        address=data.address,
        is_active=True,
    )
    db.add(warehouse)
    db.flush()
    ActivityService.log(
        db=db,
        user=user,
        action="CREATE",
        entity_type="WAREHOUSE",
        entity_id=warehouse.id,
        summary=f"Created warehouse {warehouse.code}",
        details={"name": warehouse.name},
    )
    db.commit()
    db.refresh(warehouse)
    return warehouse
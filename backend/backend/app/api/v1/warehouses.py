from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.warehouse import Warehouse
from app.schemas.warehouse import WarehouseCreate, WarehouseResponse
from app.services.audit import record_audit

router = APIRouter(prefix="/warehouses", tags=["Warehouses"])


@router.get("", response_model=list[WarehouseResponse])
def get_warehouses(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return db.query(Warehouse).order_by(Warehouse.code).all()


@router.post("", response_model=WarehouseResponse, status_code=201)
def create_warehouse(
    data: WarehouseCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    existing = db.query(Warehouse).filter(Warehouse.code == data.code).first()
    if existing:
        raise HTTPException(status_code=409, detail="Warehouse code already exists")

    warehouse = Warehouse(
        code=data.code.strip().upper(),
        name=data.name.strip(),
        address=data.address,
    )
    db.add(warehouse)
    db.flush()

    record_audit(
        db=db,
        user=current_user,
        action="CREATE",
        entity_type="WAREHOUSE",
        entity_id=warehouse.id,
        summary=f"Created warehouse {warehouse.code}",
        details={"code": warehouse.code, "name": warehouse.name},
    )

    db.commit()
    db.refresh(warehouse)
    return warehouse

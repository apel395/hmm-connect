from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.supplier import Supplier
from app.schemas.supplier import SupplierCreate, SupplierUpdate


router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.get("")
def list_suppliers(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Supplier).order_by(Supplier.code).all()


@router.post("", status_code=201)
def create_supplier(
    data: SupplierCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    if db.query(Supplier).filter(Supplier.code == data.code).first():
        raise HTTPException(status_code=409, detail="Supplier code already exists")
    supplier = Supplier(**data.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.patch("/{supplier_id}")
def update_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    return supplier

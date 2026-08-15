from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.supplier import Supplier
from app.schemas.supplier import SupplierCreate, SupplierUpdate


router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.get("")
def list_suppliers(
    response: Response,
    search: str | None = Query(default=None, max_length=100),
    is_active: bool | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=25, ge=1, le=250),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(Supplier)
    if is_active is not None:
        query = query.filter(Supplier.is_active.is_(is_active))
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(Supplier.code.ilike(term), Supplier.name.ilike(term)))

    total = query.count()
    response.headers["X-Total-Count"] = str(total)
    query = query.order_by(Supplier.code)
    if page is not None:
        query = query.offset((page - 1) * page_size).limit(page_size)
    return query.all()


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

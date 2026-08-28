from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import require_permission
from app.models.supplier import Supplier
from app.schemas.supplier import SupplierCreate, SupplierUpdate
from app.services.direct_coa_service import DirectCoaService


router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


def _filtered(query, search: str | None, is_active: bool | None):
    if is_active is not None:
        query = query.filter(Supplier.is_active.is_(is_active))
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Supplier.code.ilike(term), Supplier.name.ilike(term)))
    return query


@router.get("")
def list_suppliers(search: str | None = Query(default=None, max_length=100), is_active: bool | None = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100), db: Session = Depends(get_db), _=Depends(get_current_user)):
    query = _filtered(db.query(Supplier), search, is_active)
    total = query.count()
    rows = query.order_by(Supplier.code).offset((page - 1) * page_size).limit(page_size).all()
    total_pages = ceil(total / page_size) if total else 0
    return {"items": rows, "page": page, "page_size": page_size, "total_items": total, "total_pages": total_pages, "has_next": page < total_pages, "has_previous": page > 1}


@router.get("/lookup")
def lookup_suppliers(search: str = Query(default="", max_length=100), limit: int = Query(default=30, ge=1, le=100), db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = _filtered(db.query(Supplier), search, True).order_by(Supplier.name, Supplier.code).limit(limit).all()
    return [{"id": row.id, "code": row.code, "name": row.name, "is_active": row.is_active, "is_pkp": row.is_pkp} for row in rows]


@router.post("", status_code=201)
def create_supplier(data: SupplierCreate, db: Session = Depends(get_db), _=Depends(require_permission("finance.manage"))):
    if db.query(Supplier).filter(Supplier.code == data.code).first():
        raise HTTPException(status_code=409, detail="Supplier code already exists")
    if data.payable_account_id:
        DirectCoaService(db).payable_account(type("SupplierProbe", (), {"code": data.code, "payable_account_id": data.payable_account_id})())
    supplier = Supplier(**data.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.patch("/{supplier_id}")
@router.put("/{supplier_id}")
def update_supplier(supplier_id: int, data: SupplierUpdate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    payload = data.model_dump(exclude_unset=True)
    if "payable_account_id" in payload and payload["payable_account_id"]:
        DirectCoaService(db).payable_account(type("SupplierProbe", (), {"code": supplier.code, "payable_account_id": payload["payable_account_id"]})())
    for field, value in payload.items():
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    return supplier

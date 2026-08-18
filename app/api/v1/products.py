from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate


router = APIRouter(prefix="/products", tags=["Products"])


def _apply_filters(query, *, active_only: bool, search: str | None, market_only: bool = False):
    if active_only:
        query = query.filter(Product.is_active.is_(True))
    if market_only:
        query = query.filter(Product.is_market_item.is_(True))
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Product.code.ilike(term), Product.name.ilike(term)))
    return query


@router.get("")
def list_products(
    active_only: bool = True,
    market_only: bool = False,
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = _apply_filters(db.query(Product), active_only=active_only, search=search, market_only=market_only)
    total = query.count()
    rows = query.order_by(Product.code).offset((page - 1) * page_size).limit(page_size).all()
    total_pages = ceil(total / page_size) if total else 0
    return {
        "items": rows,
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


@router.get("/lookup")
def lookup_products(
    search: str = Query(default="", max_length=100),
    market_only: bool = False,
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = _apply_filters(db.query(Product), active_only=True, search=search, market_only=market_only)
    rows = query.order_by(Product.name, Product.code).limit(limit).all()
    return [
        {
            "id": row.id,
            "code": row.code,
            "name": row.name,
            "description": row.description,
            "uom": row.uom,
            "usage_uom": row.usage_uom,
            "conversion_factor": row.conversion_factor,
            "tax_category": row.tax_category,
            "is_taxable": row.is_taxable,
            "tax_rate": row.tax_rate,
            "is_market_item": row.is_market_item,
        }
        for row in rows
    ]


@router.post("", status_code=201)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    if db.query(Product).filter(Product.code == data.code).first():
        raise HTTPException(status_code=409, detail="Product code already exists")
    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.patch("/{product_id}")
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product

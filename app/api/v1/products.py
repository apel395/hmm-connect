from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate


router = APIRouter(prefix="/products", tags=["Products"])


@router.get("")
def list_products(
    active_only: bool = True,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(Product)
    if active_only:
        query = query.filter(Product.is_active.is_(True))
    return query.order_by(Product.code).all()


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

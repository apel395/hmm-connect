from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import require_permission
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.supplier_product import SupplierProduct
from app.schemas.supplier_product import (
    SupplierProductCreate,
    SupplierProductMatchResponse,
    SupplierProductResponse,
)
from app.services.audit import record_audit


router = APIRouter(
    prefix="/suppliers",
    tags=["Supplier Products"],
)


def to_response(row: SupplierProduct) -> SupplierProductResponse:
    return SupplierProductResponse(
        id=row.id,
        supplier_id=row.supplier_id,
        product_id=row.product_id,

        supplier_sku=row.supplier_sku,

        supplier_price=row.supplier_price,
        lead_time_days=row.lead_time_days,
        is_preferred=row.is_preferred,

        product_code=row.product.code,
        product_name=row.product.name,
        product_uom=row.product.uom,

        product_usage_uom=row.product.usage_uom,
        conversion=row.product.conversion,
    )


@router.get(
    "/{supplier_id}/products",
    response_model=list[SupplierProductResponse],
)
def get_supplier_products(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("suppliers.manage")),
):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    rows = (
        db.query(SupplierProduct)
        .options(joinedload(SupplierProduct.product))
        .filter(SupplierProduct.supplier_id == supplier_id)
        .order_by(SupplierProduct.id)
        .all()
    )

    return [to_response(row) for row in rows]


@router.post(
    "/{supplier_id}/products",
    response_model=SupplierProductResponse,
    status_code=201,
)
def create_supplier_product(
    supplier_id: int,
    data: SupplierProductCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("suppliers.manage")),
):
    supplier = db.get(Supplier, supplier_id)
    product = db.get(Product, data.product_id)

    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = (
        db.query(SupplierProduct)
        .filter(
            SupplierProduct.supplier_id == supplier_id,
            SupplierProduct.product_id == data.product_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Product is already linked to this supplier",
        )

    if data.is_preferred:
        db.query(SupplierProduct).filter(
            SupplierProduct.product_id == data.product_id,
        ).update(
            {SupplierProduct.is_preferred: False},
            synchronize_session=False,
        )

    row = SupplierProduct(
        supplier_id=supplier_id,
        product_id=data.product_id,

        supplier_sku=data.supplier_sku,

        supplier_price=data.supplier_price,
        lead_time_days=data.lead_time_days,
        is_preferred=data.is_preferred,
    )
    db.add(row)
    db.flush()

    record_audit(
        db=db,
        user=current_user,
        action="CREATE",
        entity_type="SUPPLIER_PRODUCT",
        entity_id=row.id,
        summary=f"Linked {product.code} to supplier {supplier.code}",
        details={
            "supplier_id": supplier_id,
            "product_id": data.product_id,

            "supplier_sku": data.supplier_sku,

            "supplier_price": (
                str(data.supplier_price)
                if data.supplier_price is not None
                else None
            ),

            "is_preferred": data.is_preferred,
        },
    )

    db.commit()
    db.refresh(row)
    return to_response(row)


@router.delete(
    "/{supplier_id}/products/{supplier_product_id}",
    status_code=204,
)
def delete_supplier_product(
    supplier_id: int,
    supplier_product_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("suppliers.manage")),
):
    row = (
        db.query(SupplierProduct)
        .options(joinedload(SupplierProduct.product))
        .filter(
            SupplierProduct.id == supplier_product_id,
            SupplierProduct.supplier_id == supplier_id,
        )
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail="Supplier product not found")

    record_audit(
        db=db,
        user=current_user,
        action="DELETE",
        entity_type="SUPPLIER_PRODUCT",
        entity_id=row.id,
        summary=f"Unlinked {row.product.code} from supplier",
        details={"supplier_id": supplier_id, "product_id": row.product_id},
    )

    db.delete(row)
    db.commit()


@router.get(
    "/product/{product_id}/matches",
    response_model=list[SupplierProductMatchResponse],
)
def get_supplier_matches(
    product_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("suppliers.manage")),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    rows = (
        db.query(SupplierProduct)
        .join(SupplierProduct.supplier)
        .filter(
            SupplierProduct.product_id == product_id,
            Supplier.is_active.is_(True),
        )
        .order_by(
            SupplierProduct.is_preferred.desc(),
            SupplierProduct.supplier_price.asc().nullslast(),
            Supplier.name,
        )
        .all()
    )

    return [
        SupplierProductMatchResponse(
            supplier_id=row.supplier_id,
            supplier_code=row.supplier.code,
            supplier_name=row.supplier.name,
            supplier_price=row.supplier_price,
            lead_time_days=row.lead_time_days,
            is_preferred=row.is_preferred,
        )
        for row in rows
    ]

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user

from app.models.item_group import ItemGroup
from app.models.item_subgroup import ItemSubgroup
from app.models.product import Product
from app.services.audit import record_audit

from app.schemas.product import (
    ProductCreate,
    ProductResponse,
)


router = APIRouter(
    prefix="/products",
    tags=["Products"],
)


@router.get(
    "",
    response_model=list[ProductResponse],
)
def get_products(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return (
        db.query(Product)
        .filter(Product.is_active.is_(True))
        .order_by(Product.name)
        .all()
    )


def generate_product_code(
    db: Session,
    group_code: str,
) -> str:
    db.execute(
        text(
            """
            SELECT pg_advisory_xact_lock(
                hashtext(:lock_key)
            )
            """
        ),
        {
            "lock_key": f"product-code:{group_code}",
        },
    )

    last_number = db.execute(
        text(
            """
            SELECT COALESCE(
                MAX(
                    CAST(
                        split_part(code, '-', 2)
                        AS INTEGER
                    )
                ),
                100000
            )
            FROM products
            WHERE group_code = :group_code
            AND code ~ '^[0-9]+-[0-9]+$'
            """
        ),
        {
            "group_code": group_code,
        },
    ).scalar_one()

    return f"{group_code}-{last_number + 1}"


@router.post(
    "",
    response_model=ProductResponse,
    status_code=201,
)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    group = (
        db.query(ItemGroup)
        .filter(
            ItemGroup.code == data.group_code,
            ItemGroup.is_active.is_(True),
        )
        .first()
    )

    if not group:
        raise HTTPException(
            status_code=404,
            detail="Item group not found",
        )

    subgroup = (
        db.query(ItemSubgroup)
        .filter(
            ItemSubgroup.code == data.subgroup_code,
            ItemSubgroup.group_id == group.id,
            ItemSubgroup.is_active.is_(True),
        )
        .first()
    )

    if not subgroup:
        raise HTTPException(
            status_code=404,
            detail="Item subgroup not found for selected group",
        )

    code = generate_product_code(
        db=db,
        group_code=group.code,
    )

    product = Product(
        code=code,
        name=data.name.strip(),
        group_code=group.code,
        group_name=group.name,
        subgroup_code=subgroup.code,
        subgroup_name=subgroup.name,
        uom=data.uom,
        usage_uom=data.usage_uom,
        conversion=data.conversion,
        cost_price=0,
        selling_price=0,
        is_active=True,
    )

    db.add(product)
    db.flush()

    record_audit(
        db=db,
        user=current_user,
        action="CREATE",
        entity_type="PRODUCT",
        entity_id=product.id,
        summary=f"Created product {product.code} - {product.name}",
        details={"code": product.code, "name": product.name},
    )

    db.commit()
    db.refresh(product)

    return product

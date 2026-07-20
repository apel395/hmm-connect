from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies.auth import get_current_user

from app.models.supplier import Supplier, SupplierRow
from app.services.audit import record_audit

from app.schemas.supplier import (
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)


router = APIRouter(
    prefix="/suppliers",
    tags=["Suppliers"],
)


@router.get(
    "",
    response_model=list[SupplierResponse],
)
def get_suppliers(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return (
        db.query(Supplier)
        .options(joinedload(Supplier.rows))
        .filter(Supplier.is_active.is_(True))
        .order_by(Supplier.name)
        .all()
    )


@router.patch(
    "/{supplier_id}",
    response_model=SupplierResponse,
)
def update_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    supplier = (
        db.query(Supplier)
        .options(joinedload(Supplier.rows))
        .filter(Supplier.id == supplier_id)
        .first()
    )

    if not supplier:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found",
        )

    duplicate = (
        db.query(Supplier)
        .filter(
            Supplier.code == data.code,
            Supplier.id != supplier_id,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="Supplier code already exists",
        )

    supplier.code = data.code
    supplier.name = data.name
    supplier.address = data.address
    supplier.bank_name = data.bank_name
    supplier.bank_account_number = data.bank_account_number
    supplier.bank_account_name = data.bank_account_name

    supplier.rows.clear()
    supplier.rows.extend(
        SupplierRow(
            pic_name=row.pic_name,
            phone=row.phone,
            unit=row.unit,
            item=row.item,
        )
        for row in data.rows
    )

    db.flush()

    record_audit(
        db=db,
        user=current_user,
        action="UPDATE",
        entity_type="SUPPLIER",
        entity_id=supplier.id,
        summary=f"Updated supplier {supplier.code} - {supplier.name}",
        details={
            "code": supplier.code,
            "name": supplier.name,
            "rows": len(data.rows),
        },
    )

    db.commit()
    db.refresh(supplier)

    return supplier


@router.post(
    "",
    response_model=SupplierResponse,
    status_code=201,
)
def create_supplier(
    data: SupplierCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    existing = (
        db.query(Supplier)
        .filter(Supplier.code == data.code)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Supplier code already exists",
        )

    supplier = Supplier(
        code=data.code,
        name=data.name,
        address=data.address,
        bank_name=data.bank_name,
        bank_account_number=data.bank_account_number,
        bank_account_name=data.bank_account_name,
    )

    supplier.rows = [
        SupplierRow(
            pic_name=row.pic_name,
            phone=row.phone,
            unit=row.unit,
            item=row.item,
        )
        for row in data.rows
    ]

    db.add(supplier)
    db.flush()

    record_audit(
        db=db,
        user=current_user,
        action="CREATE",
        entity_type="SUPPLIER",
        entity_id=supplier.id,
        summary=f"Created supplier {supplier.code} - {supplier.name}",
        details={"code": supplier.code, "name": supplier.name},
    )

    db.commit()
    db.refresh(supplier)

    return supplier

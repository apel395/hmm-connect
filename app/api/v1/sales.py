from datetime import date, datetime, timezone
from decimal import Decimal
from math import ceil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.product import Product
from app.models.sales_transaction import SalesTransaction
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.sales_transaction import (
    SalesTransactionCreate,
    SalesTransactionPost,
    SalesTransactionUpdate,
    SalesTransactionVoid,
)
from app.services.location_access import apply_location_scope, resolve_location_id
from app.models.location import Location
from app.models.business_unit import BusinessUnit
from app.models.department import Department
from app.models.location_department import LocationDepartment
from app.models.item_department import ItemDepartment
from app.services.sales_transaction_service import SalesTransactionService

router = APIRouter(prefix="/pos", tags=["Point of Sales"])


def _paged(items, *, page: int, page_size: int, total: int):
    total_pages = ceil(total / page_size) if total else 0
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


def _sale_items(transaction: SalesTransaction) -> list[dict]:
    return [
        {
            "id": line.id,
            "product_id": line.product_id,
            "product_code": line.product.code if line.product else None,
            "product_name": line.product.name if line.product else None,
            "uom": line.uom,
            "quantity": line.quantity,
            "unit_price": line.unit_price,
            "tax_rate": line.tax_rate,
            "service_charge_rate": line.service_charge_rate,
            "service_charge_amount": line.service_charge_amount,
            "tax_amount": line.tax_amount,
            "line_amount": line.line_amount,
            "unit_cost": line.unit_cost,
        }
        for line in sorted(transaction.lines, key=lambda row: row.id)
    ]


def serialize_sale(transaction: SalesTransaction) -> dict[str, Any]:
    created_by = transaction.created_by
    posted_by = transaction.posted_by
    customer = transaction.customer
    journal = transaction.journal_entry
    location = transaction.location
    return {
        "id": transaction.id,
        "transaction_number": transaction.transaction_number,
        "status": transaction.status,
        "sale_date": transaction.sale_date,
        "warehouse_id": transaction.warehouse_id,
        "warehouse_code": transaction.warehouse.code if transaction.warehouse else None,
        "warehouse_name": transaction.warehouse.name if transaction.warehouse else None,
        "customer_id": transaction.customer_id,
        "customer_code": customer.customer_code if customer else None,
        "customer_name": customer.customer_name if customer else None,
        "business_unit_id": transaction.business_unit_id,
        "location_id": transaction.location_id,
        "location_name": location.name if location else None,
        "transaction_type": transaction.transaction_type,
        "table_number": transaction.table_number,
        "queue_number": transaction.queue_number,
        "department_id": transaction.department_id,
        "payment_method": transaction.payment_method,
        "payment_received": transaction.payment_received,
        "change_amount": transaction.change_amount,
        "discount_amount": transaction.discount_amount,
        "subtotal": transaction.subtotal,
        "service_charge_amount": transaction.service_charge_amount,
        "tax_amount": transaction.tax_amount,
        "total_amount": transaction.total_amount,
        "notes": transaction.notes,
        "created_by_id": transaction.created_by_id,
        "created_by_name": (created_by.full_name or created_by.username) if created_by else None,
        "posted_by_id": transaction.posted_by_id,
        "posted_by_name": (posted_by.full_name or posted_by.username) if posted_by else None,
        "posted_at": transaction.posted_at,
        "void_reason": transaction.void_reason,
        "journal_number": journal.journal_number if journal else None,
        "items": _sale_items(transaction),
    }


@router.get("/options")
def sale_options(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    SalesTransactionService._require(user, "pos.view")
    locations = apply_location_scope(db.query(Location), Location.id, user).filter(Location.is_active.is_(True)).order_by(Location.name).all()
    links = db.query(LocationDepartment, Department).join(Department, Department.id == LocationDepartment.department_id).filter(Department.is_active.is_(True), LocationDepartment.location_id.in_([row.id for row in locations])).all()
    return {"locations": [{"id": row.id, "name": row.name, "code": str(row.id)} for row in locations],
            "departments": [{"id": dept.id, "name": dept.name, "location_id": link.location_id} for link, dept in links]}


@router.get("/products")
def list_pos_products(
    location_id: int | None = None,
    department_id: int | None = None,
    search: str | None = Query(default=None, max_length=100),
    group_name: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    SalesTransactionService._require(user, "pos.view")
    location_id = resolve_location_id(user, location_id)
    location = db.get(Location, location_id) if location_id else None
    if not location or not location.is_active:
        raise HTTPException(422, "Select an active sales location")
    from app.services.organization_dimensions import validate_dimensions
    validate_dimensions(db, location.business_unit_id, location.id, department_id, False)
    unit = db.get(BusinessUnit, location.business_unit_id)
    catalog = "HOTEL" if unit and "hotel" in unit.name.casefold() else "CATERING"
    query = db.query(Product).filter(Product.is_active.is_(True), Product.item_type == "SELL", Product.inventory_treatment == "NON_STOCK", Product.catalog_type == catalog,
        or_(Product.sales_location_id.is_(None), Product.sales_location_id == location.id),
        or_(Product.sales_business_unit_id.is_(None), Product.sales_business_unit_id == location.business_unit_id))
    from app.services import item_departments
    if item_departments.available(db):
        query = query.outerjoin(ItemDepartment, ItemDepartment.product_id == Product.id).filter(or_(ItemDepartment.department_id.is_(None), ItemDepartment.department_id == department_id))
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Product.code.ilike(term), Product.name.ilike(term)))
    if group_name:
        query = query.filter(Product.group_name == group_name)
    total = query.count()
    rows = query.order_by(Product.group_name, Product.name, Product.code).offset((page-1)*page_size).limit(page_size).all()
    items = [{"product_id": p.id, "product_code": p.code, "product_name": p.name, "group_name": p.group_name,
        "uom": p.uom, "selling_price": p.selling_price, "service_charge_rate": p.service_charge_rate,
        "tax_rate": p.tax_rate, "is_taxable": p.is_taxable,
        "sale_available": p.selling_price > 0 and not any(Decimal(getattr(p, field, 0) or 0) > 0 for field in ("pbjt_rate", "sales_ppn_rate", "pph23_rate"))} for p in rows]
    return _paged(items, page=page, page_size=page_size, total=total)


@router.get("")
def list_sales(
    status: str | None = Query(default=None, max_length=30),
    warehouse_id: int | None = None,
    location_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    SalesTransactionService._require(user, "pos.view")
    query = apply_location_scope(db.query(SalesTransaction), SalesTransaction.location_id, user)
    if status and status.upper() != "ALL":
        query = query.filter(SalesTransaction.status == status.upper())
    if location_id:
        query = query.filter(SalesTransaction.location_id == location_id)
    if warehouse_id:
        query = query.filter(SalesTransaction.warehouse_id == warehouse_id)
    if date_from:
        query = query.filter(SalesTransaction.sale_date >= date_from)
    if date_to:
        query = query.filter(SalesTransaction.sale_date <= date_to)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.outerjoin(Warehouse, Warehouse.id == SalesTransaction.warehouse_id)
        query = query.filter(
            or_(
                SalesTransaction.transaction_number.ilike(term),
                Warehouse.name.ilike(term),
            )
        )

    summary_rows = (
        apply_location_scope(db.query(SalesTransaction), SalesTransaction.location_id, user)
        .with_entities(SalesTransaction.status, func.count(SalesTransaction.id))
        .group_by(SalesTransaction.status)
        .all()
    )
    totals_filter = (
        apply_location_scope(db.query(SalesTransaction), SalesTransaction.location_id, user).filter(
            SalesTransaction.status == "POSTED"
        )
    )
    if location_id:
        totals_filter = totals_filter.filter(SalesTransaction.location_id == location_id)
    if date_from:
        totals_filter = totals_filter.filter(SalesTransaction.sale_date >= date_from)
    if date_to:
        totals_filter = totals_filter.filter(SalesTransaction.sale_date <= date_to)
    posted_rows = totals_filter.with_entities(
        func.count(SalesTransaction.id),
        func.coalesce(func.sum(SalesTransaction.total_amount), 0),
        func.coalesce(func.sum(SalesTransaction.tax_amount), 0),
    ).first()

    total = query.count()
    rows = (
        query.order_by(SalesTransaction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [serialize_sale(row) for row in rows]
    result = _paged(items, page=page, page_size=page_size, total=total)
    result["summary"] = {
        "status_counts": {key: int(value) for key, value in summary_rows},
        "posted_count": int(posted_rows[0] or 0),
        "posted_value": posted_rows[1] or 0,
        "tax_value": posted_rows[2] or 0,
    }
    return result


@router.post("", status_code=201)
def create_sale(
    data: SalesTransactionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return serialize_sale(SalesTransactionService.create(db, data=data, user=user))


@router.get("/{sale_id}")
def get_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    SalesTransactionService._require(user, "pos.view")
    transaction = (
        apply_location_scope(db.query(SalesTransaction), SalesTransaction.location_id, user)
        .filter(SalesTransaction.id == sale_id)
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="POS sale not found")
    return serialize_sale(transaction)


@router.put("/{sale_id}")
def update_sale(
    sale_id: int,
    data: SalesTransactionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    transaction = (
        apply_location_scope(db.query(SalesTransaction), SalesTransaction.location_id, user)
        .filter(SalesTransaction.id == sale_id)
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="POS sale not found")
    return serialize_sale(
        SalesTransactionService.update(db, transaction=transaction, data=data, user=user)
    )


@router.post("/{sale_id}/post")
def post_sale(
    sale_id: int,
    data: SalesTransactionPost,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    transaction = (
        apply_location_scope(db.query(SalesTransaction), SalesTransaction.location_id, user)
        .filter(SalesTransaction.id == sale_id)
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="POS sale not found")
    return serialize_sale(
        SalesTransactionService.post(db, transaction_id=sale_id, data=data, user=user)
    )


@router.post("/{sale_id}/void")
def void_sale(
    sale_id: int,
    data: SalesTransactionVoid = SalesTransactionVoid(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return serialize_sale(
        SalesTransactionService.void(db, transaction_id=sale_id, data=data, user=user)
    )


@router.get("/{sale_id}/print")
def print_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    SalesTransactionService._require(user, "pos.view")
    transaction = (
        apply_location_scope(db.query(SalesTransaction), SalesTransaction.location_id, user)
        .filter(SalesTransaction.id == sale_id)
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="POS sale not found")
    payload = serialize_sale(transaction)
    payload["printed_by"] = (user.full_name or user.username) if user else "System"
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    return payload

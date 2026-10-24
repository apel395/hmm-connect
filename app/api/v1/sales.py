from datetime import date, datetime, timezone
from decimal import Decimal
from math import ceil
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, false, func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.product import Product
from app.models.sales_transaction import SalesTransaction
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.sales_transaction import (
    InvoiceARCorrection,
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
from app.services.pos_tax import pbjt_account, tax_profile
from app.services.ar_invoice_service import receivable_choices, receivable_account, correct_posted_invoice
from app.models.account_receivable import AccountReceivable
from app.models.customer import Customer
from app.services.pos_revenue import revenue_accounts
from app.services.organization_access import business_unit_scope, department_scope, resolve_organization_access

router = APIRouter(prefix="/pos", tags=["Point of Sales"])


class PosCustomerCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=150)
    address: str | None = None


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
            "tax_type": line.tax_type,
            "tax_account_id": line.tax_account_id,
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
    from sqlalchemy.orm import object_session
    ar = object_session(transaction).query(AccountReceivable).filter_by(source_sale_id=transaction.id).first()
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
        "revenue_account_id": transaction.revenue_account_id,
        "invoice_due_date": transaction.invoice_due_date,
        "receivable_account_id": transaction.receivable_account_id,
        "ar_correction_journal_id": transaction.ar_correction_journal_id,
        "account_receivable_id": ar.id if ar else None,
        "outstanding_amount": ar.outstanding_amount if ar else None,
        "payment_status": ar.status if ar else ("LEGACY_INVOICE" if transaction.transaction_type == "INVOICE" and transaction.status == "POSTED" else None),
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
    query = apply_location_scope(db.query(Location), Location.id, user).filter(Location.is_active.is_(True))
    unit = business_unit_scope(db, user)
    if unit is not None:
        query = query.filter(Location.business_unit_id == unit)
    locations = query.order_by(Location.name).all()
    links = db.query(LocationDepartment, Department).join(Department, Department.id == LocationDepartment.department_id).filter(Department.is_active.is_(True), LocationDepartment.location_id.in_([row.id for row in locations])).all()
    assigned_department = department_scope(user)
    links = [(link, dept) for link, dept in links if assigned_department in (None, dept.id)]
    return {"locations": [{"id": row.id, "name": row.name, "business_unit_id": row.business_unit_id,
                "catalog_type": "HOTEL" if "hotel" in (db.get(BusinessUnit, row.business_unit_id).name if row.business_unit_id else "").casefold() else "CATERING"} for row in locations],
            "departments": [{"id": dept.id, "name": dept.name, "location_id": link.location_id} for link, dept in links]}


@router.get("/revenue-accounts")
def pos_revenue_accounts(location_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    SalesTransactionService._require(user, "pos.view")
    scope = resolve_organization_access(db, user, location_id=location_id)
    location = db.get(Location, scope["location_id"]) if scope["location_id"] else None
    if scope["location_id"] and (not location or not location.is_active):
        raise HTTPException(404, "Location not found")
    unit_id = location.business_unit_id if location else scope["business_unit_id"]
    return [{"id": account.id, "code": account.account_number, "name": account.account_name}
            for account in revenue_accounts(db, unit_id).all()]


@router.get("/billing-options")
def billing_options(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    SalesTransactionService._require(user, "pos.view")
    try:
        default = receivable_account(db).id
    except HTTPException:
        default = None
    return {"customers": [{"id":c.id,"code":c.customer_code,"name":c.customer_name} for c in db.query(Customer).filter(Customer.is_active.is_(True)).order_by(Customer.customer_name).all()],
        "receivable_accounts": [{"id":a.id,"code":a.account_number,"name":a.account_name} for a in receivable_choices(db).all()], "default_receivable_account_id":default}


@router.post("/customers", status_code=201)
def create_pos_customer(data: PosCustomerCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    SalesTransactionService._require(user, "pos.sell")
    name = data.customer_name.strip()
    if not name:
        raise HTTPException(422, "Customer name is required")
    duplicate = db.query(Customer).filter(func.lower(Customer.customer_name) == name.casefold()).first()
    if duplicate:
        raise HTTPException(409, "Customer already exists; select it from the list")
    customer = Customer(customer_code=f"POS-{uuid4().hex[:16].upper()}", customer_name=name,
                        phone=data.phone, email=data.email, address=data.address, is_active=True)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return {"id": customer.id, "code": customer.customer_code, "name": customer.customer_name}


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
    if location_id and (not location or not location.is_active):
        raise HTTPException(422, "Select an active sales location")
    scope = resolve_organization_access(db, user, location_id=location_id,
        business_unit_id=location.business_unit_id if location else None, department_id=department_id)
    department_id = scope["department_id"]
    locations = apply_location_scope(db.query(Location), Location.id, user).filter(Location.is_active.is_(True))
    if scope["business_unit_id"] is not None:
        locations = locations.filter(Location.business_unit_id == scope["business_unit_id"])
    if location_id:
        locations = locations.filter(Location.id == location_id)
    if department_id is not None:
        locations = locations.join(LocationDepartment, LocationDepartment.location_id == Location.id).filter(LocationDepartment.department_id == department_id)
    # An unfiltered menu is the union of contexts this user may actually sell in.
    # Keep catalog, location and unit predicates together to prevent cross-unit leaks.
    contexts = []
    for loc in locations.all():
        unit = db.get(BusinessUnit, loc.business_unit_id)
        if not unit or not unit.is_active:
            continue
        catalog = "HOTEL" if "hotel" in unit.name.casefold() else "CATERING"
        contexts.append(and_(Product.catalog_type == catalog,
            or_(Product.sales_location_id.is_(None), Product.sales_location_id == loc.id),
            or_(Product.sales_business_unit_id.is_(None), Product.sales_business_unit_id == loc.business_unit_id)))
    query = db.query(Product).filter(Product.is_active.is_(True), Product.item_type == "SELL",
        Product.inventory_treatment == "NON_STOCK", or_(*contexts) if contexts else false())
    from app.services import item_departments
    if item_departments.available(db) and department_id is not None:
        query = query.outerjoin(ItemDepartment, ItemDepartment.product_id == Product.id).filter(or_(ItemDepartment.department_id.is_(None), ItemDepartment.department_id == department_id))
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Product.code.ilike(term), Product.name.ilike(term)))
    if group_name:
        query = query.filter(Product.group_name == group_name)
    total = query.count()
    rows = query.order_by(Product.group_name, Product.name, Product.code).offset((page-1)*page_size).limit(page_size).all()
    ownership = item_departments.payloads(db, [p.id for p in rows])
    items = []
    pbjt_error = None
    if any(Decimal(p.pbjt_rate or 0) > 0 for p in rows):
        try:
            pbjt_account(db)
        except HTTPException as exc:
            pbjt_error = exc.detail
    for p in rows:
        reason = "Set selling price" if p.selling_price <= 0 else None
        tax_type, rate = "NONE", Decimal(0)
        try:
            tax_type, rate = tax_profile(p)
            if tax_type == "PBJT" and pbjt_error:
                reason = pbjt_error
        except HTTPException as exc:
            reason = exc.detail
        items.append({"sales_location_id": p.sales_location_id, "sales_business_unit_id": p.sales_business_unit_id, "catalog_type": p.catalog_type,
            **ownership.get(p.id, {}), "product_id": p.id, "product_code": p.code, "product_name": p.name,
            "group_name": p.group_name, "uom": p.uom, "selling_price": p.selling_price,
            "service_charge_rate": p.service_charge_rate, "tax_type": tax_type,
            "tax_rate": rate, "is_taxable": rate > 0, "sale_available": reason is None,
            "unavailable_reason": reason})
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
    query = SalesTransactionService.scoped_query(db, user)
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
        SalesTransactionService.scoped_query(db, user)
        .with_entities(SalesTransaction.status, func.count(SalesTransaction.id))
        .group_by(SalesTransaction.status)
        .all()
    )
    totals_filter = (
        SalesTransactionService.scoped_query(db, user).filter(
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
        SalesTransactionService.scoped_query(db, user)
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
        SalesTransactionService.scoped_query(db, user)
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
        SalesTransactionService.scoped_query(db, user)
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
        SalesTransactionService.scoped_query(db, user)
        .filter(SalesTransaction.id == sale_id)
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="POS sale not found")
    payload = serialize_sale(transaction)
    payload["printed_by"] = (user.full_name or user.username) if user else "System"
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    return payload


@router.post("/{transaction_id}/correct-to-ar")
def correct_invoice_to_ar(transaction_id: int, data: InvoiceARCorrection, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    SalesTransactionService._require(user,"finance.manage")
    tx=SalesTransactionService._get(db,transaction_id,lock=True,user=user)
    return serialize_sale(correct_posted_invoice(db,tx,data,user))

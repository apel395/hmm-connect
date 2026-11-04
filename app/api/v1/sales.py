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
    SalesTransactionItemIn,
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
from app.services import department_outlets
from app.schemas.catering_billing import CateringLocationSettings

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
            "description": line.description, "registration_number": line.registration_number,
            "service_period_from": line.service_period_from, "service_period_to": line.service_period_to,
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
    department = object_session(transaction).get(Department,transaction.department_id) if transaction.department_id else None
    ar = object_session(transaction).query(AccountReceivable).filter_by(source_sale_id=transaction.id).first()
    return {
        "id": transaction.id,
        "pos_table_id": transaction.pos_table_id, "cashier_session_id": transaction.cashier_session_id,
        "order_mode": transaction.order_mode, "event_name": transaction.event_name, "order_request_key": transaction.order_request_key,
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
        "department_name": department.name if department else None,
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
        "billing_details": transaction.billing_details,
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
    outlet_labels = department_outlets.labels(db)
    from app.services.pos_outlet_setup import is_food_beverage
    fnb_parents = {d.id for d in db.query(Department).filter(Department.is_active.is_(True)) if is_food_beverage(d)}
    fnb_outlets = {id for id, label in outlet_labels.items() if label['parent_department_id'] in fnb_parents}
    outlet_locations = {link.location_id for link, dept in links if dept.id in outlet_labels}
    return {"locations": [{"id": row.id, "name": row.name, "business_unit_id": row.business_unit_id,
                "catalog_type": "HOTEL" if "hotel" in (db.get(BusinessUnit, row.business_unit_id).name if row.business_unit_id else "").casefold() else "CATERING",
                "has_outlets": row.id in outlet_locations} for row in locations],
            "departments": [{"id": dept.id, "name": dept.name, "location_id": link.location_id,
                "code": dept.code, "is_fnb_outlet": dept.id in fnb_outlets,
                "is_outlet": dept.id in outlet_labels, **department_outlets.payload(db, dept)} for link, dept in links]}


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
    return {"customers": [{"id":c.id,"code":c.customer_code,"name":c.customer_name,"address":c.address} for c in db.query(Customer).filter(Customer.is_active.is_(True)).order_by(Customer.customer_name).all()],
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


class CateringOrderContext(BaseModel):
    department_id: int | None = Field(default=None, gt=0)
    items: list[SalesTransactionItemIn] = Field(default_factory=list, max_length=200)


@router.get("/catering-locations/{location_id}")
def catering_defaults(location_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    SalesTransactionService._require(user, "pos.view")
    from app.dependencies.authorization import has_permission
    from app.services.catering_billing import catering_location, settings
    loc = catering_location(db, user, location_id)
    config = settings(db, location_id).model_dump(mode="json")
    # Services can be explicitly shared into this location without duplicating Item Master.
    services = db.query(Product).filter(Product.is_active.is_(True), Product.item_type == "SELL",
        Product.catalog_type == "CATERING", Product.inventory_treatment == "NON_STOCK",
        or_(Product.sales_business_unit_id.is_(None), Product.sales_business_unit_id == loc.business_unit_id),
        or_(Product.sales_location_id.is_(None), Product.sales_location_id.in_(
            db.query(Location.id).filter(Location.business_unit_id == loc.business_unit_id)))).order_by(Product.name).all()
    return {"configuration":config, "can_manage":has_permission(user, "finance.manage"),
        "service_choices":[{"id":p.id,"code":p.code,"name":p.name} for p in services]}


@router.put("/catering-locations/{location_id}")
def save_catering_defaults(location_id: int, data: CateringLocationSettings,
    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    SalesTransactionService._require(user, "finance.manage")
    SalesTransactionService._require(user, "pos.view")
    from app.models.catering_billing import CateringLocationBilling
    from app.services.catering_billing import catering_location
    from app.services.audit import record_audit
    loc = catering_location(db, user, location_id, data.department_id)
    if data.department_id:
        from app.services.organization_dimensions import validate_dimensions
        validate_dimensions(db, loc.business_unit_id, loc.id, data.department_id, False)
    if data.customer_id:
        customer = db.get(Customer, data.customer_id)
        if not customer or not customer.is_active:
            raise HTTPException(422, "Choose an active customer")
    if data.revenue_account_id:
        from app.models.chart_of_account import ChartOfAccount
        from app.services.pos_revenue import validate_revenue
        validate_revenue(db, db.get(ChartOfAccount, data.revenue_account_id), loc.business_unit_id)
    if data.receivable_account_id:
        receivable_account(db, data.receivable_account_id)
    for product_id in data.service_product_ids:
        product = db.get(Product, product_id)
        source_location = db.get(Location, product.sales_location_id) if product and product.sales_location_id else None
        if not product or not product.is_active or product.item_type != 'SELL' or product.catalog_type != 'CATERING' or product.inventory_treatment != 'NON_STOCK' or product.sales_business_unit_id not in (None, loc.business_unit_id) or (source_location and source_location.business_unit_id != loc.business_unit_id):
            raise HTTPException(422, "Choose active NON_STOCK Catering services in the same business unit")
    # Lock the parent as well, serializing first-time inserts for this location.
    db.query(Location).filter_by(id=location_id).with_for_update().one()
    row = db.get(CateringLocationBilling, location_id)
    before = row.configuration if row else None
    if row is None:
        row = CateringLocationBilling(location_id=location_id)
        db.add(row)
    row.configuration = data.model_dump(mode="json")
    record_audit(db, user, "CATERING_BILLING_SETTINGS_UPDATED", "LOCATION", f"Updated Catering billing defaults for {loc.name}",
        entity_id=location_id, before_data=before, after_data=row.configuration)
    db.commit()
    return {"configuration":row.configuration}


@router.post("/catering-locations/{location_id}/validate-order")
def validate_catering_context(location_id: int, data: CateringOrderContext,
    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    SalesTransactionService._require(user, "pos.sell")
    from app.services.catering_billing import catering_location
    loc = catering_location(db, user, location_id, data.department_id)
    context = SalesTransactionCreate(transaction_type="INVOICE", location_id=loc.id,
        department_id=data.department_id, items=data.items)
    context = SalesTransactionService._master_dimensions(db, context)
    unit_id, loc_id, dept_id = SalesTransactionService._dimensions(db, None, context, user)
    transaction = SalesTransaction(transaction_type="INVOICE", location_id=loc_id, business_unit_id=unit_id, department_id=dept_id)
    for line in data.items:
        SalesTransactionService._sell_item(db, db.get(Product, line.product_id), transaction)
    return {"location_id":loc_id, "business_unit_id":unit_id, "department_id":dept_id}


@router.get("/products")
def list_pos_products(
    location_id: int | None = None,
    department_id: int | None = None,
    search: str | None = Query(default=None, max_length=100),
    group_name: str | None = Query(default=None, max_length=100),
    transaction_type: str | None = Query(default=None, pattern="^(POS|INVOICE)$"),
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
        from app.services.catering_billing import shared_service_ids
        shared_ids = shared_service_ids(db, loc.id) if catalog == "CATERING" and transaction_type == "INVOICE" else []
        contexts.append(and_(Product.catalog_type == catalog,
            or_(Product.sales_location_id.is_(None), Product.sales_location_id == loc.id, Product.id.in_(shared_ids)),
            or_(Product.sales_business_unit_id.is_(None), Product.sales_business_unit_id == loc.business_unit_id)))
    query = db.query(Product).filter(Product.is_active.is_(True), Product.item_type == "SELL",
        Product.inventory_treatment == "NON_STOCK", or_(*contexts) if contexts else false())
    from app.services import item_departments
    if item_departments.available(db) and department_id is not None:
        query = query.outerjoin(ItemDepartment, ItemDepartment.product_id == Product.id).filter(or_(ItemDepartment.department_id.is_(None), ItemDepartment.department_id == department_id, Product.id.in_(shared_service_ids(db, location_id) if location_id and transaction_type == "INVOICE" and location and "hotel" not in db.get(BusinessUnit, location.business_unit_id).name.casefold() else [])))
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
    target_shared = set(shared_service_ids(db, location_id)) if location_id and transaction_type == "INVOICE" and location and "hotel" not in db.get(BusinessUnit, location.business_unit_id).name.casefold() else set()
    for p in rows:
        flexible_price = transaction_type == "INVOICE" and p.catalog_type == "CATERING"
        reason = "Set selling price" if p.selling_price <= 0 and not flexible_price else None
        tax_type, rate = "NONE", Decimal(0)
        try:
            tax_type, rate = tax_profile(p)
            if tax_type == "PBJT" and pbjt_error:
                reason = pbjt_error
        except HTTPException as exc:
            reason = exc.detail
        is_shared = transaction_type == "INVOICE" and p.catalog_type == "CATERING" and location_id and p.id in target_shared
        items.append({"catering_shared": bool(is_shared), "sales_location_id": p.sales_location_id, "sales_business_unit_id": p.sales_business_unit_id, "catalog_type": p.catalog_type,
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
    department_id: int | None = None,
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
    if department_id:
        query = query.filter(SalesTransaction.department_id == department_id)
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

    status_query = SalesTransactionService.scoped_query(db, user)
    if location_id:
        status_query = status_query.filter(SalesTransaction.location_id == location_id)
    if department_id:
        status_query = status_query.filter(SalesTransaction.department_id == department_id)
    if date_from:
        status_query = status_query.filter(SalesTransaction.sale_date >= date_from)
    if date_to:
        status_query = status_query.filter(SalesTransaction.sale_date <= date_to)
    summary_rows = status_query.with_entities(SalesTransaction.status, func.count(SalesTransaction.id)).group_by(SalesTransaction.status).all()
    totals_filter = (
        SalesTransactionService.scoped_query(db, user).filter(
            SalesTransaction.status == "POSTED"
        )
    )
    if location_id:
        totals_filter = totals_filter.filter(SalesTransaction.location_id == location_id)
    if department_id:
        totals_filter = totals_filter.filter(SalesTransaction.department_id == department_id)
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
        .with_for_update()
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
    # Use the same authorized AR document for client-specific invoice printing.
    # The POS source is scoped above; the receivable is additionally scoped below.
    payload["client_invoice"] = None
    if transaction.transaction_type == "INVOICE" and payload.get("account_receivable_id"):
        from app.services.ar_invoice_service import scoped_receivables
        from app.api.v1.ar_invoice_print import invoice_payload
        receivable = scoped_receivables(db, user).filter_by(id=payload["account_receivable_id"], source_sale_id=transaction.id).first()
        if receivable:
            document = invoice_payload(db, receivable)
            if document["layout"]["template"] == "phr":
                # Collection history stays in Finance; POS only needs the invoice.
                document.pop("receipts", None)
                payload["client_invoice"] = document
    return payload


@router.post("/{transaction_id}/correct-to-ar")
def correct_invoice_to_ar(transaction_id: int, data: InvoiceARCorrection, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    SalesTransactionService._require(user,"finance.manage")
    tx=SalesTransactionService._get(db,transaction_id,lock=True,user=user)
    return serialize_sale(correct_posted_invoice(db,tx,data,user))


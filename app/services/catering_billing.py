"""Location defaults are suggestions; saved invoice details are independent snapshots."""
from fastapi import HTTPException
from app.models.business_unit import BusinessUnit
from app.models.catering_billing import CateringLocationBilling
from app.models.customer import Customer
from app.models.location import Location
from app.models.product import Product
from sqlalchemy import or_
from app.models.ar_invoice_layout import ARInvoiceLayout
from app.schemas.catering_billing import CateringBilling, CateringLocationSettings
from app.services.organization_access import resolve_organization_access


def catering_location(db, user, location_id, department_id=None):
    loc = db.get(Location, location_id)
    unit = db.get(BusinessUnit, loc.business_unit_id) if loc else None
    if not loc or not loc.is_active or not unit or not unit.is_active or "hotel" in unit.name.casefold():
        raise HTTPException(422, "Choose an active Catering location")
    resolve_organization_access(db, user, location_id=loc.id, business_unit_id=unit.id, department_id=department_id)
    return loc


def settings(db, location_id):
    row = db.get(CateringLocationBilling, location_id)
    return CateringLocationSettings(**(row.configuration if row else {}))


def shared_service_ids(db, location_id):
    loc = db.get(Location, location_id)
    if not loc:
        return []
    requested = settings(db, location_id).service_product_ids
    if not requested:
        return []
    return [row.id for row in db.query(Product).filter(Product.id.in_(requested), Product.is_active.is_(True),
        Product.item_type == 'SELL', Product.catalog_type == 'CATERING', Product.inventory_treatment == 'NON_STOCK',
        or_(Product.sales_business_unit_id.is_(None), Product.sales_business_unit_id == loc.business_unit_id),
        or_(Product.sales_location_id.is_(None), Product.sales_location_id.in_(db.query(Location.id).filter(Location.business_unit_id == loc.business_unit_id)))).all()]


def explicitly_shared(db, product, location_id):
    return product.catalog_type == "CATERING" and product.id in shared_service_ids(db, location_id)


def snapshot(db, transaction, supplied=None):
    loc = db.get(Location, transaction.location_id)
    unit = db.get(BusinessUnit, transaction.business_unit_id)
    if transaction.transaction_type != "INVOICE" or not loc or not unit or "hotel" in unit.name.casefold():
        if supplied is not None:
            raise HTTPException(422, "Billing details are supported for Catering invoices only")
        return None
    config = settings(db, loc.id).billing.model_dump(mode="json")
    customer_layout = db.get(ARInvoiceLayout, transaction.customer_id) if transaction.customer_id else None
    # Explicit client choices take precedence over the default layout.
    if customer_layout:
        config.update({k:v for k,v in customer_layout.configuration.items() if k in CateringBilling.model_fields})
    if supplied is not None:
        config.update(supplied.model_dump(mode="json"))
    customer = db.get(Customer, transaction.customer_id) if transaction.customer_id else None
    if customer:
        if not customer.is_active:
            raise HTTPException(422, "Choose an active customer")
        config['billing_name'] = config.get('billing_name') or customer.customer_name
        config['billing_address'] = config.get('billing_address') or customer.address or ''
    return CateringBilling(**config).model_dump(mode="json")

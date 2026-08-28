from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user

from app.models.chart_of_account import ChartOfAccount
from app.models.accounting_setting import AccountingSetting
from app.models.general_ledger import GeneralLedger
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.location import Location
from app.models.location_coa_mapping import ProductLocationCoaMapping, SupplierLocationCoaMapping, LocationTaxCoaMapping
from app.services.direct_coa_service import DirectCoaService

class DirectCoaSettingsInput(BaseModel):
    input_vat_account_id: int | None = None


class LocationCoaMappingInput(BaseModel):
    location_id: int
    scope: str
    product_id: int | None = None
    supplier_id: int | None = None
    inventory_account_id: int | None = None
    purchase_account_id: int | None = None
    cogs_account_id: int | None = None
    payable_account_id: int | None = None
    input_vat_account_id: int | None = None


router = APIRouter(
    prefix="/accounting",
    tags=["Accounting"],
)


@router.get("/trial-balance")
def trial_balance(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    rows = (
        db.query(
            ChartOfAccount.id,
            ChartOfAccount.account_number,
            ChartOfAccount.account_name,
            func.coalesce(func.sum(GeneralLedger.debit), 0).label("debit"),
            func.coalesce(func.sum(GeneralLedger.credit), 0).label("credit"),
        )
        .outerjoin(
            GeneralLedger,
            GeneralLedger.account_id == ChartOfAccount.id,
        )
        .group_by(
            ChartOfAccount.id,
            ChartOfAccount.account_number,
            ChartOfAccount.account_name,
        )
        .order_by(
            ChartOfAccount.account_number,
        )
        .all()
    )

    result = []

    total_debit = Decimal("0")
    total_credit = Decimal("0")

    for row in rows:

        balance = Decimal(row.debit) - Decimal(row.credit)

        result.append(
            {
                "account_id": row.id,
                "account_number": row.account_number,
                "account_name": row.account_name,
                "debit": row.debit,
                "credit": row.credit,
                "balance": balance,
            }
        )

        total_debit += Decimal(row.debit)
        total_credit += Decimal(row.credit)

    return {
        "accounts": result,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "balanced": total_debit == total_credit,
    }

@router.get("/general-ledger")
def general_ledger(
    account_id: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    query = db.query(GeneralLedger)

    if account_id:
        query = query.filter(
            GeneralLedger.account_id == account_id
        )

    entries = (
        query.order_by(
            GeneralLedger.posting_date,
            GeneralLedger.id,
        )
        .all()
    )

    return entries

@router.get("/account-ledger/{account_id}")
def account_ledger(
    account_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    entries = (
        db.query(GeneralLedger)
        .filter(
            GeneralLedger.account_id == account_id
        )
        .order_by(
            GeneralLedger.posting_date,
            GeneralLedger.id,
        )
        .all()
    )

    running = Decimal("0")

    result = []

    for e in entries:

        running += Decimal(e.debit)
        running -= Decimal(e.credit)

        result.append(
            {
                "date": e.posting_date,
                "description": e.description,
                "debit": e.debit,
                "credit": e.credit,
                "balance": running,
                "reference": e.reference_number,
            }
        )

    return result


@router.get("/direct-coa-settings")
def direct_coa_settings(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    row = db.query(AccountingSetting).filter(AccountingSetting.setting_key == "INPUT_VAT_ACCOUNT").first()
    return {"input_vat_account_id": row.account_id if row else None}


@router.put("/direct-coa-settings")
def update_direct_coa_settings(data: DirectCoaSettingsInput, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    account = db.get(ChartOfAccount, data.input_vat_account_id) if data.input_vat_account_id else None
    if not account or not account.is_active or not account.is_posting or account.account_type != "ASSET" or account.normal_balance != "DEBIT":
        raise HTTPException(422, "Input VAT COA must be an active debit-balance posting asset")
    row = db.query(AccountingSetting).filter(AccountingSetting.setting_key == "INPUT_VAT_ACCOUNT").first()
    if row:
        row.account_id = account.id
        row.description = "Direct COA for supplier-invoice input VAT"
    else:
        row = AccountingSetting(setting_key="INPUT_VAT_ACCOUNT", account_id=account.id, description="Direct COA for supplier-invoice input VAT")
        db.add(row)
    db.commit()
    return {"input_vat_account_id": row.account_id}


@router.get("/direct-coa-location-mappings")
def direct_coa_location_mappings(location_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    location = db.get(Location, location_id)
    if not location:
        raise HTTPException(404, "Location not found")
    items = db.query(ProductLocationCoaMapping).filter(ProductLocationCoaMapping.location_id == location_id).all()
    suppliers = db.query(SupplierLocationCoaMapping).filter(SupplierLocationCoaMapping.location_id == location_id).all()
    tax = db.query(LocationTaxCoaMapping).filter(LocationTaxCoaMapping.location_id == location_id).first()
    return {
        "location_id": location_id,
        "items": [{
            "product_id": row.product_id, "product_code": row.product.code, "product_name": row.product.name,
            "inventory_account_id": row.inventory_account_id, "purchase_account_id": row.purchase_account_id,
            "cogs_account_id": row.cogs_account_id,
        } for row in items],
        "suppliers": [{
            "supplier_id": row.supplier_id, "supplier_code": row.supplier.code, "supplier_name": row.supplier.name,
            "payable_account_id": row.payable_account_id,
        } for row in suppliers],
        "input_vat_account_id": tax.input_vat_account_id if tax else None,
    }


@router.put("/direct-coa-location-mappings")
def update_direct_coa_location_mapping(data: LocationCoaMappingInput, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if not db.get(Location, data.location_id):
        raise HTTPException(404, "Location not found")
    scope = data.scope.upper()
    resolver = DirectCoaService(db)

    if scope == "ITEM":
        product = db.get(Product, data.product_id) if data.product_id else None
        if not product:
            raise HTTPException(404, "Item not found")
        row = db.query(ProductLocationCoaMapping).filter(
            ProductLocationCoaMapping.product_id == product.id,
            ProductLocationCoaMapping.location_id == data.location_id,
        ).first() or ProductLocationCoaMapping(product_id=product.id, location_id=data.location_id)
        row.inventory_account_id = data.inventory_account_id
        row.purchase_account_id = data.purchase_account_id
        row.cogs_account_id = data.cogs_account_id
        db.add(row)
        db.flush()
        if row.inventory_account_id: resolver.inventory_account(product, data.location_id)
        if row.purchase_account_id: resolver.expense_account(product, data.location_id)
        if row.cogs_account_id: resolver.cogs_account(product, data.location_id)
    elif scope == "SUPPLIER":
        supplier = db.get(Supplier, data.supplier_id) if data.supplier_id else None
        if not supplier or not data.payable_account_id:
            raise HTTPException(422, "Supplier and Payable COA are required")
        row = db.query(SupplierLocationCoaMapping).filter(
            SupplierLocationCoaMapping.supplier_id == supplier.id,
            SupplierLocationCoaMapping.location_id == data.location_id,
        ).first() or SupplierLocationCoaMapping(supplier_id=supplier.id, location_id=data.location_id, payable_account_id=data.payable_account_id)
        row.payable_account_id = data.payable_account_id
        db.add(row)
        db.flush()
        resolver.payable_account(supplier, data.location_id)
    elif scope == "TAX":
        if not data.input_vat_account_id:
            raise HTTPException(422, "Input VAT COA is required")
        row = db.query(LocationTaxCoaMapping).filter(LocationTaxCoaMapping.location_id == data.location_id).first()
        if row:
            row.input_vat_account_id = data.input_vat_account_id
        else:
            row = LocationTaxCoaMapping(location_id=data.location_id, input_vat_account_id=data.input_vat_account_id)
            db.add(row)
        db.flush()
        resolver.input_vat_account(data.location_id)
    else:
        raise HTTPException(422, "Scope must be ITEM, SUPPLIER, or TAX")

    db.commit()
    return direct_coa_location_mappings(data.location_id, db, current_user)

from datetime import date, datetime, timezone
from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.models.fixed_asset import FixedAsset, FixedAssetCategory, FixedAssetDepreciationRun, FixedAssetDepreciationSchedule
from app.schemas.fixed_asset import AssetInput, AssetUpdate, CapitalizeInput, CategoryAssignmentInput, CategoryInput, DisposalInput, RunInput, TransferInput, WriteOffInput
from app.services.document_number import next_document_number
from app.services.fixed_asset_service import DepreciationRunService, FixedAssetService, ZERO
from app.services.invoice_asset_registration import sync_posted_invoice_assets
from app.services.organization_access import resolve_organization_access


router = APIRouter(prefix="/fixed-assets", tags=["Fixed Assets"])
reports_router = APIRouter(prefix="/reports", tags=["Fixed Asset Reports"])


def access(user):
    if not has_permission(user, "finance.manage"):
        raise HTTPException(403, "Finance access required")


@router.get("/categories")
def categories(db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    return db.query(FixedAssetCategory).order_by(FixedAssetCategory.code).all()


@router.post("/categories")
def create_category(data: CategoryInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    item = FixedAssetService(db).create_category(data)
    db.commit(); db.refresh(item)
    return item


@router.patch("/categories/{category_id}")
def update_category(category_id: int, data: CategoryInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    item = db.get(FixedAssetCategory, category_id)
    if not item:
        raise HTTPException(404, "Category not found")
    data=data.model_copy(update={"code":data.code.strip().upper(),"name":data.name.strip()})
    if db.query(FixedAssetCategory).filter(FixedAssetCategory.code==data.code,FixedAssetCategory.id!=category_id).first(): raise HTTPException(409,"Asset category code already exists")
    FixedAssetService(db).validate_accounts(data)
    for key, value in data.model_dump().items(): setattr(item, key, value)
    db.commit(); db.refresh(item)
    return item


@router.post("/sync-invoice-assets")
def sync_invoice_assets(db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    created = sync_posted_invoice_assets(db, user=user)
    db.commit()
    return {"registered": created}


@router.get("")
def listing(page: int = 1, page_size: int = 20, search: str | None = None, status: str | None = None, business_unit_id: int | None = None, location_id: int | None = None, department_id: int | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    scope=resolve_organization_access(db,user,location_id=location_id,business_unit_id=business_unit_id,department_id=department_id)
    location_id,business_unit_id,department_id=scope["location_id"],scope["business_unit_id"],scope["department_id"]
    query = db.query(FixedAsset)
    if search:
        query = query.filter(or_(FixedAsset.asset_number.ilike(f"%{search}%"), FixedAsset.asset_name.ilike(f"%{search}%"), FixedAsset.serial_number.ilike(f"%{search}%")))
    for column, value in ((FixedAsset.status, status), (FixedAsset.business_unit_id, business_unit_id), (FixedAsset.location_id, location_id), (FixedAsset.department_id, department_id)):
        if value is not None: query = query.filter(column == value)
    total = query.count(); service = FixedAssetService(db)
    return {"items": [service.serialize(item) for item in query.order_by(FixedAsset.id.desc()).offset((page - 1) * page_size).limit(page_size)], "page": page, "page_size": page_size, "total_items": total, "total_pages": ceil(total / page_size) if total else 0}


@router.post("", status_code=201)
def create(data: AssetInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    data=data.model_copy(update=resolve_organization_access(db,user,location_id=data.location_id,business_unit_id=data.business_unit_id,department_id=data.department_id))
    item = FixedAssetService(db).create_asset(data, user)
    db.commit(); db.refresh(item)
    return FixedAssetService(db).serialize(FixedAssetService(db).get(item.id))


@router.get("/depreciation-runs")
def runs(db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    scope=resolve_organization_access(db,user)
    query=db.query(FixedAssetDepreciationRun)
    for key in ("location_id","business_unit_id"):
        if scope[key] is not None: query=query.filter(getattr(FixedAssetDepreciationRun,key)==scope[key])
    return query.order_by(FixedAssetDepreciationRun.id.desc()).all()


@router.post("/depreciation-runs")
def create_run(data: RunInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    values=data.model_dump()
    scope=resolve_organization_access(db,user,location_id=data.location_id,business_unit_id=data.business_unit_id)
    values.update({key:scope[key] for key in ("location_id","business_unit_id")})
    run = FixedAssetDepreciationRun(run_number=next_document_number(db, "FADR"), created_by_id=user.id, **values)
    db.add(run); db.commit(); db.refresh(run)
    return run


def get_run(run_id: int, db: Session, user=None):
    run = db.get(FixedAssetDepreciationRun, run_id)
    if not run: raise HTTPException(404, "Depreciation run not found")
    if user is not None:
        scope=resolve_organization_access(db,user,location_id=run.location_id,business_unit_id=run.business_unit_id)
        if any(scope[key] is not None and getattr(run,key) != scope[key] for key in ("location_id","business_unit_id")): raise HTTPException(404,"Depreciation run not found")
    return run


@router.post("/depreciation-runs/{run_id}/calculate")
def calculate_run(run_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); run = get_run(run_id, db, user); DepreciationRunService(db).calculate(run); db.commit(); db.refresh(run); return run


@router.post("/depreciation-runs/{run_id}/post")
def post_run(run_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); run = get_run(run_id, db, user); DepreciationRunService(db).post(run, user); db.commit(); db.refresh(run); return run


def scoped_asset(service, asset_id, user):
    asset=service.get(asset_id)
    scope = resolve_organization_access(service.db,user,location_id=asset.location_id,business_unit_id=asset.business_unit_id,department_id=asset.department_id)
    if asset.status == "PENDING_REGISTRATION" and asset.business_unit_id is None and any(value is not None for value in scope.values()):
        raise HTTPException(403, "Unassigned asset registration requires global finance access")
    return asset


@router.get("/{asset_id}")
def detail(asset_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); return FixedAssetService(db).serialize(scoped_asset(FixedAssetService(db),asset_id,user))


@router.patch("/{asset_id}")
def update(asset_id: int, data: AssetUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); service = FixedAssetService(db); item = scoped_asset(service,asset_id,user)
    if item.status != "DRAFT": raise HTTPException(409, "Only draft assets can be edited")
    values = data.model_dump(exclude_unset=True)
    if "product_id" in values:
        from app.services.asset_item_master import ensure_asset_item
        if not values["product_id"]: raise HTTPException(422, "An asset must retain its BUY item link")
        product = ensure_asset_item(db, name=item.asset_name, account_id=item.asset_account_id, product_id=values["product_id"], user=user)
        if item.source_invoice_line_id and item.product_id != product.id:
            raise HTTPException(409, "Repair source invoice and asset links together; source item cannot be changed here")
    from app.services.organization_dimensions import validate_dimensions
    validate_dimensions(db, values.get("business_unit_id", item.business_unit_id), values.get("location_id", item.location_id), values.get("department_id", item.department_id), required=True)
    for key, value in values.items(): setattr(item, key, value)
    db.commit(); return service.serialize(scoped_asset(service,asset_id,user))


@router.post("/{asset_id}/complete-registration")
def complete_registration(asset_id: int, data: AssetInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    service = FixedAssetService(db)
    asset = scoped_asset(service, asset_id, user)
    values = resolve_organization_access(db, user, location_id=data.location_id, business_unit_id=data.business_unit_id, department_id=data.department_id)
    asset = service.complete_registration(asset, data.model_copy(update=values), user)
    db.commit()
    return service.serialize(service.get(asset.id))


@router.post("/{asset_id}/assign-category")
def assign_category(asset_id: int, data: CategoryAssignmentInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    service = FixedAssetService(db)
    asset = service.assign_category(scoped_asset(service,asset_id,user), data.asset_category_id)
    db.commit()
    return service.serialize(service.get(asset.id))


@router.post("/{asset_id}/capitalize")
def capitalize(asset_id: int, data: CapitalizeInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); service = FixedAssetService(db); item = service.capitalize(scoped_asset(service,asset_id,user), data, user); db.commit(); return service.serialize(service.get(item.id))


@router.post("/{asset_id}/generate-schedule")
def generate_schedule(asset_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); service = FixedAssetService(db); item = scoped_asset(service,asset_id,user); rows = service.generate_schedule(item); db.commit(); return {"asset_id": item.id, "periods": len(rows)}


@router.post("/{asset_id}/transfer")
def transfer(asset_id: int, data: TransferInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); resolve_organization_access(db,user,location_id=data.location_id,business_unit_id=data.business_unit_id,department_id=data.department_id); service = FixedAssetService(db); item = service.transfer(scoped_asset(service,asset_id,user), data, user); db.commit(); return service.serialize(service.get(item.id))


@router.post("/{asset_id}/dispose")
def dispose(asset_id: int, data: DisposalInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); service = FixedAssetService(db); result = service.dispose(scoped_asset(service,asset_id,user), data, user); db.commit(); return {"asset": service.serialize(scoped_asset(service,asset_id,user)), "journal_entry_id": result["journal"].id, "gain_loss": result["gain_loss"]}


@router.post("/{asset_id}/write-off")
def write_off(asset_id: int, data: WriteOffInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); service = FixedAssetService(db); result = service.dispose(scoped_asset(service,asset_id,user), data, user, True); db.commit(); return {"asset": service.serialize(scoped_asset(service,asset_id,user)), "journal_entry_id": result["journal"].id}


def scoped_asset_query(db, user, query):
    scope = resolve_organization_access(db, user)
    for key, value in scope.items():
        if value is not None:
            query = query.filter(getattr(FixedAsset, key) == value)
    return query


def asset_report(db: Session, user):
    return [{"id": item.id, "asset_number": item.asset_number, "asset_name": item.asset_name, "category": item.category.name if item.category else "Category setup required", "acquisition_date": item.acquisition_date, "capitalization_date": item.capitalization_date, "acquisition_cost": item.acquisition_cost, "accumulated_depreciation": item.accumulated_depreciation, "net_book_value": item.net_book_value, "residual_value": item.residual_value, "status": item.status} for item in scoped_asset_query(db,user,db.query(FixedAsset).filter(FixedAsset.status != "PENDING_REGISTRATION")).all()]


@reports_router.get("/fixed-assets")
def fixed_asset_report(db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); items = asset_report(db,user); return {"items": items, "totals": {"acquisition_cost": sum((item["acquisition_cost"] for item in items), ZERO), "accumulated_depreciation": sum((item["accumulated_depreciation"] for item in items), ZERO), "net_book_value": sum((item["net_book_value"] for item in items), ZERO)}}


@reports_router.get("/depreciation")
def depreciation_report(date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); query = scoped_asset_query(db,user,db.query(FixedAssetDepreciationSchedule).join(FixedAsset))
    if date_from: query = query.filter(FixedAssetDepreciationSchedule.period_end >= date_from)
    if date_to: query = query.filter(FixedAssetDepreciationSchedule.period_start <= date_to)
    items = [{"asset_id": row.fixed_asset_id, "asset_number": row.asset.asset_number, "asset_name": row.asset.asset_name, "period": f"{row.period_year}-{row.period_month:02d}", "opening_book_value": row.opening_book_value, "depreciation_amount": row.depreciation_amount, "accumulated_depreciation": row.accumulated_depreciation, "closing_book_value": row.closing_book_value, "journal_entry_id": row.journal_entry_id, "status": row.status} for row in query.all()]
    return {"items": items, "total_depreciation": sum((item["depreciation_amount"] for item in items), ZERO), "generated_at": datetime.now(timezone.utc)}

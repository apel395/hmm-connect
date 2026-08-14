from datetime import date, datetime, timezone
from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role
from app.models.fixed_asset import FixedAsset, FixedAssetCategory, FixedAssetDepreciationRun, FixedAssetDepreciationSchedule
from app.schemas.fixed_asset import AssetInput, AssetUpdate, CapitalizeInput, CategoryInput, DisposalInput, RunInput, TransferInput, WriteOffInput
from app.services.document_number import next_document_number
from app.services.fixed_asset_service import DepreciationRunService, FixedAssetService, ZERO


router = APIRouter(prefix="/fixed-assets", tags=["Fixed Assets"])
reports_router = APIRouter(prefix="/reports", tags=["Fixed Asset Reports"])


def access(user):
    if not has_any_role(user, "FINANCE"):
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
    FixedAssetService(db).validate_accounts(data)
    for key, value in data.model_dump().items(): setattr(item, key, value)
    db.commit(); db.refresh(item)
    return item


@router.get("")
def listing(page: int = 1, page_size: int = 20, search: str | None = None, status: str | None = None, business_unit_id: int | None = None, location_id: int | None = None, department_id: int | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
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
    item = FixedAssetService(db).create_asset(data, user)
    db.commit(); db.refresh(item)
    return FixedAssetService(db).serialize(FixedAssetService(db).get(item.id))


@router.get("/depreciation-runs")
def runs(db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    return db.query(FixedAssetDepreciationRun).order_by(FixedAssetDepreciationRun.id.desc()).all()


@router.post("/depreciation-runs")
def create_run(data: RunInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    run = FixedAssetDepreciationRun(run_number=next_document_number(db, "FADR"), created_by_id=user.id, **data.model_dump())
    db.add(run); db.commit(); db.refresh(run)
    return run


def get_run(run_id: int, db: Session):
    run = db.get(FixedAssetDepreciationRun, run_id)
    if not run: raise HTTPException(404, "Depreciation run not found")
    return run


@router.post("/depreciation-runs/{run_id}/calculate")
def calculate_run(run_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); run = get_run(run_id, db); DepreciationRunService(db).calculate(run); db.commit(); db.refresh(run); return run


@router.post("/depreciation-runs/{run_id}/post")
def post_run(run_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); run = get_run(run_id, db); DepreciationRunService(db).post(run, user); db.commit(); db.refresh(run); return run


@router.get("/{asset_id}")
def detail(asset_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); return FixedAssetService(db).serialize(FixedAssetService(db).get(asset_id))


@router.patch("/{asset_id}")
def update(asset_id: int, data: AssetUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); service = FixedAssetService(db); item = service.get(asset_id)
    if item.status != "DRAFT": raise HTTPException(409, "Only draft assets can be edited")
    values = data.model_dump(exclude_unset=True)
    from app.services.organization_dimensions import validate_dimensions
    validate_dimensions(db, values.get("business_unit_id", item.business_unit_id), values.get("location_id", item.location_id), values.get("department_id", item.department_id), required=True)
    for key, value in values.items(): setattr(item, key, value)
    db.commit(); return service.serialize(service.get(asset_id))


@router.post("/{asset_id}/capitalize")
def capitalize(asset_id: int, data: CapitalizeInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); service = FixedAssetService(db); item = service.capitalize(service.get(asset_id), data, user); db.commit(); return service.serialize(service.get(item.id))


@router.post("/{asset_id}/generate-schedule")
def generate_schedule(asset_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); service = FixedAssetService(db); item = service.get(asset_id); rows = service.generate_schedule(item); db.commit(); return {"asset_id": item.id, "periods": len(rows)}


@router.post("/{asset_id}/transfer")
def transfer(asset_id: int, data: TransferInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); service = FixedAssetService(db); item = service.transfer(service.get(asset_id), data, user); db.commit(); return service.serialize(service.get(item.id))


@router.post("/{asset_id}/dispose")
def dispose(asset_id: int, data: DisposalInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); service = FixedAssetService(db); result = service.dispose(service.get(asset_id), data, user); db.commit(); return {"asset": service.serialize(service.get(asset_id)), "journal_entry_id": result["journal"].id, "gain_loss": result["gain_loss"]}


@router.post("/{asset_id}/write-off")
def write_off(asset_id: int, data: WriteOffInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); service = FixedAssetService(db); result = service.dispose(service.get(asset_id), data, user, True); db.commit(); return {"asset": service.serialize(service.get(asset_id)), "journal_entry_id": result["journal"].id}


def asset_report(db: Session):
    return [{"id": item.id, "asset_number": item.asset_number, "asset_name": item.asset_name, "category": item.category.name, "acquisition_date": item.acquisition_date, "capitalization_date": item.capitalization_date, "acquisition_cost": item.acquisition_cost, "accumulated_depreciation": item.accumulated_depreciation, "net_book_value": item.net_book_value, "residual_value": item.residual_value, "status": item.status} for item in db.query(FixedAsset).all()]


@reports_router.get("/fixed-assets")
def fixed_asset_report(db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); items = asset_report(db); return {"items": items, "totals": {"acquisition_cost": sum((item["acquisition_cost"] for item in items), ZERO), "accumulated_depreciation": sum((item["accumulated_depreciation"] for item in items), ZERO), "net_book_value": sum((item["net_book_value"] for item in items), ZERO)}}


@reports_router.get("/depreciation")
def depreciation_report(date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user); query = db.query(FixedAssetDepreciationSchedule).join(FixedAsset)
    if date_from: query = query.filter(FixedAssetDepreciationSchedule.period_end >= date_from)
    if date_to: query = query.filter(FixedAssetDepreciationSchedule.period_start <= date_to)
    items = [{"asset_id": row.fixed_asset_id, "asset_number": row.asset.asset_number, "asset_name": row.asset.asset_name, "period": f"{row.period_year}-{row.period_month:02d}", "opening_book_value": row.opening_book_value, "depreciation_amount": row.depreciation_amount, "accumulated_depreciation": row.accumulated_depreciation, "closing_book_value": row.closing_book_value, "journal_entry_id": row.journal_entry_id, "status": row.status} for row in query.all()]
    return {"items": items, "total_depreciation": sum((item["depreciation_amount"] for item in items), ZERO), "generated_at": datetime.now(timezone.utc)}

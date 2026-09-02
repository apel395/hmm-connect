from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.chart_of_account import ChartOfAccount
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.schemas.fiscal_account import (
    FiscalAccountCreate, FiscalAccountPage, FiscalAccountRead, FiscalAccountUpdate,
    FiscalMappingCreate, FiscalMappingPage, FiscalMappingRead,
)
from app.services.audit import record_audit
from app.services.fiscal_account_service import FiscalAccountService

router = APIRouter(prefix="/fiscal", tags=["Fiscal Chart of Accounts"])


def require_fiscal_view(user):
    if not has_permission(user, "fiscal.view"):
        raise HTTPException(status_code=403, detail="Fiscal access required")


def require_fiscal_manage(user):
    if not has_permission(user, "fiscal.manage"):
        raise HTTPException(status_code=403, detail="Fiscal manage access required")


@router.get("/accounts", response_model=FiscalAccountPage)
def list_accounts(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    search: str | None = None, category: str | None = None,
    is_active: bool | None = None, is_header: bool | None = None,
    sort_by: Literal["code", "name", "category", "sort_order", "created_at"] = "sort_order",
    sort_order: Literal["asc", "desc"] = "asc",
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    if not has_permission(_user, "fiscal.view"):
        raise HTTPException(status_code=403, detail="Fiscal access required")
    return FiscalAccountService(db).list(
        page=page, page_size=page_size, search=search, category=category,
        is_active=is_active, is_header=is_header, sort_by=sort_by, sort_order=sort_order,
    )


@router.get("/categories", response_model=list[str])
def list_categories(
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    if not has_permission(_user, "fiscal.view"):
        raise HTTPException(status_code=403, detail="Fiscal access required")
    return FiscalAccountService(db).categories()


@router.get("/accounts/{account_id}", response_model=FiscalAccountRead)
def get_account(
    account_id: int, db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    if not has_permission(_user, "fiscal.view"):
        raise HTTPException(status_code=403, detail="Fiscal access required")
    return FiscalAccountService.serialize(FiscalAccountService(db).get_or_404(account_id))


@router.post("/accounts", response_model=FiscalAccountRead, status_code=status.HTTP_201_CREATED)
def create_account(
    data: FiscalAccountCreate, db: Session = Depends(get_db), user=Depends(get_current_user),
):
    require_fiscal_manage(user)
    service = FiscalAccountService(db)
    account = service.create(data)
    record_audit(db, user, "FISCAL_COA_CREATED", "FISCAL_ACCOUNT",
                 f"Created fiscal COA {account.code}")
    return service.serialize(account)


@router.patch("/accounts/{account_id}", response_model=FiscalAccountRead)
def update_account(
    account_id: int, data: FiscalAccountUpdate,
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    require_fiscal_manage(user)
    service = FiscalAccountService(db)
    account = service.update(account_id, data)
    record_audit(db, user, "FISCAL_COA_UPDATED", "FISCAL_ACCOUNT",
                 f"Updated fiscal COA {account.code}")
    return service.serialize(account)


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: int, db: Session = Depends(get_db), user=Depends(get_current_user),
):
    require_fiscal_manage(user)
    service = FiscalAccountService(db)
    account = service.get_or_404(account_id)
    service.delete(account_id)
    record_audit(db, user, "FISCAL_COA_DELETED", "FISCAL_ACCOUNT",
                 f"Deleted fiscal COA {account.code}")


@router.get("/mappings", response_model=FiscalMappingPage)
def list_mappings(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    search: str | None = None, fiscal_account_id: int | None = None,
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    if not has_permission(_user, "fiscal.view"):
        raise HTTPException(status_code=403, detail="Fiscal access required")
    return FiscalAccountService(db).list_mappings(
        page=page, page_size=page_size, search=search,
        fiscal_account_id=fiscal_account_id, unmapped_only=False,
    )


@router.get("/mappings/unmapped-commercial", response_model=dict)
def unmapped_commercial(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
    search: str | None = None,
    db: Session = Depends(get_db), _user=Depends(get_current_user),
):
    if not has_permission(_user, "fiscal.view"):
        raise HTTPException(status_code=403, detail="Fiscal access required")
    return FiscalAccountService(db).unmapped_commercial(
        page=page, page_size=page_size, search=search,
    )


@router.post("/mappings", response_model=FiscalMappingRead, status_code=status.HTTP_201_CREATED)
def create_mapping(
    data: FiscalMappingCreate, db: Session = Depends(get_db), user=Depends(get_current_user),
):
    require_fiscal_manage(user)
    service = FiscalAccountService(db)
    mapping = service.create_mapping(data)
    record_audit(db, user, "FISCAL_MAPPING_CREATED", "FISCAL_ACCOUNT_MAPPING",
                 f"Mapped commercial account {mapping.commercial_account_id} to fiscal "
                 f"account {mapping.fiscal_account_id}")
    fiscal = service.get_or_404(mapping.fiscal_account_id)
    commercial = db.get(ChartOfAccount, mapping.commercial_account_id)
    return FiscalMappingRead(
        id=mapping.id,
        fiscal_account_id=fiscal.id,
        fiscal_code=fiscal.code,
        fiscal_name=fiscal.name,
        commercial_account_id=commercial.id,
        commercial_code=commercial.account_number,
        commercial_name=commercial.account_name,
    )


@router.delete("/mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mapping(
    mapping_id: int, db: Session = Depends(get_db), user=Depends(get_current_user),
):
    require_fiscal_manage(user)
    service = FiscalAccountService(db)
    service.delete_mapping(mapping_id)
    record_audit(db, user, "FISCAL_MAPPING_DELETED", "FISCAL_ACCOUNT_MAPPING",
                 f"Deleted fiscal mapping {mapping_id}")
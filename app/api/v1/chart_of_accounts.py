from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.chart_of_account import (
    AccountType, ChartOfAccountCreate, ChartOfAccountLookup, ChartOfAccountPage,
    ChartOfAccountRead, ChartOfAccountTree, ChartOfAccountUpdate,
)
from app.services.audit import record_audit
from app.services.chart_of_account_service import ChartOfAccountService

router = APIRouter(prefix="/chart-of-accounts", tags=["Chart of Accounts"])


@router.get("", response_model=ChartOfAccountPage)
def list_accounts(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    search: str | None = None, account_type: AccountType | None = None,
    is_active: bool | None = None, parent_account_id: int | None = None,
    sort_by: Literal["account_code", "account_name", "account_type", "normal_balance", "is_active", "created_at", "updated_at"] = "account_code",
    sort_order: Literal["asc", "desc"] = "asc",
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    return ChartOfAccountService(db).list(page=page, page_size=page_size, search=search,
        account_type=account_type, is_active=is_active, parent_account_id=parent_account_id,
        sort_by=sort_by, sort_order=sort_order)


@router.get("/tree", response_model=list[ChartOfAccountTree])
def account_tree(is_active: bool | None = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return ChartOfAccountService(db).tree(is_active)


@router.get("/lookup", response_model=list[ChartOfAccountLookup])
def account_lookup(search: str | None = None, is_active: bool = True,
                   db: Session = Depends(get_db), _=Depends(get_current_user)):
    return ChartOfAccountService(db).lookup(search, is_active)


@router.get("/{account_id}", response_model=ChartOfAccountRead)
def get_account(account_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return ChartOfAccountService.serialize(ChartOfAccountService(db).get_or_404(account_id))


@router.post("", response_model=ChartOfAccountRead, status_code=status.HTTP_201_CREATED)
def create_account(data: ChartOfAccountCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    service = ChartOfAccountService(db)
    account = service.create(data)
    record_audit(db, user, "COA_CREATED", "CHART_OF_ACCOUNT", f"Created COA {account.account_number}",
                 entity_id=account.id, after_data=jsonable_encoder(service.serialize(account)))
    db.commit(); db.refresh(account)
    return service.serialize(account)


@router.patch("/{account_id}", response_model=ChartOfAccountRead)
def update_account(account_id: int, data: ChartOfAccountUpdate,
                   db: Session = Depends(get_db), user=Depends(get_current_user)):
    service = ChartOfAccountService(db)
    account = service.get_or_404(account_id)
    before = jsonable_encoder(service.serialize(account))
    updated = service.update(account_id, data)
    action = "COA_ARCHIVED" if before["is_active"] and not updated.is_active else "COA_UPDATED"
    record_audit(db, user, action, "CHART_OF_ACCOUNT", f"Updated COA {updated.account_number}",
                 entity_id=updated.id, before_data=before, after_data=jsonable_encoder(service.serialize(updated)))
    db.commit(); db.refresh(updated)
    return service.serialize(updated)


@router.delete("/{account_id}", response_model=ChartOfAccountRead)
def archive_account(account_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    service = ChartOfAccountService(db)
    account = service.get_or_404(account_id)
    before = jsonable_encoder(service.serialize(account))
    archived = service.archive(account_id)
    record_audit(db, user, "COA_ARCHIVED", "CHART_OF_ACCOUNT", f"Archived COA {archived.account_number}",
                 entity_id=archived.id, before_data=before, after_data=jsonable_encoder(service.serialize(archived)))
    db.commit(); db.refresh(archived)
    return service.serialize(archived)

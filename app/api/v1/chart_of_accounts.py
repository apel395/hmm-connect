from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
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


def require_finance_access(user):
    if not {role.name for role in user.roles}.intersection({"FINANCE", "ADMIN"}):
        raise HTTPException(status_code=403, detail="Finance access required")


@router.get("", response_model=ChartOfAccountPage)
def list_accounts(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    search: str | None = None, account_type: AccountType | None = None,
    normal_balance: Literal["DEBIT", "CREDIT"] | None = None,
    is_posting: bool | None = None,
    is_active: bool | None = None, parent_account_id: int | None = None,
    sort_by: Literal["account_code", "account_name", "account_type", "normal_balance", "is_active", "created_at", "updated_at"] = "account_code",
    sort_order: Literal["asc", "desc"] = "asc",
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    return ChartOfAccountService(db).list(page=page, page_size=page_size, search=search,
        account_type=account_type, normal_balance=normal_balance, is_posting=is_posting,
        is_active=is_active, parent_account_id=parent_account_id,
        sort_by=sort_by, sort_order=sort_order)


@router.get("/tree", response_model=list[ChartOfAccountTree])
def account_tree(is_active: bool | None = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return ChartOfAccountService(db).tree(is_active)


@router.get("/lookup", response_model=list[ChartOfAccountLookup])
def account_lookup(search: str | None = None, is_active: bool | None = None,
                   account_type: AccountType | None = None, account_subtype: list[str] | None = Query(None), is_posting: bool | None = None,
                   db: Session = Depends(get_db), _=Depends(get_current_user)):
    return ChartOfAccountService(db).lookup(search, is_active, account_type, is_posting, account_subtype)


@router.get("/{account_id}", response_model=ChartOfAccountRead)
def get_account(account_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return ChartOfAccountService.serialize(ChartOfAccountService(db).get_or_404(account_id))


@router.post("", response_model=ChartOfAccountRead, status_code=status.HTTP_201_CREATED)
def create_account(data: ChartOfAccountCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_finance_access(user)
    service = ChartOfAccountService(db)
    account = service.create(data)
    record_audit(db, user, "COA_CREATED", "CHART_OF_ACCOUNT", f"Created COA {account.account_number}",
                 entity_id=account.id, after_data=jsonable_encoder(service.serialize(account)))
    db.commit(); db.refresh(account)
    return service.serialize(account)


@router.patch("/{account_id}", response_model=ChartOfAccountRead)
def update_account(account_id: int, data: ChartOfAccountUpdate,
                   db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_finance_access(user)
    service = ChartOfAccountService(db)
    account = service.get_or_404(account_id)
    before = jsonable_encoder(service.serialize(account))
    updated = service.update(account_id, data)
    action = "COA_ARCHIVED" if before["is_active"] and not updated.is_active else "COA_UPDATED"
    record_audit(db, user, action, "CHART_OF_ACCOUNT", f"Updated COA {updated.account_number}",
                 entity_id=updated.id, before_data=before, after_data=jsonable_encoder(service.serialize(updated)))
    if before.get("account_subtype")!=updated.account_subtype:
        record_audit(db,user,"CASH_ACCOUNT_CLASSIFICATION_UPDATED","CHART_OF_ACCOUNT",f"Classified COA {updated.account_number} as {updated.account_subtype}",entity_id=updated.id)
    if before.get("cash_flow_category")!=updated.cash_flow_category:
        record_audit(db,user,"CASH_FLOW_CATEGORY_UPDATED","CHART_OF_ACCOUNT",f"Updated cash-flow category for {updated.account_number}",entity_id=updated.id)
    if before.get("financial_statement_group")!=updated.financial_statement_group:
        record_audit(db,user,"FINANCIAL_STATEMENT_GROUP_UPDATED","CHART_OF_ACCOUNT",f"Updated financial-statement group for {updated.account_number}",entity_id=updated.id)
    db.commit(); db.refresh(updated)
    return service.serialize(updated)


@router.delete("/{account_id}", response_model=ChartOfAccountRead)
def archive_account(account_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_finance_access(user)
    service = ChartOfAccountService(db)
    account = service.get_or_404(account_id)
    before = jsonable_encoder(service.serialize(account))
    archived = service.archive(account_id)
    record_audit(db, user, "COA_ARCHIVED", "CHART_OF_ACCOUNT", f"Archived COA {archived.account_number}",
                 entity_id=archived.id, before_data=before, after_data=jsonable_encoder(service.serialize(archived)))
    db.commit(); db.refresh(archived)
    return service.serialize(archived)


@router.patch("/{account_id}/archive", response_model=ChartOfAccountRead)
def archive_account_patch(account_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return archive_account(account_id, db, user)


@router.patch("/{account_id}/restore", response_model=ChartOfAccountRead)
def restore_account(account_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_finance_access(user)
    service = ChartOfAccountService(db)
    account = service.get_or_404(account_id)
    before = jsonable_encoder(service.serialize(account))
    restored = service.restore(account_id)
    record_audit(db, user, "COA_RESTORED", "CHART_OF_ACCOUNT", f"Restored COA {restored.account_number}",
                 entity_id=restored.id, before_data=before, after_data=jsonable_encoder(service.serialize(restored)))
    db.commit(); db.refresh(restored)
    return service.serialize(restored)

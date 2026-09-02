from __future__ import annotations

from math import ceil

from fastapi import HTTPException, status
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models.chart_of_account import ChartOfAccount
from app.models.fiscal_account import FiscalAccount, FiscalAccountMapping
from app.schemas.fiscal_account import (
    FiscalAccountCreate, FiscalAccountUpdate, FiscalMappingCreate,
)


class FiscalAccountService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def serialize(account: FiscalAccount) -> dict:
        return {
            "id": account.id,
            "code": account.code,
            "name": account.name,
            "category": account.category,
            "parent_code": account.parent_code,
            "is_header": account.is_header,
            "is_active": account.is_active,
            "sort_order": account.sort_order,
            "created_at": account.created_at,
            "updated_at": account.updated_at,
        }

    def get_or_404(self, account_id: int) -> FiscalAccount:
        account = self.db.get(FiscalAccount, account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Fiscal account not found")
        return account

    def list(
        self, *, page: int, page_size: int, search: str | None,
        category: str | None, is_active: bool | None, is_header: bool | None,
        sort_by: str, sort_order: str,
    ) -> dict:
        query = self.db.query(FiscalAccount)
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    FiscalAccount.code.ilike(term),
                    FiscalAccount.name.ilike(term),
                )
            )
        if category:
            query = query.filter(FiscalAccount.category == category)
        if is_active is not None:
            query = query.filter(FiscalAccount.is_active == is_active)
        if is_header is not None:
            query = query.filter(FiscalAccount.is_header == is_header)

        total = query.count()
        pages = max(1, ceil(total / page_size))

        sort_col = getattr(FiscalAccount, sort_by, FiscalAccount.sort_order)
        if sort_order == "desc":
            query = query.order_by(desc(sort_col), asc(FiscalAccount.sort_order))
        else:
            query = query.order_by(asc(sort_col), asc(FiscalAccount.sort_order))

        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return {
            "items": [self.serialize(a) for a in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }

    def categories(self) -> list[str]:
        rows = (
            self.db.query(FiscalAccount.category)
            .distinct()
            .order_by(asc(FiscalAccount.category))
            .all()
        )
        return [r[0] for r in rows]

    def create(self, data: FiscalAccountCreate) -> FiscalAccount:
        existing = (
            self.db.query(FiscalAccount)
            .filter(FiscalAccount.code == data.code.strip())
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Fiscal account code already exists")
        account = FiscalAccount(**data.model_dump())
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def update(self, account_id: int, data: FiscalAccountUpdate) -> FiscalAccount:
        account = self.get_or_404(account_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(account, field, value)
        self.db.commit()
        self.db.refresh(account)
        return account

    def delete(self, account_id: int) -> None:
        account = self.get_or_404(account_id)
        if account.mappings:
            raise HTTPException(
                status_code=409,
                detail="Cannot delete fiscal account with existing mappings",
            )
        self.db.delete(account)
        self.db.commit()

    def list_mappings(
        self, *, page: int, page_size: int, search: str | None,
        fiscal_account_id: int | None, unmapped_only: bool,
    ) -> dict:
        query = (
            self.db.query(
                FiscalAccountMapping,
                FiscalAccount,
                ChartOfAccount,
            )
            .join(FiscalAccount, FiscalAccountMapping.fiscal_account_id == FiscalAccount.id)
            .join(ChartOfAccount, FiscalAccountMapping.commercial_account_id == ChartOfAccount.id)
        )
        if fiscal_account_id is not None:
            query = query.filter(FiscalAccountMapping.fiscal_account_id == fiscal_account_id)
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    FiscalAccount.code.ilike(term),
                    FiscalAccount.name.ilike(term),
                    ChartOfAccount.account_number.ilike(term),
                    ChartOfAccount.account_name.ilike(term),
                )
            )

        total = query.count()
        pages = max(1, ceil(total / page_size))
        rows = (
            query.order_by(asc(FiscalAccount.sort_order), asc(ChartOfAccount.account_number))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        items = []
        for mapping, fiscal, commercial in rows:
            items.append(
                {
                    "id": mapping.id,
                    "fiscal_account_id": fiscal.id,
                    "fiscal_code": fiscal.code,
                    "fiscal_name": fiscal.name,
                    "commercial_account_id": commercial.id,
                    "commercial_code": commercial.account_number,
                    "commercial_name": commercial.account_name,
                }
            )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }

    def unmapped_commercial(self, *, page: int, page_size: int, search: str | None) -> dict:
        mapped_ids = select(FiscalAccountMapping.commercial_account_id)
        query = self.db.query(ChartOfAccount).filter(ChartOfAccount.is_active.is_(True))
        query = query.filter(ChartOfAccount.id.notin_(mapped_ids))
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    ChartOfAccount.account_number.ilike(term),
                    ChartOfAccount.account_name.ilike(term),
                )
            )
        total = query.count()
        pages = max(1, ceil(total / page_size))
        items = (
            query.order_by(asc(ChartOfAccount.account_number))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "items": [
                {
                    "id": c.id,
                    "account_code": c.account_number,
                    "account_name": c.account_name,
                    "account_type": c.account_type,
                }
                for c in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }

    def create_mapping(self, data: FiscalMappingCreate) -> FiscalAccountMapping:
        fiscal = self.get_or_404(data.fiscal_account_id)
        commercial = self.db.get(ChartOfAccount, data.commercial_account_id)
        if commercial is None:
            raise HTTPException(status_code=404, detail="Commercial account not found")
        exists = (
            self.db.query(FiscalAccountMapping)
            .filter(
                FiscalAccountMapping.fiscal_account_id == fiscal.id,
                FiscalAccountMapping.commercial_account_id == commercial.id,
            )
            .first()
        )
        if exists:
            raise HTTPException(status_code=409, detail="Mapping already exists")
        mapping = FiscalAccountMapping(
            fiscal_account_id=fiscal.id,
            commercial_account_id=commercial.id,
        )
        self.db.add(mapping)
        self.db.commit()
        self.db.refresh(mapping)
        return mapping

    def delete_mapping(self, mapping_id: int) -> None:
        mapping = self.db.get(FiscalAccountMapping, mapping_id)
        if mapping is None:
            raise HTTPException(status_code=404, detail="Fiscal mapping not found")
        self.db.delete(mapping)
        self.db.commit()
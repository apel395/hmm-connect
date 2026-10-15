from __future__ import annotations

from math import ceil

from fastapi import HTTPException, status
from sqlalchemy import asc, desc, func, inspect, or_
from sqlalchemy.orm import Session

from app.models.chart_of_account import ChartOfAccount
from app.models.accounting_setting import AccountingSetting
from app.schemas.chart_of_account import ChartOfAccountCreate, ChartOfAccountUpdate


class ChartOfAccountService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def serialize(account: ChartOfAccount) -> dict:
        return {
            "id": account.id,
            "account_code": account.account_number,
            "account_name": account.account_name,
            "account_type": account.account_type,
            "parent_account_id": account.parent_account_id,
            "normal_balance": account.normal_balance,
            "description": account.description,
            "cash_flow_category": account.cash_flow_category,
            "account_subtype": account.account_subtype,
            "financial_statement_group": account.financial_statement_group,
            "is_posting": account.is_posting,
            "is_system": account.is_system,
            "is_active": account.is_active,
            "created_at": account.created_at,
            "updated_at": account.updated_at,
        }

    def get_or_404(self, account_id: int) -> ChartOfAccount:
        account = self.db.get(ChartOfAccount, account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Chart of account not found")
        return account

    def list(self, *, page: int, page_size: int, search: str | None,
             account_type: str | None, normal_balance: str | None,
             is_posting: bool | None, is_active: bool | None,
             parent_account_id: int | None, sort_by: str, sort_order: str) -> dict:
        query = self.db.query(ChartOfAccount)
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(or_(ChartOfAccount.account_number.ilike(term),
                                     ChartOfAccount.account_name.ilike(term),
                                     ChartOfAccount.description.ilike(term)))
        if account_type:
            query = query.filter(ChartOfAccount.account_type == account_type)
        if normal_balance:
            query = query.filter(ChartOfAccount.normal_balance == normal_balance)
        if is_posting is not None:
            query = query.filter(ChartOfAccount.is_posting.is_(is_posting))
        if is_active is not None:
            query = query.filter(ChartOfAccount.is_active.is_(is_active))
        if parent_account_id is not None:
            query = query.filter(ChartOfAccount.parent_account_id == parent_account_id)

        total_items = query.count()
        columns = {
            "account_code": ChartOfAccount.account_number,
            "account_name": ChartOfAccount.account_name,
            "account_type": ChartOfAccount.account_type,
            "normal_balance": ChartOfAccount.normal_balance,
            "is_active": ChartOfAccount.is_active,
            "created_at": ChartOfAccount.created_at,
            "updated_at": ChartOfAccount.updated_at,
        }
        column = columns[sort_by]
        ordering = desc(column) if sort_order == "desc" else asc(column)
        rows = query.order_by(ordering, ChartOfAccount.id).offset((page - 1) * page_size).limit(page_size).all()
        return {
            "items": [self.serialize(row) for row in rows],
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": ceil(total_items / page_size) if total_items else 0,
            "has_next": page * page_size < total_items,
            "has_previous": page > 1,
        }

    def tree(self, is_active: bool | None = None) -> list[dict]:
        query = self.db.query(ChartOfAccount)
        if is_active is not None:
            query = query.filter(ChartOfAccount.is_active.is_(is_active))
        accounts = query.order_by(ChartOfAccount.account_number).all()
        nodes = {row.id: {**self.serialize(row), "children": []} for row in accounts}
        roots = []
        for row in accounts:
            node = nodes[row.id]
            if row.parent_account_id in nodes:
                nodes[row.parent_account_id]["children"].append(node)
            else:
                roots.append(node)
        return roots

    def lookup(self, search: str | None, is_active: bool | None, account_type: str | None,
               is_posting: bool | None, account_subtypes: list[str] | None = None,
               page: int = 1, page_size: int = 50) -> list[dict]:
        query = self.db.query(ChartOfAccount)
        if is_active is not None:
            query = query.filter(ChartOfAccount.is_active.is_(is_active))
        if account_type:
            query = query.filter(ChartOfAccount.account_type == account_type)
        if is_posting is not None:
            query = query.filter(ChartOfAccount.is_posting.is_(is_posting))
        if account_subtypes:
            query = query.filter(ChartOfAccount.account_subtype.in_(account_subtypes))
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(or_(ChartOfAccount.account_number.ilike(term), ChartOfAccount.account_name.ilike(term)))
        rows = (
            query.order_by(ChartOfAccount.account_number, ChartOfAccount.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return [
            {
                "id": row.id,
                "account_code": row.account_number,
                "account_name": row.account_name,
                "account_type": row.account_type,
                "normal_balance": row.normal_balance,
                "is_posting": row.is_posting,
                "is_active": row.is_active,
                "account_subtype": row.account_subtype,
                "cash_flow_category": row.cash_flow_category,
            }
            | {"financial_statement_group": row.financial_statement_group}
            for row in rows
        ]

    def create(self, payload: ChartOfAccountCreate) -> ChartOfAccount:
        if payload.account_type in {"REVENUE", "INCOME"} and payload.is_posting and payload.account_code != "400":
            raise HTTPException(422, "Revenue posting account must be 400")
        self._validate_statistic(payload.account_code, payload.account_type, payload.parent_account_id)
        if payload.account_type == "STATISTIC":
            payload = payload.model_copy(update={"is_posting": False, "normal_balance": "DEBIT", "cash_flow_category": None, "financial_statement_group": None, "account_subtype": "OTHER"})
        self._validate_unique(payload.account_code, payload.account_name)
        self._validate_parent(None, payload.parent_account_id)
        account = ChartOfAccount(
            account_number=payload.account_code,
            account_name=payload.account_name,
            account_type=payload.account_type,
            parent_account_id=payload.parent_account_id,
            normal_balance=payload.normal_balance or self._default_balance(payload.account_type),
            description=payload.description,
            is_active=payload.is_active,
            is_posting=payload.is_posting,
            is_system=False,
            cash_flow_category=payload.cash_flow_category,
            account_subtype=payload.account_subtype,
            financial_statement_group=payload.financial_statement_group,
        )
        self._validate_cash_classification(account.account_type, account.account_subtype, account.is_posting, account.is_active, account.parent_account_id)
        self._validate_statement_group(account.account_type, account.financial_statement_group)
        self.db.add(account)
        self.db.flush()
        return account

    def update(self, account_id: int, payload: ChartOfAccountUpdate) -> ChartOfAccount:
        account = self.get_or_404(account_id)
        data = payload.model_dump(exclude_unset=True)
        next_type = data.get("account_type", account.account_type)
        if (account.account_type == "STATISTIC") != (next_type == "STATISTIC"):
            raise HTTPException(409, "Create a separate account when switching between financial and statistical types")
        self._validate_statistic(data.get("account_code", account.account_number), next_type, data.get("parent_account_id", account.parent_account_id))
        if next_type == "STATISTIC":
            data.update(is_posting=False, normal_balance="DEBIT", cash_flow_category=None, financial_statement_group=None, account_subtype="OTHER")
        code = data.get("account_code", account.account_number)
        name = data.get("account_name", account.account_name)
        self._validate_unique(code, name, account.id)
        if "parent_account_id" in data:
            self._validate_parent(account.id, data["parent_account_id"])
        elif data.get("is_active") is True and not account.is_active:
            self._validate_parent(account.id, account.parent_account_id)
        if data.get("is_active") is False and account.is_active:
            self._ensure_no_active_children(account.id)
        if account.account_number == "400" and any(key in data and data[key] != value for key, value in (("account_code", "400"), ("account_type", "REVENUE"), ("normal_balance", "CREDIT"))):
            raise HTTPException(409, "Account 400 is the single credit revenue posting account")
        if data.get("is_posting") is True and account.account_number != "400":
            self._ensure_no_active_children(account.id)
        if account.is_system and any(key in data and data[key] != getattr(account, "account_number" if key == "account_code" else key) for key in ("account_code", "account_type", "normal_balance")):
            raise HTTPException(status_code=409, detail="Protected fields of a system account cannot be changed")
        if account.is_system and next_type == "STATISTIC":
            for key in ("normal_balance", "account_type", "account_code"):
                data.pop(key, None)
        if data.get("normal_balance") is None:
            data.pop("normal_balance", None)
        self._validate_cash_classification(data.get("account_type",account.account_type),data.get("account_subtype",account.account_subtype),data.get("is_posting",account.is_posting),data.get("is_active",account.is_active),data.get("parent_account_id",account.parent_account_id))
        self._validate_statement_group(data.get("account_type",account.account_type),data.get("financial_statement_group",account.financial_statement_group))
        for key, value in data.items():
            setattr(account, "account_number" if key == "account_code" else key, value)
        self.db.flush()
        return account

    def archive(self, account_id: int) -> ChartOfAccount:
        account = self.get_or_404(account_id)
        if account.is_system:
            raise HTTPException(status_code=409, detail="System accounts cannot be archived")
        self._ensure_no_active_children(account.id)
        if inspect(self.db.get_bind()).has_table(AccountingSetting.__tablename__):
            setting = self.db.query(AccountingSetting).filter(AccountingSetting.account_id == account.id).first()
            if setting:
                raise HTTPException(status_code=409, detail=f"Account is required by accounting setting '{setting.setting_key}'")
        account.is_active = False
        self.db.flush()
        return account

    def restore(self, account_id: int) -> ChartOfAccount:
        account = self.get_or_404(account_id)
        self._validate_parent(account.id, account.parent_account_id)
        account.is_active = True
        self.db.flush()
        return account

    def _validate_statistic(self, code, account_type, parent_id):
        parent = self.db.get(ChartOfAccount, parent_id) if parent_id else None
        if account_type != "STATISTIC":
            if code == "900" or code.startswith("900-") or (parent and parent.account_type == "STATISTIC"):
                raise HTTPException(422, "900 is reserved for statistical accounts")
            return
        if code == "900":
            if parent_id:
                raise HTTPException(422, "Statistic header 900 cannot have a parent")
            return
        if not code.startswith("900-") or not parent or parent.account_type != "STATISTIC":
            raise HTTPException(422, "Statistical detail accounts require code 900-* and a statistical parent")

    @staticmethod
    def _default_balance(account_type: str) -> str:
        return "DEBIT" if account_type in {"ASSET", "EXPENSE"} else "CREDIT"

    @staticmethod
    def _validate_cash_classification(account_type, subtype, is_posting, is_active, parent_account_id):
        if subtype in {"CASH","BANK","PETTY_CASH"} and account_type!="ASSET":
            raise HTTPException(status_code=422,detail="Cash-like subtypes require ASSET account type")
        if subtype in {"CASH","BANK","PETTY_CASH"} and (not is_posting or not is_active):
            raise HTTPException(status_code=422,detail="Cash-like accounts must be active posting accounts")

    @staticmethod
    def _validate_statement_group(account_type, group):
        allowed={"ASSET":{"CURRENT_ASSET","NON_CURRENT_ASSET"},"LIABILITY":{"CURRENT_LIABILITY","NON_CURRENT_LIABILITY"},"EQUITY":{"EQUITY"},"REVENUE":{"OPERATING_REVENUE","OTHER_REVENUE"},"EXPENSE":{"COST_OF_REVENUE","OPERATING_EXPENSE","OTHER_EXPENSE"}}
        if group and group not in allowed.get(account_type,set()):
            raise HTTPException(status_code=422,detail=f"Financial statement group {group} is invalid for {account_type}")

    def _validate_unique(self, code: str, name: str, exclude_id: int | None = None) -> None:
        query = self.db.query(ChartOfAccount).filter(ChartOfAccount.id != exclude_id) if exclude_id else self.db.query(ChartOfAccount)
        if query.filter(func.lower(ChartOfAccount.account_number) == code.lower()).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account code already exists")
        if query.filter(func.lower(ChartOfAccount.account_name) == name.lower()).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account name already exists")

    def _validate_parent(self, account_id: int | None, parent_id: int | None) -> None:
        if parent_id is None:
            return
        if parent_id == account_id:
            raise HTTPException(status_code=400, detail="Account cannot be its own parent")
        parent = self.db.get(ChartOfAccount, parent_id)
        if parent is None:
            raise HTTPException(status_code=404, detail="Parent account not found")
        if not parent.is_active:
            raise HTTPException(status_code=400, detail="Parent account must be active")
        preserving_legacy_revenue_parent = parent.account_number == "400" and account_id is not None and self.get_or_404(account_id).parent_account_id == parent_id
        if parent.is_posting and not preserving_legacy_revenue_parent:
            raise HTTPException(status_code=400, detail="A posting account cannot have child accounts")
        current = parent
        visited = set()
        while current is not None and current.id not in visited:
            if current.id == account_id:
                raise HTTPException(status_code=400, detail="Parent account would create a circular hierarchy")
            visited.add(current.id)
            current = self.db.get(ChartOfAccount, current.parent_account_id) if current.parent_account_id else None

    def _ensure_no_active_children(self, account_id: int) -> None:
        child = self.db.query(ChartOfAccount).filter(
            ChartOfAccount.parent_account_id == account_id,
            ChartOfAccount.is_active.is_(True),
        ).first()
        if child:
            raise HTTPException(status_code=409, detail="Cannot archive an account with active children")

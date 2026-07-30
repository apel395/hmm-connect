from sqlalchemy.orm import Session

from fastapi import HTTPException, status

from app.models.chart_of_account import ChartOfAccount
from app.schemas.chart_of_account import (
    ChartOfAccountCreate,
    ChartOfAccountUpdate,
)


class ChartOfAccountService:

    def __init__(self, db: Session):
        self.db = db

    # ----------------------------------------------------
    # Query
    # ----------------------------------------------------

    def get_all(self):
        return (
            self.db.query(ChartOfAccount)
            .order_by(ChartOfAccount.account_number)
            .all()
        )

    def get(self, account_id: int):
        return (
            self.db.query(ChartOfAccount)
            .filter(ChartOfAccount.id == account_id)
            .first()
        )

    def get_tree(self):

        accounts = (
            self.db.query(ChartOfAccount)
            .order_by(
                ChartOfAccount.account_number
            )
            .all()
        )

        lookup = {}

        for account in accounts:
            account.children = []
            lookup[account.id] = account

        roots = []

        for account in accounts:

            if account.parent_account_id:

                parent = lookup.get(account.parent_account_id)

                if parent:
                    parent.children.append(account)

            else:
                roots.append(account)

        return roots

    # ----------------------------------------------------
    # Create
    # ----------------------------------------------------

    def create(
        self,
        payload: ChartOfAccountCreate,
    ):

        self._validate_unique_number(
            payload.account_number
        )

        self._validate_unique_name(
            payload.account_name
        )

        parent = None
        level = 1

        if payload.parent_account_id:

            parent = self.get(payload.parent_account_id)

            if parent is None:
                raise HTTPException(
                    404,
                    "Parent account not found",
                )

            if parent.is_posting:
                raise HTTPException(
                    400,
                    "Parent account cannot be postable",
                )

        account = ChartOfAccount(
            account_number=payload.account_number,
            account_name=payload.account_name,
            account_type=payload.account_type,
            cash_flow_category=payload.cash_flow_category,
            parent_account_id=payload.parent_account_id,
            is_posting=payload.is_posting,
            is_active=payload.is_active,
        )

        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)

        return account

    # ----------------------------------------------------
    # Update
    # ----------------------------------------------------

    def update(
        self,
        account_id: int,
        payload: ChartOfAccountUpdate,
    ):

        account = self.get(account_id)

        if account is None:
            raise HTTPException(
                404,
                "Chart of account not found",
            )

        data = payload.model_dump(
            exclude_unset=True
        )

        if (
            "account_number" in data
            and data["account_number"]
            != account.account_number
        ):
            self._validate_unique_number(
                data["account_number"]
            )

        if (
            "account_name" in data
            and data["account_name"]
            != account.account_name
        ):
            self._validate_unique_name(
                data["account_name"]
            )

        if "parent_account_id" in data:

            parent_id = data["parent_account_id"]

            if parent_id == account.id:
                raise HTTPException(
                    400,
                    "Account cannot be its own parent",
                )

            if parent_id:

                parent = self.get(parent_id)

                if parent is None:
                    raise HTTPException(
                        404,
                        "Parent account not found",
                    )

                if parent.is_posting:
                    raise HTTPException(
                        400,
                        "Parent account cannot be postable",
                    )

        for key, value in data.items():
            setattr(account, key, value)

        self.db.commit()
        self.db.refresh(account)

        return account

    # ----------------------------------------------------
    # Delete
    # ----------------------------------------------------

    def delete(
        self,
        account_id: int,
    ):

        account = self.get(account_id)

        if account is None:
            raise HTTPException(
                404,
                "Chart of account not found",
            )

        if account.children:
            raise HTTPException(
                400,
                "Cannot delete account with children",
            )

        if account.account_receipts:
            raise HTTPException(
                400,
                "Account already used",
            )

        self.db.delete(account)
        self.db.commit()

    # ----------------------------------------------------
    # Validation
    # ----------------------------------------------------

    def _validate_unique_number(
        self,
        account_number: str,
    ):

        exists = (
            self.db.query(ChartOfAccount)
            .filter(
                ChartOfAccount.account_number
                == account_number
            )
            .first()
        )

        if exists:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Account number already exists",
            )

    def _validate_unique_name(
        self,
        account_name: str,
    ):

        exists = (
            self.db.query(ChartOfAccount)
            .filter(
                ChartOfAccount.account_name
                == account_name
            )
            .first()
        )

        if exists:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Account name already exists",
            )

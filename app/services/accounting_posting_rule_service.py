from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.accounting_posting_rule import AccountingPostingRule
from app.models.chart_of_account import ChartOfAccount


class AccountingPostingRuleService:
    BANK_SUBTYPES = {"BANK", "CASH", "CASH_AND_BANK"}

    def __init__(self, db: Session):
        self.db = db

    @classmethod
    def _validate_event_accounts(cls, event_type, debit, credit):
        if event_type == "SUPPLIER_INVOICE_INVENTORY":
            if debit.account_type != "ASSET" or debit.normal_balance != "DEBIT":
                raise HTTPException(400, "Inventory invoice debit account must be a debit-balance asset")
            if str(debit.account_subtype or "").upper() in cls.BANK_SUBTYPES:
                raise HTTPException(400, "Inventory invoice debit account cannot be a cash or bank account")
            if credit.account_type != "LIABILITY" or credit.normal_balance != "CREDIT":
                raise HTTPException(400, "Supplier invoice credit account must be a credit-balance liability")
        elif event_type == "SUPPLIER_INVOICE_DIRECT_USE":
            if debit.account_type != "EXPENSE" or debit.normal_balance != "DEBIT":
                raise HTTPException(400, "Direct-use invoice debit account must be a debit-balance expense")
            if credit.account_type != "LIABILITY" or credit.normal_balance != "CREDIT":
                raise HTTPException(400, "Supplier invoice credit account must be a credit-balance liability")
        elif event_type == "CUSTOMER_PAYMENT":
            if debit.account_type != "ASSET" or debit.normal_balance != "DEBIT":
                raise HTTPException(400, "Customer payment debit account must be a debit-balance asset")
            if credit.account_type != "ASSET" or credit.normal_balance != "DEBIT":
                raise HTTPException(400, "Customer payment credit account must be a debit-balance receivable asset")

    def validate(
        self,
        debit_id: int,
        credit_id: int,
        event_type: str,
        exclude_id: int | None = None,
        active: bool = True,
        input_vat_account_id: int | None = None,
    ):
        if debit_id == credit_id:
            raise HTTPException(400, "Debit and credit accounts must be different")
        account_ids = [debit_id, credit_id]
        if input_vat_account_id is not None:
            account_ids.append(input_vat_account_id)
        accounts = {}
        for account_id in account_ids:
            account = self.db.get(ChartOfAccount, account_id)
            if not account or not account.is_active or not account.is_posting:
                raise HTTPException(400, "Posting rules require active posting accounts")
            accounts[account_id] = account
        self._validate_event_accounts(event_type, accounts[debit_id], accounts[credit_id])
        if input_vat_account_id in {debit_id, credit_id}:
            raise HTTPException(400, "Input VAT account must be different from the main debit and credit accounts")

        query = self.db.query(AccountingPostingRule).filter(
            AccountingPostingRule.event_type == event_type,
            AccountingPostingRule.is_active.is_(True),
        )
        if exclude_id:
            query = query.filter(AccountingPostingRule.id != exclude_id)
        if active and query.first():
            raise HTTPException(409, "An active posting rule already exists for this event type")

    @staticmethod
    def serialize(row):
        return {
            "id": row.id,
            "event_type": row.event_type,
            "debit_account_id": row.debit_account_id,
            "debit_account_code": row.debit_account.account_number,
            "debit_account_name": row.debit_account.account_name,
            "credit_account_id": row.credit_account_id,
            "credit_account_code": row.credit_account.account_number,
            "credit_account_name": row.credit_account.account_name,
            "input_vat_account_id": row.input_vat_account_id,
            "input_vat_account_code": row.input_vat_account.account_number if row.input_vat_account else None,
            "input_vat_account_name": row.input_vat_account.account_name if row.input_vat_account else None,
            "description": row.description,
            "is_active": row.is_active,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

from fastapi import HTTPException
from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from app.models.accounting_posting_rule import AccountingPostingRule
from app.models.chart_of_account import ChartOfAccount


class AccountingPostingRuleService:
    BANK_SUBTYPES = {"BANK", "CASH", "CASH_AND_BANK"}
    DIRECT_USE_ASSET_FALLBACK_CODES = {"100-300-999"}
    RECEIVABLE_SUBTYPES = {"ACCOUNTS_RECEIVABLE", "RECEIVABLE", "TRADE_RECEIVABLE"}

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
            account_code = str(debit.account_number or "").strip()
            is_expense = debit.account_type == "EXPENSE" and debit.normal_balance == "DEBIT"
            is_approved_asset_fallback = (
                debit.account_type == "ASSET"
                and debit.normal_balance == "DEBIT"
                and account_code in cls.DIRECT_USE_ASSET_FALLBACK_CODES
                and str(debit.account_subtype or "").upper() not in cls.BANK_SUBTYPES
            )
            if not (is_expense or is_approved_asset_fallback):
                raise HTTPException(
                    400,
                    "Direct-use invoice debit account must be a debit-balance expense "
                    "or an approved temporary inventory fallback",
                )
            if credit.account_type != "LIABILITY" or credit.normal_balance != "CREDIT":
                raise HTTPException(400, "Supplier invoice credit account must be a credit-balance liability")
        elif event_type == "SUPPLIER_PAYMENT":
            if debit.account_type != "LIABILITY" or debit.normal_balance != "CREDIT":
                raise HTTPException(400, "Supplier payment debit account must be a credit-balance payable liability")
            if (
                credit.account_type != "ASSET"
                or credit.normal_balance != "DEBIT"
                or str(credit.account_subtype or "").upper() not in cls.BANK_SUBTYPES
            ):
                raise HTTPException(400, "Supplier payment credit account must be a debit-balance cash or bank asset")
        elif event_type == "CUSTOMER_PAYMENT":
            if debit.account_type != "ASSET" or debit.normal_balance != "DEBIT":
                raise HTTPException(400, "Customer payment debit account must be a debit-balance asset")
            if credit.account_type != "ASSET" or credit.normal_balance != "DEBIT":
                raise HTTPException(400, "Customer payment credit account must be a debit-balance receivable asset")

    @classmethod
    def validate_invoice_debit_account(cls, event_type, account, status_code=409):
        subtype = str(account.account_subtype or "").upper()
        code = str(account.account_number or "").strip()
        if subtype in cls.BANK_SUBTYPES:
            raise HTTPException(status_code, "Supplier invoice cannot debit a cash or bank account")
        if subtype in cls.RECEIVABLE_SUBTYPES or code.startswith(("100-200-", "100-210-")):
            raise HTTPException(status_code, "Supplier invoice cannot debit an accounts receivable account")
        if event_type == "SUPPLIER_INVOICE_INVENTORY":
            if account.account_type != "ASSET" or account.normal_balance != "DEBIT":
                raise HTTPException(status_code, "Inventory invoice debit account must be a debit-balance asset")
        elif event_type == "SUPPLIER_INVOICE_DIRECT_USE":
            is_expense = account.account_type == "EXPENSE" and account.normal_balance == "DEBIT"
            is_fallback = (
                account.account_type == "ASSET"
                and account.normal_balance == "DEBIT"
                and code in cls.DIRECT_USE_ASSET_FALLBACK_CODES
            )
            if not (is_expense or is_fallback):
                raise HTTPException(
                    status_code,
                    "Direct-use invoice debit account must be a debit-balance expense "
                    "or an approved temporary inventory fallback",
                )

    def select_rule(self, event_type: str, business_unit_id: int | None, location_id: int | None):
        query = self.db.query(AccountingPostingRule).filter(
            AccountingPostingRule.event_type == event_type,
            AccountingPostingRule.is_active.is_(True),
            or_(AccountingPostingRule.business_unit_id.is_(None), AccountingPostingRule.business_unit_id == business_unit_id),
            or_(AccountingPostingRule.location_id.is_(None), AccountingPostingRule.location_id == location_id),
        )
        scope_rank = case(
            (
                (AccountingPostingRule.business_unit_id == business_unit_id)
                & (AccountingPostingRule.location_id == location_id),
                4,
            ),
            (AccountingPostingRule.location_id == location_id, 3),
            (AccountingPostingRule.business_unit_id == business_unit_id, 2),
            else_=1,
        )
        return query.order_by(scope_rank.desc(), AccountingPostingRule.id.desc()).first()

    @classmethod
    def validate_source_journal_accounts(cls, event_type, debit_accounts, credit_accounts):
        event_type = str(event_type or "").upper()
        if event_type == "SUPPLIER_PAYMENT":
            for account in debit_accounts:
                if account.account_type != "LIABILITY" or account.normal_balance != "CREDIT":
                    raise HTTPException(409, "Supplier payment journal must debit a credit-balance payable liability")
            for account in credit_accounts:
                if (
                    account.account_type != "ASSET"
                    or account.normal_balance != "DEBIT"
                    or str(account.account_subtype or "").upper() not in cls.BANK_SUBTYPES
                ):
                    raise HTTPException(409, "Supplier payment journal must credit a debit-balance cash or bank asset")
        elif event_type == "SUPPLIER_INVOICE":
            for account in debit_accounts:
                subtype = str(account.account_subtype or "").upper()
                code = str(account.account_number or "").strip()
                if subtype in cls.RECEIVABLE_SUBTYPES or code.startswith(("100-200-", "100-210-")):
                    raise HTTPException(409, "Supplier invoice journal cannot debit an accounts receivable account")
                if account.normal_balance != "DEBIT" or account.account_type not in {"ASSET", "EXPENSE"}:
                    raise HTTPException(409, "Supplier invoice journal debits must use debit-balance asset or expense accounts")
                if subtype in cls.BANK_SUBTYPES:
                    raise HTTPException(409, "Supplier invoice journal cannot debit a cash or bank account")
            for account in credit_accounts:
                if account.account_type != "LIABILITY" or account.normal_balance != "CREDIT":
                    raise HTTPException(409, "Supplier invoice journal must credit a credit-balance payable liability")

    def validate(
        self,
        debit_id: int,
        credit_id: int,
        event_type: str,
        exclude_id: int | None = None,
        active: bool = True,
        input_vat_account_id: int | None = None,
        business_unit_id: int | None = None,
        location_id: int | None = None,
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
        query = query.filter(
            AccountingPostingRule.business_unit_id.is_(None)
            if business_unit_id is None
            else AccountingPostingRule.business_unit_id == business_unit_id,
            AccountingPostingRule.location_id.is_(None)
            if location_id is None
            else AccountingPostingRule.location_id == location_id,
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
            "business_unit_id": row.business_unit_id,
            "business_unit_name": row.business_unit.name if row.business_unit else None,
            "location_id": row.location_id,
            "location_name": row.location.name if row.location else None,
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

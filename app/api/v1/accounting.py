from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import require_permission

from app.models.chart_of_account import ChartOfAccount
from app.models.accounting_setting import AccountingSetting
from app.models.general_ledger import GeneralLedger

class DirectCoaSettingsInput(BaseModel):
    input_vat_account_id: int | None = None
    accounts_payable_account_id: int | None = None
    grni_account_id: int | None = None
    purchase_discount_account_id: int | None = None
    withholding_tax_payable_account_id: int | None = None


DIRECT_COA_SETTING_FIELDS = {
    "input_vat_account_id": "INPUT_VAT_ACCOUNT",
    "accounts_payable_account_id": "ACCOUNTS_PAYABLE_ACCOUNT",
    "grni_account_id": "GRNI_ACCOUNT",
    "purchase_discount_account_id": "PURCHASE_DISCOUNT_ACCOUNT",
    "withholding_tax_payable_account_id": "WITHHOLDING_TAX_PAYABLE_ACCOUNT",
}

DIRECT_COA_SETTING_DESCRIPTIONS = {
    "INPUT_VAT_ACCOUNT": "Global direct COA for supplier-invoice input VAT",
    "ACCOUNTS_PAYABLE_ACCOUNT": "Global direct COA for supplier accounts payable",
    "GRNI_ACCOUNT": "Global direct COA for goods received not invoiced",
    "PURCHASE_DISCOUNT_ACCOUNT": "Global direct COA for purchase discounts",
    "WITHHOLDING_TAX_PAYABLE_ACCOUNT": "Global direct COA for withholding tax payable",
}


router = APIRouter(
    prefix="/accounting",
    tags=["Accounting"],
)


@router.get("/trial-balance")
def trial_balance(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    rows = (
        db.query(
            ChartOfAccount.id,
            ChartOfAccount.account_number,
            ChartOfAccount.account_name,
            func.coalesce(func.sum(GeneralLedger.debit), 0).label("debit"),
            func.coalesce(func.sum(GeneralLedger.credit), 0).label("credit"),
        )
        .outerjoin(
            GeneralLedger,
            GeneralLedger.account_id == ChartOfAccount.id,
        )
        .group_by(
            ChartOfAccount.id,
            ChartOfAccount.account_number,
            ChartOfAccount.account_name,
        )
        .order_by(
            ChartOfAccount.account_number,
        )
        .all()
    )

    result = []

    total_debit = Decimal("0")
    total_credit = Decimal("0")

    for row in rows:

        balance = Decimal(row.debit) - Decimal(row.credit)

        result.append(
            {
                "account_id": row.id,
                "account_number": row.account_number,
                "account_name": row.account_name,
                "debit": row.debit,
                "credit": row.credit,
                "balance": balance,
            }
        )

        total_debit += Decimal(row.debit)
        total_credit += Decimal(row.credit)

    return {
        "accounts": result,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "balanced": total_debit == total_credit,
    }

@router.get("/general-ledger")
def general_ledger(
    account_id: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    query = db.query(GeneralLedger)

    if account_id:
        query = query.filter(
            GeneralLedger.account_id == account_id
        )

    entries = (
        query.order_by(
            GeneralLedger.posting_date,
            GeneralLedger.id,
        )
        .all()
    )

    return entries

@router.get("/account-ledger/{account_id}")
def account_ledger(
    account_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    entries = (
        db.query(GeneralLedger)
        .filter(
            GeneralLedger.account_id == account_id
        )
        .order_by(
            GeneralLedger.posting_date,
            GeneralLedger.id,
        )
        .all()
    )

    running = Decimal("0")

    result = []

    for e in entries:

        running += Decimal(e.debit)
        running -= Decimal(e.credit)

        result.append(
            {
                "date": e.posting_date,
                "description": e.description,
                "debit": e.debit,
                "credit": e.credit,
                "balance": running,
                "reference": e.reference_number,
            }
        )

    return result


def _validate_direct_setting_account(field_name: str, account: ChartOfAccount) -> None:
    if not account.is_active or not account.is_posting:
        raise HTTPException(422, "Direct COA mapping must use an active posting account")

    if field_name == "input_vat_account_id":
        valid = account.account_type == "ASSET" and account.normal_balance == "DEBIT"
        message = "Input VAT COA must be an active debit-balance posting asset"
    elif field_name in {
        "accounts_payable_account_id",
        "grni_account_id",
        "withholding_tax_payable_account_id",
    }:
        valid = account.account_type == "LIABILITY" and account.normal_balance == "CREDIT"
        labels = {
            "accounts_payable_account_id": "Accounts Payable",
            "grni_account_id": "GRNI",
            "withholding_tax_payable_account_id": "Withholding Tax Payable",
        }
        message = f"{labels[field_name]} COA must be an active credit-balance posting liability"
    else:
        valid = (
            account.account_type in {"INCOME", "EXPENSE"}
            and account.normal_balance == "CREDIT"
        )
        message = "Purchase Discount COA must be an active credit-balance posting income or contra-expense account"

    if not valid:
        raise HTTPException(422, message)


def _serialize_direct_coa_settings(db: Session) -> dict:
    rows = (
        db.query(AccountingSetting)
        .filter(AccountingSetting.setting_key.in_(DIRECT_COA_SETTING_FIELDS.values()))
        .all()
    )
    by_key = {row.setting_key: row.account_id for row in rows}
    result = {
        field_name: by_key.get(setting_key)
        for field_name, setting_key in DIRECT_COA_SETTING_FIELDS.items()
    }
    missing = [
        field_name
        for field_name, account_id in result.items()
        if account_id is None
    ]
    return {
        **result,
        "is_complete": not missing,
        "missing_settings": missing,
    }


@router.get("/direct-coa-settings")
def direct_coa_settings(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("finance.manage")),
):
    return _serialize_direct_coa_settings(db)


@router.put("/direct-coa-settings")
def update_direct_coa_settings(
    data: DirectCoaSettingsInput,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("finance.manage")),
):
    values = data.model_dump(exclude_none=True)
    if not values:
        raise HTTPException(422, "At least one direct COA setting is required")

    for field_name, account_id in values.items():
        account = db.get(ChartOfAccount, account_id)
        if not account:
            raise HTTPException(422, f"{field_name} references an unknown COA")
        _validate_direct_setting_account(field_name, account)

        setting_key = DIRECT_COA_SETTING_FIELDS[field_name]
        row = (
            db.query(AccountingSetting)
            .filter(AccountingSetting.setting_key == setting_key)
            .first()
        )
        if row:
            row.account_id = account.id
            row.description = DIRECT_COA_SETTING_DESCRIPTIONS[setting_key]
        else:
            db.add(
                AccountingSetting(
                    setting_key=setting_key,
                    account_id=account.id,
                    description=DIRECT_COA_SETTING_DESCRIPTIONS[setting_key],
                )
            )

    db.commit()
    return _serialize_direct_coa_settings(db)

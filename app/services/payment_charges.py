from decimal import Decimal
from fastapi import HTTPException
from app.models.chart_of_account import ChartOfAccount

ZERO = Decimal("0")


def funding_total(payment):
    amount = getattr(payment, "amount", None)
    if amount is None:
        amount = payment.total_amount
    return Decimal(amount) + Decimal(getattr(payment, "bank_charge_amount", 0) or 0) + Decimal(getattr(payment, "short_over_amount", 0) or 0)


def charge_entries(payment):
    """Amount is AP settlement; charges never change the invoice allocation."""
    bank = Decimal(getattr(payment, "bank_charge_amount", 0) or 0)
    short = Decimal(getattr(payment, "short_over_amount", 0) or 0)
    entries = []
    if bank:
        entries.append((payment.bank_charge_account_id, bank, ZERO, "Bank administration charge"))
    if short:
        entries.append((payment.short_over_account_id, max(short, ZERO), max(-short, ZERO), "Payment short / over"))
    return entries


def validate_charge_accounts(db, payment):
    for aid, _, _, _ in charge_entries(payment):
        account = db.get(ChartOfAccount, aid) if aid else None
        if not account or not account.is_active or not account.is_posting or account.account_type != "EXPENSE" or account.normal_balance != "DEBIT":
            raise HTTPException(422, "Bank charge and short/over require active debit expense posting accounts")
    if charge_entries(payment) and not str(getattr(payment, "difference_reason", "") or "").strip():
        raise HTTPException(422, "Enter the reason for payment charges or short/over")

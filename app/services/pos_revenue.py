"""Operating revenue choices for the sale's actual business unit."""
from fastapi import HTTPException
from sqlalchemy import or_
from app.models.business_unit import BusinessUnit
from app.models.chart_of_account import ChartOfAccount


def revenue_accounts(db, business_unit_id=None):
    query = db.query(ChartOfAccount).filter(ChartOfAccount.is_active.is_(True),
        ChartOfAccount.is_posting.is_(True), ChartOfAccount.account_type.in_(['REVENUE', 'INCOME']),
        ChartOfAccount.normal_balance == 'CREDIT')
    prefix = '400'
    if business_unit_id is not None:
        unit = db.get(BusinessUnit, business_unit_id)
        if not unit or not unit.is_active:
            raise HTTPException(404, 'Business unit not found')
        prefix = '400-100' if 'hotel' in unit.name.casefold() else '400-110'
    return query.filter(or_(ChartOfAccount.account_number == '400', ChartOfAccount.account_number.like(prefix + '-%'))).order_by(ChartOfAccount.account_number)


def validate_revenue(db, account, business_unit_id):
    if account is None or not revenue_accounts(db, business_unit_id).filter(ChartOfAccount.id == account.id).first():
        raise HTTPException(422, 'Choose an active operating revenue posting account for this sale business unit')
    return account

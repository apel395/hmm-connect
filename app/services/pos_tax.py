"""Explicit SELL tax snapshots and direct PBJT liability resolution."""
from decimal import Decimal
from fastapi import HTTPException
from app.models.chart_of_account import ChartOfAccount
from app.services.direct_coa_service import DirectCoaService


def tax_profile(product):
    pbjt = Decimal(product.pbjt_rate or 0)
    if Decimal(product.sales_ppn_rate or 0) > 0 or Decimal(product.pph23_rate or 0) > 0:
        raise HTTPException(409, 'PPN / PPh 23 sales profiles require their own posting flow')
    if pbjt > 0:
        return 'PBJT', pbjt
    rate = Decimal(product.tax_rate or 0) if product.is_taxable else Decimal(0)
    return ('PPN' if rate else 'NONE'), rate


def pbjt_account(db):
    # Explicit mappings take precedence; otherwise use the supplied menu PBJT COA, not electricity PBJT.
    # Never create an account or choose an arbitrary match.
    mapped = DirectCoaService(db).setting_account('POS_PBJT_PAYABLE_ACCOUNT', 'Hutang PBJT')
    if mapped is None:
        mapped = db.query(ChartOfAccount).filter(ChartOfAccount.account_number == '200-400-100').first()
    if mapped is None:
        raise HTTPException(409, 'Existing menu PBJT account 200-400-100 was not found; check its COA or explicit POS_PBJT_PAYABLE_ACCOUNT mapping')
    if not mapped.is_active or not mapped.is_posting or mapped.account_type != 'LIABILITY' or mapped.normal_balance != 'CREDIT':
        raise HTTPException(409, 'Hutang PBJT must be an active credit-balance liability posting account')
    return mapped

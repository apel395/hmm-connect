"""PMK 72/2023 fiscal schedules. No journal, stock or book-balance writes."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from app.models.fixed_asset import FixedAssetFiscalProfile
from app.models.chart_of_account import ChartOfAccount
from app.schemas.asset_fiscal import GROUPS
from app.services.audit import record_audit

ZERO = Decimal('0.00')
def money(value):
    return Decimal(value).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

def month_add(value, count):
    index = value.year * 12 + value.month - 1 + count
    return date(index // 12, index % 12 + 1, 1)

def profile_dict(profile):
    if not profile:
        return None
    return {key: getattr(profile, key) for key in (
        'fixed_asset_id', 'group_code', 'method', 'fiscal_cost', 'start_date',
        'useful_life_months', 'reference', 'opening_date', 'opening_book_value', 'version')}

def fiscal_schedule(profile, end_date=None):
    """Calendar-year declining balance; first year prorated; final month writes off remainder."""
    if profile.group_code == 'LAND':
        return []
    life = profile.useful_life_months or GROUPS[profile.group_code][1]
    start = profile.start_date.replace(day=1)
    final = month_add(start, life - 1)
    if profile.opening_date and profile.opening_date >= final and profile.opening_book_value:
        raise ValueError('An asset beyond fiscal useful life must have zero fiscal opening value')
    cursor = month_add(profile.opening_date, 1) if profile.opening_date else start
    balance = money(profile.opening_book_value if profile.opening_date else profile.fiscal_cost)
    annual_basis = balance
    rows = []
    while cursor <= final and (end_date is None or cursor <= end_date):
        if cursor.month == 1:
            annual_basis = balance
        if profile.method == 'DECLINING_BALANCE':
            amount = money(annual_basis * Decimal(GROUPS[profile.group_code][3]) / 100 / 12)
        else:
            amount = money(profile.fiscal_cost / life)
        amount = balance if cursor == final else min(balance, amount)
        closing = money(balance - amount)
        rows.append({'period': cursor.isoformat()[:7], 'opening': balance, 'depreciation': amount, 'closing': closing})
        balance = closing
        cursor = month_add(cursor, 1)
    return rows

def save_profile(db, asset, data, user):
    account = db.get(ChartOfAccount, asset.asset_account_id)
    code = account.account_number if account else ''
    if not code.startswith('100-600-'):
        raise HTTPException(422, 'Fiscal fixed assets require a 100-600 asset account; prepayments and utensils are excluded')
    if asset.acquisition_cost is None:
        raise HTTPException(409, 'Complete asset registration before fiscal setup')
    if (code == '100-600-100') != (data.group_code == 'LAND'):
        raise HTTPException(422, 'Land classification must match the land account')
    building = code == '100-600-101'
    if building != data.group_code.startswith('BUILDING_'):
        raise HTTPException(422, 'Building fiscal groups must match the building account')
    if data.start_date and asset.acquisition_date and data.start_date < asset.acquisition_date:
        raise HTTPException(422, 'Fiscal depreciation cannot start before acquisition')
    # Validate lifetime and snapshots before any mutation.
    from types import SimpleNamespace
    try:
        fiscal_schedule(SimpleNamespace(**data.model_dump()))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    row = db.get(FixedAssetFiscalProfile, asset.id)
    before = profile_dict(row)
    if data.expected_version != (row.version if row else 0):
        raise HTTPException(409, 'Fiscal profile changed; reload before saving')
    if not row:
        row = FixedAssetFiscalProfile(fixed_asset_id=asset.id)
        db.add(row)
    for key, value in data.model_dump(exclude={'expected_version'}).items():
        setattr(row, key, value)
    row.version = (before['version'] if before else 0) + 1
    row.updated_by_id = user.id
    db.flush()
    # JSON audit values must not contain date/Decimal objects.
    def audit_values(values):
        return {k: str(v) if isinstance(v, (date, Decimal)) else v for k, v in (values or {}).items()}
    record_audit(db, user, 'UPDATE', 'FIXED_ASSET_FISCAL_PROFILE', 'Updated fiscal depreciation profile',
                 entity_id=asset.id, before_data=audit_values(before), after_data=audit_values(profile_dict(row)))
    return row

def fiscal_year_row(asset, profile, year):
    book = sum((s.depreciation_amount for s in asset.schedules if s.status == 'POSTED' and s.period_year == year), ZERO)
    result = {'id': asset.id, 'asset_number': asset.asset_number, 'asset_name': asset.asset_name,
              'group_code': profile.group_code if profile else None, 'book_depreciation': book,
              'status': 'CONFIGURED' if profile else 'NOT_CONFIGURED', 'fiscal_cost': None,
              'opening': None, 'fiscal_depreciation': None, 'disposal_value': None, 'closing': None, 'difference': None}
    if not profile:
        return result
    # A migrated tax opening cannot substantiate an earlier tax year.
    if profile.opening_date and year <= profile.opening_date.year:
        result['status'] = 'BEFORE_FISCAL_OPENING'
        return result
    disposed = [m.movement_date for m in asset.movements if m.movement_type in ('DISPOSAL', 'WRITE_OFF')]
    end = min([date(year, 12, 31), *disposed])
    rows = fiscal_schedule(profile, end)
    prior = [r for r in rows if r['period'] < f'{year}-01']
    current = [r for r in rows if r['period'].startswith(str(year))]
    total = sum((r['depreciation'] for r in current), ZERO)
    opening = prior[-1]['closing'] if prior else money(profile.opening_book_value if profile.opening_date else profile.fiscal_cost)
    if asset.acquisition_date and asset.acquisition_date.year > year:
        opening = ZERO
    # Retired assets no longer carry a fiscal balance after their retirement year.
    retired = bool(disposed and min(disposed).year < year)
    disposal_value = opening-total if disposed and min(disposed).year == year else ZERO
    result.update(fiscal_cost=profile.fiscal_cost, disposal_value=disposal_value, opening=ZERO if retired else opening,
                  fiscal_depreciation=total, closing=ZERO if disposed and min(disposed).year <= year else opening-total,
                  difference=money(book-total))
    return result

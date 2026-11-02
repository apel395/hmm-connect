from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, model_validator

GROUPS = {
    'GROUP_1': ('Kelompok 1', 48, '25', '50'),
    'GROUP_2': ('Kelompok 2', 96, '12.5', '25'),
    'GROUP_3': ('Kelompok 3', 192, '6.25', '12.5'),
    'GROUP_4': ('Kelompok 4', 240, '5', '10'),
    'BUILDING_PERMANENT': ('Bangunan permanen', 240, '5', None),
    'BUILDING_NON_PERMANENT': ('Bangunan tidak permanen', 120, '10', None),
    'LAND': ('Tanah', None, None, None),
}

class FiscalProfileInput(BaseModel):
    group_code: Literal['GROUP_1', 'GROUP_2', 'GROUP_3', 'GROUP_4', 'BUILDING_PERMANENT', 'BUILDING_NON_PERMANENT', 'LAND']
    method: Literal['STRAIGHT_LINE', 'DECLINING_BALANCE', 'NONE']
    fiscal_cost: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    start_date: date | None = None
    # Actual building life >20 years requires the applicable tax election/evidence.
    useful_life_months: int | None = Field(default=None, ge=240, le=1200, multiple_of=12)
    reference: str = Field(default='', max_length=500)
    opening_date: date | None = None
    opening_book_value: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    expected_version: int = Field(default=0, ge=0)

    @model_validator(mode='after')
    def policy(self):
        if self.start_date and not 1900 <= self.start_date.year <= 9800:
            raise ValueError('Select a fiscal start year between 1900 and 9800')
        if self.group_code == 'LAND':
            if self.method != 'NONE' or self.start_date or self.useful_life_months or self.opening_date or self.opening_book_value is not None:
                raise ValueError('Land has no depreciation schedule or opening depreciation balance')
        else:
            if not self.start_date or self.method == 'NONE':
                raise ValueError('Fiscal depreciation requires a start date and method')
            if self.method == 'DECLINING_BALANCE' and GROUPS[self.group_code][3] is None:
                raise ValueError('Buildings use straight-line fiscal depreciation')
        if self.useful_life_months and (self.group_code != 'BUILDING_PERMANENT' or not self.reference.strip()):
            raise ValueError('An actual building life requires permanent-building classification and tax reference')
        if (self.opening_date is None) != (self.opening_book_value is None):
            raise ValueError('Supply both fiscal opening date and fiscal opening value')
        if self.opening_date:
            if (self.opening_date.month, self.opening_date.day) != (12, 31) or self.opening_date < self.start_date:
                raise ValueError('Fiscal opening must be a year end on or after depreciation starts')
            if self.opening_book_value > self.fiscal_cost:
                raise ValueError('Fiscal opening value cannot exceed fiscal cost')
        return self

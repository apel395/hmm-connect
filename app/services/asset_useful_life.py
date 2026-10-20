"""MMH capitalization policy. This minimum is company policy, not a tax rule."""
from fastapi import HTTPException

MINIMUM_USEFUL_LIFE_MONTHS = 48


def validate_useful_life(months, *, depreciable=True):
    if depreciable and (months is None or months < MINIMUM_USEFUL_LIFE_MONTHS):
        raise HTTPException(422, 'MMH asset policy requires a minimum useful life of 48 months (4 years)')


def useful_life_review(months, *, depreciable=True):
    return 'BELOW_MINIMUM_LIFE' if depreciable and (months is None or months < MINIMUM_USEFUL_LIFE_MONTHS) else None

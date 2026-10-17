"""User-defined fresh-food defaults. Explicit Item Master choices take priority."""
import re
DIRECT_USE_FAMILIES={'VEGETABLES','FRUIT','HERB','FISH','POULTRY','MEAT','SNACK'}


def food_treatment(subgroup, name=''):
    if (subgroup or '').strip().upper() not in DIRECT_USE_FAMILIES:
        return None
    if re.search(r'\b(FROZEN|BEKU|TENDERLOIN|SIRLOIN|IMPOR|IMPORTED)\b',name or '',re.I):
        return 'STOCK'
    return 'DIRECT_USE'

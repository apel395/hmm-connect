"""Selling groups follow the four BUY group numbers without subgroups."""
SELL_GROUPS = (("5", "FOOD"), ("6", "BEVERAGE"), ("7", "SERVICE"), ("8", "ROOM"))
LEGACY_SELL_GROUP_CODES = {"S-FOOD": "5", "S-BEV": "6", "S-SERVICE": "7", "S-ROOM": "8"}


def sell_group_code(code):
    code = str(code or "").strip().upper()
    return LEGACY_SELL_GROUP_CODES.get(code, code)

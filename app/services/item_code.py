"""Classification-based item numbering; previews never reserve a number."""
import re

from fastapi import HTTPException
from sqlalchemy import func, text

from app.models.product import Product


def code_prefix(group_code, subgroup_code):
    group = str(group_code or "").strip().upper()
    subgroup = str(subgroup_code or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9-]+", group):
        raise HTTPException(422, "Select a group with a valid code")
    if not subgroup:
        return group + "-", 6
    if not re.fullmatch(r"[A-Z0-9-]+", subgroup):
        raise HTTPException(422, "Select a subgroup with a valid code")
    prefix = subgroup if subgroup.startswith(group + "-") else group + "-" + subgroup
    return prefix, 5


def next_item_code(db, group_code, subgroup_code):
    prefix, width = code_prefix(group_code, subgroup_code)
    pattern = re.compile(re.escape(prefix) + r"(\d{" + str(width) + r"})$")
    codes = db.query(Product.code).filter(func.upper(Product.code).startswith(prefix)).all()
    last = max((int(match.group(1)) for (code,) in codes if (match := pattern.fullmatch(code.strip().upper()))), default=0)
    if last >= 10 ** width - 1 or len(prefix) + width > 20:
        raise HTTPException(409, "This item classification has exhausted its code range")
    return prefix + str(last + 1).zfill(width)


def lock_item_creation(db):
    # Serialize API item creation across Lambda instances until commit/rollback.
    # Explicit codes share the lock so they cannot take a generated code mid-save.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext('MMH_ITEM_CODE'))"))

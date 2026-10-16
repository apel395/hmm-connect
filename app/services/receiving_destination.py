"""Receipt-line routing, with immutable legacy fallback and explicit exceptions."""
from fastapi import HTTPException

WAREHOUSE = "WAREHOUSE"
DIRECT_USE = "DIRECT_USE"


def master_destination(product):
    treatment = str(getattr(product, "inventory_treatment", "") or "").upper()
    if treatment == "STOCK":
        return WAREHOUSE
    if treatment in {"DIRECT_USE", "NON_STOCK", "FIXED_ASSET"}:
        return DIRECT_USE
    raise HTTPException(409, f"Item {product.code} requires Item Master treatment review")


def line_destination(receipt, item):
    """Never reinterpret existing lines from a changed Item Master."""
    value = getattr(item, "destination_type", None)
    if value in {WAREHOUSE, DIRECT_USE}:
        return value
    header = str(getattr(receipt, "destination_type", "") or "").upper()
    if header in {WAREHOUSE, "INVENTORY"}:
        return WAREHOUSE
    if header == DIRECT_USE:
        return DIRECT_USE
    raise HTTPException(409, "Receiving line destination is missing")


def resolve_destination(product, requested=None, reason=None, legacy_header=None):
    default = master_destination(product)
    destination = requested or legacy_header or default
    if destination not in {WAREHOUSE, DIRECT_USE}:
        raise HTTPException(422, "Choose Warehouse or Direct Use for the receiving line")
    if destination == WAREHOUSE and product.inventory_treatment in {"NON_STOCK", "FIXED_ASSET"}:
        raise HTTPException(422, f"Item {product.code} cannot be received into warehouse stock")
    explanation = (reason or "").strip() or None
    if requested and destination != default and (not explanation or len(explanation) < 3):
        raise HTTPException(422, f"Enter a reason for the destination exception on item {product.code}")
    return destination, explanation if destination != default else None


def receipt_destination(receipt):
    destinations = {line_destination(receipt, item) for item in receipt.items}
    return next(iter(destinations)) if len(destinations) == 1 else "MIXED"


def warehouse_items(receipt):
    return [item for item in receipt.items if line_destination(receipt, item) == WAREHOUSE]

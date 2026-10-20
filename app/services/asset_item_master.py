"""Link asset intake to BUY items without changing source accounting or tax."""
from decimal import Decimal
import re

from fastapi import HTTPException
from sqlalchemy import func, update
from app.models.chart_of_account import ChartOfAccount
from app.models.item_group import ItemGroup
from app.models.item_subgroup import ItemSubgroup
from app.models.product import Product
from app.models.supplier_invoice import SupplierInvoiceLine
from app.services.item_code import lock_item_creation, next_item_code
from app.services.audit import record_audit


def ensure_asset_item(db, *, name, account_id, user, product_id=None, uom="SET", subgroup_code=None):
    from app.services.item_asset_policy import validate_asset_item
    validate_asset_item({"name":name,"inventory_treatment":"FIXED_ASSET"})
    lock_item_creation(db)
    account = db.get(ChartOfAccount, account_id)
    if not account or not account.is_active or not account.is_posting or not account.account_number.startswith(("100-600-", "100-900-")) or account.account_type != "ASSET" or account.normal_balance != "DEBIT":
        raise HTTPException(422, "Asset item requires an active posting fixed asset account")
    if product_id:
        item = db.get(Product, product_id)
        if not item or not item.is_active or item.item_type != "BUY" or item.inventory_treatment != "FIXED_ASSET" or item.asset_account_id != account_id:
            raise HTTPException(422, "Select an active BUY fixed asset item with the same asset account")
        return item
    name = re.sub(r"\s+", " ", str(name or "")).strip()
    uom = str(uom or "SET").strip()
    if not name or len(name) > 150 or not uom or len(uom) > 20:
        raise HTTPException(422, "Asset item name (up to 150 characters) and UOM (up to 20) are required")
    matches = db.query(Product).filter(Product.item_type == "BUY", func.lower(func.trim(Product.name)) == name.lower()).all()
    if matches:
        eligible = [p for p in matches if p.is_active and p.inventory_treatment == "FIXED_ASSET" and p.asset_account_id == account_id and p.uom.lower() == uom.lower()]
        if len(matches) != 1 or len(eligible) != 1:
            raise HTTPException(409, "Matching BUY item needs classification or UOM review; link the correct item explicitly")
        return eligible[0]
    # Use existing catalog only. Computers belong to KOMPUTER, other FF&E to FURNITURE.
    if not subgroup_code:
        if account.account_number.startswith("100-900-"): subgroup_code = "4-2"
        subgroup_code = subgroup_code or {"100-600-101": "4-1", "100-600-102": "4-3", "100-600-103": "4-5", "100-600-104": "4-2"}.get(account.account_number)
        if account.account_number == "100-600-104" and re.search(r"\b(computer|komputer|intel|laptop|desktop|pc)\b", name, re.I):
            subgroup_code = "4-4"
    group = db.query(ItemGroup).filter(ItemGroup.code == "4", ItemGroup.is_active.is_(True), ItemGroup.item_type.in_(["BUY", "ITEM"])).one_or_none()
    subgroup = db.query(ItemSubgroup).filter(ItemSubgroup.code == subgroup_code, ItemSubgroup.is_active.is_(True), ItemSubgroup.group_id == group.id).one_or_none() if group else None
    if not group or not subgroup:
        raise HTTPException(422, "Select an existing ASSET subgroup or a classified BUY item before registration")
    item = Product(code=next_item_code(db, group.code, subgroup.code), name=name,
        group_code=group.code, group_name=group.name, subgroup_code=subgroup.code, subgroup_name=subgroup.name,
        uom=uom, usage_uom=uom, conversion=Decimal("1"), item_type="BUY", inventory_treatment="FIXED_ASSET",
        asset_account_id=account_id, inventory_account_id=None, purchase_account_id=None, cogs_account_id=None,
        is_active=True, tax_category="REVIEW_REQUIRED", is_taxable=False, tax_rate=Decimal("0"))
    item._asset_intake_item = True  # The existing source asset is linked immediately below.
    db.add(item); db.flush()
    record_audit(db, user, "ASSET_ITEM_REGISTERED", "PRODUCT", f"Registered BUY asset item {item.code}", entity_id=item.id,
        after_data={"code": item.code, "asset_account_id": account_id, "inventory_treatment": "FIXED_ASSET"})
    return item


def link_asset_item(db, asset, *, user, subgroup_code=None):
    line = db.get(SupplierInvoiceLine, asset.source_invoice_line_id) if asset.source_invoice_line_id else None
    if line and asset.product_id and line.product_id and asset.product_id != line.product_id:
        raise HTTPException(409, "Asset and source invoice have different item links")
    product_id = asset.product_id or (line.product_id if line else None)
    if asset.goods_receipt_id and not product_id:
        from app.models.goods_receipt import GoodsReceiptItem
        ids = {row.product_id for row in db.query(GoodsReceiptItem).filter(GoodsReceiptItem.goods_receipt_id == asset.goods_receipt_id).all()}
        if len(ids) != 1:
            raise HTTPException(422, "Receiving contains multiple items; select the asset item explicitly")
        product_id = ids.pop()
    item = ensure_asset_item(db, name=(line.description if line else asset.asset_name), account_id=asset.asset_account_id,
        user=user, product_id=product_id, uom=(line.uom if line else "SET"), subgroup_code=subgroup_code)
    if asset.product_id == item.id and (not line or line.product_id == item.id):
        return item
    asset.product_id = item.id
    if line and not line.product_id:
        # Reference-only repair: ORM purchasing hooks must not recalculate a posted line's tax or totals.
        db.execute(update(SupplierInvoiceLine).where(SupplierInvoiceLine.id == line.id).values(product_id=item.id))
        db.expire(line, ["product_id", "product"])
    record_audit(db, user, "FIXED_ASSET_ITEM_LINKED", "FIXED_ASSET", f"Linked {asset.asset_number} to BUY item {item.code}", entity_id=asset.id,
        after_data={"product_id": item.id, "source_invoice_line_id": asset.source_invoice_line_id})
    return item

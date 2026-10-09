"""Repair explicit fixed asset IDs; dry run by default; no accounting writes."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.fixed_asset import FixedAsset
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.models.user import User
from app.services.asset_item_master import link_asset_item


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-id", type=int, required=True)
    parser.add_argument("--invoice-id", type=int, required=True)
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--subgroup", default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        try:
            asset = db.query(FixedAsset).filter(FixedAsset.id == args.asset_id).with_for_update().one()
            if asset.purchase_invoice_id != args.invoice_id or not asset.source_invoice_line_id:
                raise ValueError("Asset does not match the expected invoice source")
            invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == args.invoice_id).with_for_update().one()
            line = db.get(SupplierInvoiceLine, asset.source_invoice_line_id)
            user = db.get(User, args.user_id)
            if not user or invoice.status != "POSTED" or line.supplier_invoice_id != invoice.id:
                raise ValueError("Expected posted invoice, source line and audit user are required")
            before_invoice = dict(db.execute(select(SupplierInvoice.__table__).where(SupplierInvoice.id == invoice.id)).mappings().one())
            before_line = dict(db.execute(select(SupplierInvoiceLine.__table__).where(SupplierInvoiceLine.id == line.id)).mappings().one())
            cost = asset.acquisition_cost
            item = link_asset_item(db, asset, user=user, subgroup_code=args.subgroup)
            db.flush()
            after_invoice = dict(db.execute(select(SupplierInvoice.__table__).where(SupplierInvoice.id == invoice.id)).mappings().one())
            after_line = dict(db.execute(select(SupplierInvoiceLine.__table__).where(SupplierInvoiceLine.id == line.id)).mappings().one())
            before_line.pop("product_id"); after_line.pop("product_id")
            if before_invoice != after_invoice or before_line != after_line or asset.acquisition_cost != cost:
                raise ValueError("Source amounts or tax changed; repair refused")
            print(json.dumps({"mode": "APPLY" if args.apply else "DRY_RUN", "asset": asset.asset_number, "product_id": item.id,
                "code": item.code, "name": item.name, "group": item.group_name, "subgroup": item.subgroup_name, "treatment": item.inventory_treatment}, indent=2))
            if args.apply:
                db.commit(); print("COMMITTED Item Master and source links. Asset cost, invoice amounts, tax, stock and journals unchanged.")
            else:
                db.rollback(); print("DRY RUN: no changes committed.")
        except Exception:
            db.rollback()
            raise

if __name__ == "__main__": main()

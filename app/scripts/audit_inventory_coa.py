"""Audit missing inventory COA mappings that would block WAREHOUSE receiving POST.

Resolves the same dependency DirectCoaService.inventory_account() uses:
    LOCATION_{location_id}_INVENTORY_{FOOD|BEVERAGE|MATERIAL} setting,
    falling back to product.inventory_account_id.

Prints, for every active location, which LOCATION_*_INVENTORY_* settings are
missing, and lists every product that has no inventory_account_id. Also dumps
the 100-300-* inventory account rows (per-company) to help pick correct seeds.

Usage (on EC2):
    .venv/bin/python -m app.scripts.audit_inventory_coa
"""

from __future__ import annotations

from app.core.database import SessionLocal
from app.models.accounting_setting import AccountingSetting
from app.models.chart_of_account import ChartOfAccount
from app.models.location import Location
from app.models.product import Product

ROLES = ("INVENTORY_FOOD", "INVENTORY_BEVERAGE", "INVENTORY_MATERIAL")


def main() -> None:
    db = SessionLocal()
    try:
        print("=== Products MISSING inventory_account_id (block WAREHOUSE receiving) ===")
        prods = (
            db.query(Product)
            .filter(Product.inventory_account_id.is_(None))
            .order_by(Product.code)
            .all()
        )
        print(f"  count = {len(prods)}")
        for p in prods:
            print(f"  {p.code}  {p.name}  (group={p.group_name})")
        if len(prods) > 40:
            print(f"  ... {len(prods)} total; only first 40 shown")

        print("\n=== Locations and their LOCATION_*_INVENTORY_* settings ===")
        locations = db.query(Location).filter(Location.is_active.is_(True)).order_by(Location.id).all()
        for loc in locations:
            states = []
            for role in ROLES:
                key = f"LOCATION_{loc.id}_{role}"
                s = db.query(AccountingSetting).filter(AccountingSetting.setting_key == key).first()
                states.append(f"{role}={'OK' if s else 'MISSING'}")
            print(f"  loc#{loc.id} {loc.code} {loc.name}: {', '.join(states)}")

        print("\n=== Existing inventory account COA rows (100-300-*) per-company ===")
        for a in (
            db.query(ChartOfAccount)
            .filter(ChartOfAccount.account_number.like("100-300-%"))
            .order_by(ChartOfAccount.account_number)
            .all()
        ):
            print(f"  {a.account_number}  {a.account_name}")

        print("\n=== All existing LOCATION_* accounting settings ===")
        settings = (
            db.query(AccountingSetting)
            .filter(AccountingSetting.setting_key.like("LOCATION%"))
            .order_by(AccountingSetting.setting_key)
            .all()
        )
        for s in settings:
            acc = db.get(ChartOfAccount, s.account_id) if s.account_id else None
            label = f"{acc.account_number} {acc.account_name}" if acc else "?"
            print(f"  {s.setting_key} -> {s.account_id} {label}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

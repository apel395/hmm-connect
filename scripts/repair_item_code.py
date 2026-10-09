"""Repair one exact temporary import code; preview by default."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.database import SessionLocal
from app.models.product import Product
from app.models.user import User
from app.api.v1.products import numbering_classification, update_product
from app.schemas.product import ProductUpdate
from app.services.item_code import next_item_code


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--old-code", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--user-id", required=True, type=int)
    p.add_argument("--apply", action="store_true")
    args=p.parse_args()
    with SessionLocal() as db:
        item=db.query(Product).filter(Product.code==args.old_code, Product.name==args.name).one()
        if not item.code.startswith("RBI-"): raise ValueError("Expected a temporary RBI import code")
        numbering_classification(db,item.item_type,item.group_code,item.subgroup_code)
        old=item.code
        if args.apply:
            actor=db.get(User,args.user_id)
            if not actor: raise ValueError("Audit user not found")
            item=update_product(item.id,ProductUpdate(regenerate_code=True,expected_code=old),db,actor)
            code=item.code
        else: code=next_item_code(db,item.group_code,item.subgroup_code)
        print(json.dumps({"mode":"APPLY" if args.apply else "DRY_RUN","id":item.id,"name":item.name,"old_code":old,"new_code":code},indent=2))
        print("COMMITTED code and audit only; document links unchanged." if args.apply else "DRY RUN: no writes. Add --apply to repair.")

if __name__=="__main__": main()

"""Read-only remaining Sell Item and utensil classification report for EC2."""
import json
import re
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def inspect_items(db):
    from app.models.product import Product
    from app.models.fixed_asset import FixedAsset
    from app.models.inventory import Inventory
    from app.models.chart_of_account import ChartOfAccount
    from app.services.item_asset_policy import is_utensil
    from app.services.sell_item_groups import SELL_GROUPS, sell_group_code
    from app.services.department_outlets import labels
    groups=dict(SELL_GROUPS);sell=[];utensils=[]
    products=db.query(Product).order_by(Product.id).all()
    assets={}
    for asset in db.query(FixedAsset).filter(FixedAsset.product_id.isnot(None)):
        assets.setdefault(asset.product_id,[]).append({'id':asset.id,'number':asset.asset_number,'status':asset.status,'cost':str(asset.acquisition_cost) if asset.acquisition_cost is not None else None})
    accounts={a.id:a.account_number for a in db.query(ChartOfAccount)}
    for item in products:
        if item.item_type=='SELL':
            group=sell_group_code(item.group_code);issues=[]
            if group not in groups or groups.get(group)!=str(item.group_name or '').strip().upper():issues.append('GROUP_MISMATCH')
            if item.group_code!=group or not re.fullmatch(re.escape(group)+r'-\d{6}',item.code):issues.append('CODE_REVIEW')
            if item.subgroup_code or item.subgroup_name:issues.append('SUBGROUP_NOT_EMPTY')
            if item.inventory_treatment!='NON_STOCK':issues.append('SELL_TREATMENT')
            if item.catalog_type=='CATERING' and group=='8':issues.append('ROOM_IN_CATERING')
            if item.inventory_account_id or item.asset_account_id:issues.append('SELL_INVENTORY_OR_ASSET_MAPPING')
            if issues:sell.append({'id':item.id,'code':item.code,'name':item.name,'catalog':item.catalog_type,'issues':issues})
        elif is_utensil(item) and (item.inventory_treatment=='FIXED_ASSET' or item.group_name.upper()=='ASSET' or item.id in assets):
            stock=[{'warehouse_id':row.warehouse_id,'quantity':str(row.quantity),'average_cost':str(row.average_cost)} for row in db.query(Inventory).filter_by(product_id=item.id) if row.quantity]
            utensils.append({'id':item.id,'code':item.code,'name':item.name,'catalog':item.catalog_type,'treatment':item.inventory_treatment,
                'asset_account':accounts.get(item.asset_account_id),'assets':assets.get(item.id,[]),'stock':stock,
                'required':'MATERIAL; choose STOCK or DIRECT_USE from actual usage. Review valued assets and posted accounting before changing.'})
    return {'mode':'READ_ONLY','sell_items':sum(p.item_type=='SELL' for p in products),'sell_issues':sell,'utensil_reviews':utensils,'hotel_outlets':labels(db)}


def main():
    from sqlalchemy import text
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        if db.bind.dialect.name=='postgresql':db.execute(text('SET TRANSACTION READ ONLY'))
        print(json.dumps(inspect_items(db),indent=2,default=str))
        db.rollback()
    print('READ ONLY: no items, assets, stock, tax, journals or opening balances changed.')

if __name__=='__main__':main()

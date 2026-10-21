from test_item_auto_code import db, ADMIN
from app.api.v1.products import create_product, update_product
from app.schemas.product import ProductCreate, ProductUpdate
from app.models.inventory import Inventory
from app.models.journal_entry import JournalEntry
from app.models.fixed_asset import FixedAsset


def test_sell_item_creation_and_edit_need_no_inventory_or_expense_mapping(db):
    row=create_product(ProductCreate(name='Catering meals no stock offset',item_type='SELL',group_code='5',group_name='FOOD',subgroup_code='',subgroup_name='',uom='Meals',usage_uom='Meals',conversion=1,inventory_treatment='NON_STOCK',selling_price=50000,inventory_account_id=999,purchase_account_id=999,cogs_account_id=999,asset_account_id=999,pbjt_rate=10),db,ADMIN)
    assert row.code=='5-000001' and row.pbjt_rate==10
    for field in ('inventory_account_id','purchase_account_id','cogs_account_id','asset_account_id'):
        assert getattr(row,field) is None
    update_product(row.id,ProductUpdate(selling_price=55000,purchase_account_id=998),db,ADMIN)
    assert row.selling_price==55000 and row.purchase_account_id is None
    assert db.query(Inventory).count()==db.query(JournalEntry).count()==db.query(FixedAsset).count()==0

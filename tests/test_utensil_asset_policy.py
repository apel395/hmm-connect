from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.services.item_asset_policy import is_utensil,validate_asset_item
from app.api.v1.products import _validate_treatment
from app.services.asset_item_master import ensure_asset_item
from app.models.fixed_asset import FixedAsset
from test_asset_master_registration import db,item


def test_utensils_reject_capitalization_while_stock_and_direct_use_are_valid():
    for treatment in ('STOCK','DIRECT_USE'):
        validate_asset_item({'name':'Hotel utensils','subgroup_name':'KITCHEN','inventory_treatment':treatment})
    with pytest.raises(HTTPException):
        _validate_treatment({'name':'Hotel cutlery set','group_name':'ASSET','subgroup_name':'FURNITURE','item_type':'BUY','inventory_treatment':'FIXED_ASSET','asset_account_id':1})
    assert is_utensil(SimpleNamespace(name='Dinner set',subgroup_name='CHINAWARE, GLASSWARE & CUTLERIES'))
    assert is_utensil(SimpleNamespace(name='Sendok makan stainless',subgroup_name='FURNITURE'))
    assert not is_utensil(SimpleNamespace(name='Fork lift',subgroup_name='MACHINERY'))
    assert not is_utensil(SimpleNamespace(name='Hotel towel',subgroup_name='LINEN'))


def test_manual_intake_cannot_bypass_policy_and_existing_linen_is_preserved(db):
    with pytest.raises(HTTPException):ensure_asset_item(db,name='Hotel utensils',account_id=1,user=None)
    assert db.query(FixedAsset).count()==0
    product=item(db)
    assert db.query(FixedAsset).one().product_id==product.id

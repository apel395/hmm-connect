import copy
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from classify_resiping_items import MANIFEST, verify_source, desired_profile, validate_identity, classify_batch
from seed_resiping_items import seed_plan


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.manifest=json.loads(MANIFEST.read_text())
        self.source={'source_sha256':self.manifest['source_sha256'],
                     'items':[{'name':r['name'],'units':r['units']} for r in self.manifest['items']]}

    def test_complete_exact_manifest_no_prefix_or_generic_fallback(self):
        rules=verify_source(self.source,self.manifest)
        self.assertEqual(len(rules),349)
        self.assertEqual(self.manifest['expected_batch_count'],291)
        self.assertEqual(rules['RISOLES']['treatment'],'DIRECT_USE')
        self.assertEqual(rules['BATAGOR']['treatment'],'DIRECT_USE')
        self.assertEqual(rules['WORTEL/CARROT']['subgroup'],'VEGETABLES')
        self.assertEqual(rules['DENALI SYRUP STRAWBERRY']['group'],'BEVERAGE')
        self.assertEqual(rules['DENALI SYRUP STRAWBERRY']['subgroup'],'SYRUP')
        self.assertEqual(rules['SIRUP MARJAN MELON']['subgroup'],'SYRUP')
        self.assertEqual(rules['DENALI POWDER COCOA SIGNATURE']['subgroup'],'BEVERAGE INGREDIENTS')
        self.assertEqual(rules['BLUEBERRY FROZEN']['subgroup'],'FRUIT')
        self.assertEqual(rules['PLASTIK SAMPAH']['group'],'MATERIAL')
        self.assertEqual(rules['CHICKEN SAUSAGE']['treatment'],'STOCK')

    def test_changed_workbook_or_missing_names_rejected(self):
        for change in ('hash','name','unit'):
            src=copy.deepcopy(self.source)
            if change=='hash': src['source_sha256']='new'
            elif change=='name': src['items'].pop()
            else: src['items'][0]['units']=['BAD']
            with self.assertRaises(ValueError): verify_source(src,self.manifest)

    def test_coa_mapping_and_no_tax_in_desired_changes(self):
        accounts=[SimpleNamespace(id=i,account_number=n,is_active=True,is_posting=True,account_type=t,normal_balance='DEBIT')
                  for i,n,t in [(1,'100-300-100','ASSET'),(2,'500-100-100','EXPENSE')]]
        group=SimpleNamespace(code='1',name='FOOD');sub=SimpleNamespace(code='1-9',name='PREPARED FOOD')
        rule={'group':'FOOD','treatment':'DIRECT_USE'}
        profile=desired_profile(rule,group,sub,accounts)
        self.assertIsNone(profile['inventory_account_id'])
        self.assertEqual(profile['purchase_account_id'],2)
        self.assertFalse(any('tax' in k for k in profile))
        rule['treatment']='STOCK'
        self.assertEqual(desired_profile(rule,group,sub,accounts)['inventory_account_id'],1)
        accounts[0].is_posting=False
        with self.assertRaises(ValueError): desired_profile(rule,group,sub,accounts)


def fixture(db, monkeypatch):
    from app.models import Base
    from app.models.product import Product
    from app.models.audit_log import AuditLog
    from app.models.item_group import ItemGroup
    from app.models.chart_of_account import ChartOfAccount
    import app.services.audit as audit
    manifest=json.loads(MANIFEST.read_text())
    names=['RISOLES','WORTEL/CARROT','DENALI SYRUP STRAWBERRY','PLASTIK SAMPAH']
    manifest['items']=[r for r in manifest['items'] if r['name'] in names]
    manifest['expected_batch_count']=len(names)
    source={'source_sha256':manifest['source_sha256'],'items':[{'name':r['name'],'units':r['units']} for r in manifest['items']]}
    for code,name in [('1','FOOD'),('2','BEVERAGE'),('3','MATERIAL')]:
        db.add(ItemGroup(code=code,name=name,item_type='ITEM',is_active=True))
    for code,kind in [('100-300-100','ASSET'),('100-300-500','ASSET'),('100-300-700','ASSET'),('500-100-100','EXPENSE'),('500-100-102','EXPENSE')]:
        db.add(ChartOfAccount(account_number=code,account_name=code,account_type=kind,normal_balance='DEBIT',is_active=True,is_posting=True))
    ids=[]
    for r in manifest['items']:
        report={'items':[{'name':r['name'],'units':r['units'],'unit_review_required':False}]}
        seed_plan(report,[])
        fields=report['items'][0]['new_product'].copy();fields.pop('tax_reason')
        p=Product(**fields);db.add(p);db.flush();ids.append(p.id)
        db.add(AuditLog(action='RESIPING_BUY_ITEM_CREATED',entity_type='PRODUCT',entity_id=p.id,summary='seed',details={'source_sha256':manifest['source_sha256']},after_data=fields))
    db.add(Product(code='SELL1',name='RISOLES',item_type='SELL',group_code='SELL',group_name='SELL',subgroup_code='SELL1',subgroup_name='SELL',uom='PCS',usage_uom='PCS',conversion=1,inventory_treatment='REVIEW_REQUIRED',tax_category='REVIEW_REQUIRED'))
    db.commit()
    def record(session,user,action,entity_type,summary,**kwargs):
        session.add(AuditLog(action=action,entity_type=entity_type,summary=summary,**kwargs))
    monkeypatch.setattr(audit,'record_audit',record)
    return source,manifest,ids


def test_master_only_dry_run_commit_repeat_and_rollback(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.models import Base
    from app.models.product import Product
    from app.models.audit_log import AuditLog
    from app.models.item_subgroup import ItemSubgroup
    from app.models.inventory import Inventory
    from app.models.stock_movement import StockMovement
    from app.models.journal_entry import JournalEntry
    from app.models.opening_balance import OpeningBalance
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine) as db:
        source,manifest,ids=fixture(db,monkeypatch)
        dry=classify_batch(db,source,manifest)
        assert dry['counts']=={'CLASSIFY':4}
        assert db.query(ItemSubgroup).count()==0
        assert all(db.get(Product,i).group_code=='BUYPEND' for i in ids)
        classify_batch(db,source,manifest,apply=True)
        db.rollback()
        assert db.query(ItemSubgroup).count()==0
        assert all(db.get(Product,i).group_code=='BUYPEND' for i in ids)
        classify_batch(db,source,manifest,apply=True);db.commit()
        assert db.query(AuditLog).filter_by(action='RESIPING_BUY_ITEM_CLASSIFIED').count()==4
        assert db.query(Product).filter_by(item_type='SELL').one().group_code=='SELL'
        assert all(db.get(Product,i).tax_category=='REVIEW_REQUIRED' and not db.get(Product,i).is_taxable for i in ids)
        repeated=classify_batch(db,source,manifest,apply=True);db.commit()
        assert repeated['counts']=={'ALREADY_CLASSIFIED':4}
        assert db.query(AuditLog).filter_by(action='RESIPING_BUY_ITEM_CLASSIFIED').count()==4
        for model in (Inventory,StockMovement,JournalEntry,OpeningBalance): assert db.query(model).count()==0
        db.get(Product,ids[0]).subgroup_name='MANUAL CHANGE';db.flush()
        import pytest
        with pytest.raises(ValueError,match='profile changed'): classify_batch(db,source,manifest,apply=True)


def test_batch_count_identity_and_existing_document_guard(monkeypatch):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session
    from app.models import Base
    from app.models.product import Product
    import pytest
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine) as db:
        source,manifest,ids=fixture(db,monkeypatch)
        bad=copy.deepcopy(manifest);bad['expected_batch_count']=291
        with pytest.raises(ValueError,match='291'): classify_batch(db,source,bad,apply=True)
        db.get(Product,ids[0]).uom='BOX'
        with pytest.raises(ValueError,match='identity or unit'): classify_batch(db,source,manifest,apply=True)
        db.rollback()
        db.execute(text('INSERT INTO inventory(product_id,warehouse_id,quantity,average_cost) VALUES(:pid,1,1,1)'),{'pid':ids[0]})
        with pytest.raises(ValueError,match='already used in inventory'): classify_batch(db,source,manifest,apply=True)
        assert all(db.get(Product,i).group_code=='BUYPEND' for i in ids)

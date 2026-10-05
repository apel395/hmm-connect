import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('correction', ROOT / 'scripts/correct_item_classification.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
RULES = json.loads((ROOT / 'scripts/item_classification_rules_20261005.json').read_text())


class ClassificationCorrectionTests(unittest.TestCase):
    def fixture(self, treatment='DIRECT_USE'):
        rule = dict(next(r for r in RULES if r['id'] == 6314))
        rule['treatment'] = treatment
        rule['account'] = '500-100-100' if treatment == 'DIRECT_USE' else '100-300-100'
        product = {**rule['expected'], 'id':6314, 'code':rule['code'], 'name':rule['name'],
                   'group_code':'1', 'subgroup_code':'1-8', 'cogs_account_id':37,
                   'is_active':True, 'item_type':'BUY', 'is_market_item':False,
                   'is_taxable':False, 'tax_rate':'0.0000', 'tax_category':'NON_TAXABLE'}
        group={'id':1,'code':'1','name':'FOOD'}
        sub={'id':999,'code':'1-99','name':'PREPARED FOOD'}
        account={'id':37 if treatment=='DIRECT_USE' else 167,'account_number':rule['account'],
                 'account_type':'EXPENSE' if treatment=='DIRECT_USE' else 'ASSET',
                 'normal_balance':'DEBIT','is_active':True,'is_posting':True}
        history={'has_stock':False,'has_movements':False,'has_posted_receipt':False}
        return product,rule,group,sub,account,history

    def test_confirmed_direct_use_clears_inventory_mapping_without_tax_changes(self):
        changes,blocked,_=module.build_changes(*self.fixture())
        self.assertIsNone(blocked)
        self.assertEqual(changes['inventory_treatment'],'DIRECT_USE')
        self.assertIsNone(changes['inventory_account_id'])
        self.assertIsNone(changes['cogs_account_id'])
        self.assertFalse({'tax_category','is_taxable','tax_rate'}.intersection(changes))

    def test_each_stock_dependency_defers_accounting_change(self):
        for key in ('has_stock','has_movements','has_posted_receipt'):
            args=self.fixture();args[-1][key]=True
            changes,blocked,proposed=module.build_changes(*args)
            self.assertEqual(changes,{})
            self.assertTrue(blocked)
            self.assertEqual(proposed['inventory_treatment'],'DIRECT_USE')

    def test_family_only_change_is_allowed_with_stock_history(self):
        args=self.fixture('STOCK');args[-1]['has_movements']=True
        changes,blocked,_=module.build_changes(*args)
        self.assertIsNone(blocked)
        self.assertEqual(changes['subgroup_name'],'PREPARED FOOD')

    def test_identity_and_stale_mapping_are_rejected(self):
        for field,value in [('code','different'),('inventory_account_id',999)]:
            args=self.fixture();args[0][field]=value
            with self.assertRaises(ValueError):module.build_changes(*args)

    def test_invalid_coa_is_rejected(self):
        for field,value in [('is_active',False),('is_posting',False),('account_type','LIABILITY'),('normal_balance','CREDIT')]:
            args=self.fixture();args[-2][field]=value
            with self.assertRaises(ValueError):module.build_changes(*args)

    def test_correction_is_idempotent(self):
        args=self.fixture();changes,_,_=module.build_changes(*args)
        args[0].update(changes)
        self.assertEqual(module.build_changes(*args)[0],{})

    def test_rules_preserve_unique_source_identity(self):
        self.assertEqual(len(RULES),93)
        self.assertEqual(len({r['id'] for r in RULES}),93)
        self.assertEqual(len({r['code'] for r in RULES}),93)

    def test_missing_food_catalog_uses_existing_item_codes(self):
        snapshots=[{'group_code':'1','group_name':'FOOD','subgroup_code':'1-5','subgroup_name':'VEGETABLES'}]
        group=module.resolve_group([],snapshots,'FOOD')
        self.assertEqual(group['code'],'1')
        self.assertTrue(group['_new'])
        subgroup=module.resolve_subgroup([],snapshots,group,['VEGETABLES'])
        self.assertEqual(subgroup['code'],'1-5')
        rule=next(r for r in RULES if r['id']==4700)
        product={**rule['expected'],'id':4700,'code':rule['code'],'name':rule['name'],
                 'group_code':'4','subgroup_code':'4-2','cogs_account_id':40,
                 'is_active':True,'item_type':'BUY','is_market_item':False}
        account={'id':167,'account_number':'100-300-100','is_active':True,'is_posting':True,
                 'account_type':'ASSET','normal_balance':'DEBIT'}
        history={'has_stock':False,'has_movements':False,'has_posted_receipt':False}
        changes,blocked,_=module.build_changes(product,rule,group,subgroup,account,history)
        self.assertIsNone(blocked)
        self.assertEqual(changes['group_name'],'FOOD')
        self.assertEqual(changes['subgroup_name'],'VEGETABLES')
        self.assertEqual(changes['inventory_account_id'],167)

    def test_duplicate_group_labels_resolve_by_verified_code(self):
        groups=[{'id':1,'code':'1','name':'FOOD','item_type':'BUY','is_active':True},
                {'id':2,'code':'99','name':'FOOD','item_type':'BUY','is_active':True}]
        self.assertEqual(module.resolve_group(groups,[{'group_code':'1','group_name':'FOOD'}],'FOOD')['id'],1)

    def test_group_conflicts_and_inactive_entries_are_rejected(self):
        snapshots=[{'group_code':'1','group_name':'FOOD'}]
        for field,value in [('is_active',False),('name','ASSET'),('item_type','SELL')]:
            group={'id':1,'code':'1','name':'FOOD','item_type':'BUY','is_active':True,field:value}
            with self.assertRaises(ValueError):module.resolve_group([group],snapshots,'FOOD')
        with self.assertRaises(ValueError):
            module.resolve_group([],snapshots+[{'group_code':'9','group_name':'FOOD'}],'FOOD')

    def test_subgroup_code_conflicts_are_rejected(self):
        snapshots=[{'group_code':'1','group_name':'FOOD','subgroup_code':'1-5','subgroup_name':'VEGETABLES'}]
        group={'id':1,'code':'1'}
        for field,value in [('is_active',False),('name','FURNITURE'),('group_id',2)]:
            subgroup={'id':5,'code':'1-5','name':'VEGETABLES','group_id':1,'is_active':True,field:value}
            with self.assertRaises(ValueError):module.resolve_subgroup([subgroup],snapshots,group,['VEGETABLES'])

    def test_new_subgroups_do_not_reuse_legacy_codes(self):
        subgroup=module.resolve_subgroup([], [{'group_code':'1','subgroup_code':'1-1','subgroup_name':'MEAT'}],
                                        {'id':1,'code':'1'}, ['PREPARED FOOD'])
        self.assertEqual(subgroup['code'],'1-2')


if __name__=='__main__':unittest.main()

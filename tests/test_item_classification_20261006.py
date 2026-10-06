import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('classification_v2', ROOT / 'scripts/correct_item_classification.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
RULES = json.loads((ROOT / 'scripts/item_classification_rules_20261006.json').read_text())


class CurrentClassificationTests(unittest.TestCase):
    def test_complete_237_unique_buy_source_identities(self):
        self.assertEqual(len(RULES), 237)
        source = {r['id']: {'ID':r['id'], 'Code':r['code'], 'Item':r['name']} for r in RULES}
        module.validate_rules(RULES, source)
        with self.assertRaises(ValueError): module.validate_rules(RULES + [RULES[0]], source)
        source[RULES[0]['id']]['Item'] = 'different item'
        with self.assertRaises(ValueError): module.validate_rules(RULES, source)

    def test_syrup_is_not_fresh_fruit_or_prepared_drink(self):
        for pid in (6147, 6063):
            rule = next(r for r in RULES if r['id'] == pid)
            self.assertEqual((rule['group'], rule['subgroups'], rule['treatment'], rule['account']),
                             ('BEVERAGE', ['SYRUP'], 'STOCK', '100-300-500'))

    def fixture(self, pid=6332):
        rule = next(r for r in RULES if r['id'] == pid)
        product = {**rule['expected'], 'id':pid, 'code':rule['code'], 'name':rule['name'],
                   'group_code':'2','subgroup_code':'2-1', 'item_type':'BUY','is_active':True,
                   'inventory_treatment':'STOCK','inventory_account_id':177,'purchase_account_id':39,
                   'asset_account_id':None,'cogs_account_id':39,'tax_rate':'11.0000','is_taxable':True}
        group = {'code':'2','name':'BEVERAGE'}
        subgroup = {'code':'2-1','name':'MINERAL WATER'}
        history = {'has_stock':True,'has_movements':True,'has_posted_receipt':True}
        return product, rule, group, subgroup, None, history

    def test_direct_use_receipt_does_not_reclassify_water_default(self):
        args = self.fixture()
        changes, blocked, _ = module.build_changes(*args)
        self.assertIsNone(blocked)
        self.assertEqual(changes, {})
        self.assertEqual(args[0]['inventory_treatment'], 'STOCK')

    def test_classification_only_preserves_accounting_tax_and_existing_direct_use_default(self):
        args = list(self.fixture(6339))
        args[0].update(group_code='1', subgroup_code='1-8', inventory_treatment='DIRECT_USE', inventory_account_id=None)
        args[2] = {'code':'1', 'name':'FOOD'}
        args[3] = {'code':'1-8', 'name':'GROCERIES'}
        changes, blocked, _ = module.build_changes(*args)
        self.assertIsNone(blocked)
        self.assertEqual(changes, {'subgroup_name':'GROCERIES'})
        args[0].update(changes)
        self.assertEqual(module.build_changes(*args)[0], {})

    def test_uncertain_equipment_stops_and_sell_is_never_changed(self):
        with self.assertRaises(ValueError): module.build_changes(*self.fixture(6065))
        args = self.fixture(); args[0]['item_type'] = 'SELL'
        with self.assertRaises(ValueError): module.build_changes(*args)

    def test_posted_syrup_coa_correction_is_deferred(self):
        rule = next(r for r in RULES if r['id'] == 6147)
        product = {**rule['expected'],'id':6147,'code':rule['code'],'name':rule['name'],
                   'group_code':'1','subgroup_code':'1-6','item_type':'BUY','is_active':True,
                   'cogs_account_id':37,'is_market_item':True}
        account = {'id':177,'account_number':'100-300-500','account_type':'ASSET',
                   'normal_balance':'DEBIT','is_active':True,'is_posting':True}
        changes, blocked, proposed = module.build_changes(product,rule,{'code':'2','name':'BEVERAGE'},
            {'code':'2-9','name':'SYRUP'},account,{'has_stock':True,'has_movements':True,'has_posted_receipt':True})
        self.assertEqual(changes,{})
        self.assertTrue(blocked)
        self.assertEqual(proposed['inventory_account_id'],177)
        self.assertNotIn('tax_rate',proposed)


if __name__ == '__main__': unittest.main()

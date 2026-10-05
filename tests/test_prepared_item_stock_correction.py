import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('stock_correction', ROOT / 'scripts/correct_prepared_item_stock.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
MANIFEST = json.loads((ROOT / 'scripts/item_stock_correction_20261005.json').read_text())
RULES = {r['id']:r for r in json.loads((ROOT / 'scripts/item_classification_rules_20261005.json').read_text())}


class PreparedItemStockCorrectionTests(unittest.TestCase):
    def inputs(self):
        m = copy.deepcopy(MANIFEST)
        return [MANIFEST,m['pending_items'],m['inventory'],m['movements'],m['receipt_items'],RULES]

    def test_traced_stock_becomes_balanced_expense_correction(self):
        plan = module.plan_stock(*self.inputs())
        self.assertEqual(len(plan),22)
        for r in plan:
            r['expense_account_id'] = 37 if r['expense_code']=='500-100-100' else 39
        sig = module.correction_signature(plan)
        self.assertEqual(sum(k[1]*v for k,v in sig.items()),Decimal('2665000.00'))
        self.assertEqual(sum(k[2]*v for k,v in sig.items()),Decimal('2665000.00'))
        self.assertEqual(sig[(37,Decimal('2397000.00'),Decimal('0'))],1)
        self.assertEqual(sig[(39,Decimal('268000.00'),Decimal('0'))],1)
        self.assertEqual(sig[(167,Decimal('0'),Decimal('2635000.00'))],1)
        self.assertEqual(sig[(198,Decimal('0'),Decimal('30000.00'))],1)
        self.assertFalse(any(k[0]==304 for k in sig))

    def test_changed_inventory_quantity_or_cost_refuses_entire_batch(self):
        for field in ('quantity','average_cost'):
            args=self.inputs();args[2][0][field]='1'
            with self.assertRaises(ValueError):module.plan_stock(*args)

    def test_out_movement_or_new_stock_history_refuses_batch(self):
        args=self.inputs();args[3].append({**args[3][0],'id':999999,'movement_type':'OUT'})
        with self.assertRaises(ValueError):module.plan_stock(*args)
        args=self.inputs();args[3][0]['movement_type']='OUT'
        with self.assertRaises(ValueError):module.plan_stock(*args)

    def test_changed_tax_snapshot_refuses_batch(self):
        args=self.inputs();args[4][0]['tax_amount']='100'
        with self.assertRaises(ValueError):module.plan_stock(*args)

    def test_changed_identity_or_classification_refuses_batch(self):
        for field,value in [('code','other'),('inventory_treatment','DIRECT_USE'),('inventory_account_id',999)]:
            args=self.inputs();args[1][0][field]=value
            with self.assertRaises(ValueError):module.plan_stock(*args)

    def test_signature_preserves_duplicate_account_lines(self):
        rows=[{'account_id':1,'debit':'100','credit':'0'}]*2
        self.assertNotEqual(module.signature(rows),module.signature(rows[:1]))

    def test_decimal_representation_changes_are_equivalent(self):
        args=self.inputs();args[2][0]['quantity']=Decimal(args[2][0]['quantity'])
        self.assertEqual(len(module.plan_stock(*args)),22)


if __name__ == '__main__':
    unittest.main()

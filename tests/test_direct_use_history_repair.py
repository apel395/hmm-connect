import copy
from datetime import datetime, timezone
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('repair', ROOT / 'scripts/repair_direct_use_receiving_history.py')
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)
MANIFEST = json.loads((ROOT / 'scripts/item_stock_correction_20261005.json').read_text())
RULES = {r['id']:r for r in json.loads((ROOT / 'scripts/item_classification_rules_20261005.json').read_text())}


class DirectUseHistoryRepairTests(unittest.TestCase):
    def plan(self):
        plan = repair.plan_stock(MANIFEST, MANIFEST['pending_items'], MANIFEST['inventory'],
                                 MANIFEST['movements'], MANIFEST['receipt_items'], RULES)
        for item in plan:
            item['expense_account_id'] = 37 if item['expense_code']=='500-100-100' else 39
        return plan

    def test_original_receiving_has_expenses_not_false_inventory(self):
        wanted = repair.receiving_signature(MANIFEST['journal_lines'],self.plan())
        self.assertEqual(wanted,repair.Counter({
            (167,Decimal('1280000'),Decimal('0')):1,
            (177,Decimal('80000'),Decimal('0')):1,
            (37,Decimal('2397000'),Decimal('0')):1,
            (39,Decimal('268000'),Decimal('0')):1,
            (304,Decimal('0'),Decimal('4025000')):1,
        }))
        self.assertFalse(any(a==198 for a,_,_ in wanted))

    def test_repair_preserves_current_account_balances(self):
        plan=self.plan()
        temporary=[{'account_id':a,'debit':d,'credit':c} for a,d,c in repair.correction_signature(plan).elements()]
        wanted=[{'account_id':a,'debit':d,'credit':c} for a,d,c in repair.receiving_signature(MANIFEST['journal_lines'],plan).elements()]
        self.assertEqual(repair.balances(MANIFEST['general_ledger']+temporary),repair.balances(wanted))

    def test_insufficient_original_inventory_debit_is_rejected(self):
        source=copy.deepcopy(MANIFEST['journal_lines']);source[0]['debit']='1'
        with self.assertRaises(ValueError):repair.receiving_signature(source,self.plan())

    def test_changed_suspense_balance_cannot_be_hidden_by_repair(self):
        source=copy.deepcopy(MANIFEST['journal_lines']);source[-1]['credit']='4025001'
        with self.assertRaises(ValueError):repair.receiving_signature(source,self.plan())

    def outs(self):
        day=datetime(2026,1,1,tzinfo=timezone.utc)
        outs=[{'product_id':p['product_id'],'movement_type':'OUT','reference_type':repair.MARKER,
               'reference_id':661,'journal_entry_id':1400,'goods_receipt_id':661,
               'goods_receipt_item_id':p['receipt_item_id'],'warehouse_id':11,
               'inventory_account_id':p['inventory_account_id'],'offset_account_id':p['expense_account_id'],
               'quantity':p['quantity'],'unit_cost':p['unit_cost'],'created_at':day} for p in self.plan()]
        return outs,day

    def test_only_verified_synthetic_outs_are_removable(self):
        outs,day=self.outs();repair.validate_outs(outs,self.plan(),1400,day)
        for field,value in [('quantity',999),('warehouse_id',12),('reference_type','STORE_REQUEST'),('journal_entry_id',99)]:
            changed=copy.deepcopy(outs);changed[0][field]=value
            with self.assertRaises(ValueError):repair.validate_outs(changed,self.plan(),1400,day)

    def test_missing_or_duplicate_outs_are_rejected(self):
        outs,day=self.outs()
        for altered in (outs[:-1],outs[:-1]+[outs[0]]):
            with self.assertRaises(ValueError):repair.validate_outs(altered,self.plan(),1400,day)


if __name__ == '__main__':unittest.main()

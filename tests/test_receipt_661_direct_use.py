import copy
from datetime import datetime, timezone
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('complete_receipt',ROOT/'scripts/set_receipt_661_direct_use.py')
repair=importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)
ITEMS=[r for r in json.loads((ROOT/'scripts/receipt_661_direct_use_manifest.json').read_text())
       if r['product_id'] in repair.REMAINING]


class CompleteReceivingTests(unittest.TestCase):
    def stock(self):
        movements=[{'product_id':r['product_id'],'movement_type':'IN','reference_type':'GOODS_RECEIPT',
            'reference_id':661,'goods_receipt_id':661,'goods_receipt_item_id':r['receipt_item_id'],
            'journal_entry_id':1332,'warehouse_id':11,
            'inventory_account_id':177 if r['product_id']==6332 else 167,
            'created_at':datetime(2026,1,1,tzinfo=timezone.utc),
            'quantity':r['quantity'],'unit_cost':r['unit_cost']} for r in ITEMS]
        inventory=[{'product_id':r['product_id'],'warehouse_id':11,
                    'quantity':r['quantity'],'average_cost':r['unit_cost']} for r in ITEMS]
        return movements,inventory

    def test_six_remaining_in_entries_match_original_receipt(self):
        movements,stock=self.stock()
        repair.validate_remaining_stock(ITEMS,movements,stock)
        self.assertEqual(sum(Decimal(r['quantity'])*Decimal(r['unit_cost']) for r in ITEMS),Decimal('1360000'))

    def test_historical_entry_creation_timestamp_is_not_receiving_date(self):
        movements,stock=self.stock()
        for movement in movements:
            movement['created_at']=datetime(2026,9,25,3,29,tzinfo=timezone.utc)
            movement['journal_entry_id']=None
        repair.validate_remaining_stock(ITEMS,movements,stock)

    def test_failure_reports_the_actual_changed_field(self):
        movements,stock=self.stock()
        stock[0]['quantity']='99'
        with self.assertRaisesRegex(ValueError, 'inventory.quantity.*99'):
            repair.validate_remaining_stock(ITEMS,movements,stock)

    def test_missing_journal_link_does_not_allow_another_receipt(self):
        movements,stock=self.stock()
        movements[0]['journal_entry_id']=None
        movements[0]['goods_receipt_id']=666
        with self.assertRaisesRegex(ValueError, 'goods_receipt_id'):
            repair.validate_remaining_stock(ITEMS,movements,stock)

    def test_other_movements_or_warehouse_stock_refuse_deletion(self):
        movements,stock=self.stock()
        for altered in [movements[:-1],movements+[movements[0]]]:
            with self.assertRaises(ValueError):repair.validate_remaining_stock(ITEMS,altered,stock)
        altered=copy.deepcopy(stock);altered[0]['warehouse_id']=12
        with self.assertRaises(ValueError):repair.validate_remaining_stock(ITEMS,movements,altered)

    def test_cost_quantity_or_source_drift_refuses_deletion(self):
        movements,stock=self.stock()
        for field,value in [('quantity','1'),('unit_cost','1'),('journal_entry_id',99),('movement_type','OUT')]:
            altered=copy.deepcopy(movements);altered[0][field]=value
            with self.assertRaises(ValueError):repair.validate_remaining_stock(ITEMS,altered,stock)
        altered=copy.deepcopy(stock);altered[0]['average_cost']='1'
        with self.assertRaises(ValueError):repair.validate_remaining_stock(ITEMS,movements,altered)

    def test_final_journal_has_only_expense_and_original_suspense(self):
        accounts={a:{'id':a,'is_active':True,'is_posting':True,'account_type':t,'normal_balance':n}
                  for a,t,n in [(167,'ASSET','DEBIT'),(177,'ASSET','DEBIT'),
                                (37,'EXPENSE','DEBIT'),(39,'EXPENSE','DEBIT'),(304,'LIABILITY','CREDIT')]}
        products={r['product_id']:{**r,'item_type':'BUY','inventory_treatment':'STOCK',
            'purchase_account_id':39 if r['product_id']==6332 else 37} for r in ITEMS}
        previous=[{'account_id':a,'debit':d,'credit':c} for a,d,c in [
            (167,'1280000','0'),(177,'80000','0'),(37,'2397000','0'),
            (39,'268000','0'),(304,'0','4025000')]]
        expected=repair.target_signature(previous,ITEMS,products,accounts)
        self.assertEqual(expected,repair.Counter({
            (37,Decimal('3677000'),Decimal('0')):1,
            (39,Decimal('348000'),Decimal('0')):1,
            (304,Decimal('0'),Decimal('4025000')):1}))
        accounts[37]['account_type']='ASSET'
        with self.assertRaises(ValueError):repair.target_signature(previous,ITEMS,products,accounts)


if __name__=='__main__':unittest.main()

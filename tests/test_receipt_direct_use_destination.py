"""Exercise the actual receiving validation/routing methods without DB setup."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
tree = ast.parse((ROOT/'app/services/goods_receipt_service.py').read_text())
service = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='GoodsReceiptService')
methods = [n for n in service.body if isinstance(n,ast.FunctionDef)
           and n.name in {'_validate_item_treatments','_receiving_debit_account'}]
module = ast.Module(body=[ast.ImportFrom(module='__future__',
    names=[ast.alias(name='annotations')],level=0),
    ast.ClassDef(name='Service',bases=[],keywords=[],body=methods,decorator_list=[])],type_ignores=[])


class HTTPException(Exception):
    def __init__(self,status_code,detail):
        super().__init__(detail)
        self.status_code=status_code


namespace={'HTTPException':HTTPException}
exec(compile(ast.fix_missing_locations(module),'receiving methods','exec'),namespace)
Service=namespace['Service']


def receipt(destination,*treatments):
    return SimpleNamespace(destination_type=destination,location_id=6,
        items=[SimpleNamespace(product=SimpleNamespace(inventory_treatment=t,code=str(i)))
               for i,t in enumerate(treatments)])


class Resolver:
    def inventory_account(self,product,location):return 'inventory'
    def expense_account(self,product):return 'expense'
    def fixed_asset_account(self,product):return 'fixed_asset'


class DestinationTests(unittest.TestCase):
    def test_stock_and_prepared_food_can_be_received_for_direct_use(self):
        doc=receipt('DIRECT_USE','STOCK','DIRECT_USE','NON_STOCK')
        Service._validate_item_treatments(doc)
        for item in doc.items:
            self.assertEqual(Service._receiving_debit_account(Resolver(),doc,item.product),'expense')

    def test_same_stock_item_retains_inventory_routing_for_warehouse(self):
        doc=receipt('WAREHOUSE','STOCK')
        Service._validate_item_treatments(doc)
        self.assertEqual(Service._receiving_debit_account(Resolver(),doc,doc.items[0].product),'inventory')

    def test_direct_use_items_cannot_enter_warehouse(self):
        for treatments in [('DIRECT_USE',),('STOCK','DIRECT_USE'),('NON_STOCK',)]:
            with self.assertRaises(HTTPException):
                Service._validate_item_treatments(receipt('WAREHOUSE',*treatments))

    def test_fixed_assets_still_capitalize_and_cannot_mix_with_consumption(self):
        doc=receipt('DIRECT_USE','FIXED_ASSET')
        Service._validate_item_treatments(doc)
        self.assertEqual(Service._receiving_debit_account(Resolver(),doc,doc.items[0].product),'fixed_asset')
        with self.assertRaises(HTTPException):
            Service._validate_item_treatments(receipt('DIRECT_USE','FIXED_ASSET','STOCK'))

    def test_unreviewed_items_still_require_mapping(self):
        with self.assertRaises(HTTPException):
            Service._validate_item_treatments(receipt('DIRECT_USE','REVIEW_REQUIRED'))

    def test_routing_rejects_invalid_destinations(self):
        doc=receipt('UNKNOWN','STOCK')
        with self.assertRaises(HTTPException):
            Service._receiving_debit_account(Resolver(),doc,doc.items[0].product)


if __name__=='__main__':unittest.main()

"""Receiving routing rules, including explicit warehouse exceptions."""
from types import SimpleNamespace
import unittest
from fastapi import HTTPException
from app.services.goods_receipt_service import GoodsReceiptService as Service
from app.services.receiving_destination import resolve_destination


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

    def test_direct_use_warehouse_exception_requires_a_reason(self):
        product = SimpleNamespace(code="MEAT", inventory_treatment="DIRECT_USE")
        with self.assertRaises(HTTPException):
            resolve_destination(product, "WAREHOUSE")
        self.assertEqual(resolve_destination(product, "WAREHOUSE", "Frozen imported meat")[0], "WAREHOUSE")
        with self.assertRaises(HTTPException):
            Service._validate_item_treatments(receipt('WAREHOUSE','NON_STOCK'))

    def test_fixed_assets_still_capitalize_alongside_consumption(self):
        doc=receipt('DIRECT_USE','FIXED_ASSET')
        Service._validate_item_treatments(doc)
        self.assertEqual(Service._receiving_debit_account(Resolver(),doc,doc.items[0].product),'fixed_asset')
        Service._validate_item_treatments(receipt('DIRECT_USE','FIXED_ASSET','STOCK'))

    def test_unreviewed_items_still_require_mapping(self):
        with self.assertRaises(HTTPException):
            Service._validate_item_treatments(receipt('DIRECT_USE','REVIEW_REQUIRED'))

    def test_routing_rejects_invalid_destinations(self):
        doc=receipt('UNKNOWN','STOCK')
        with self.assertRaises(HTTPException):
            Service._receiving_debit_account(Resolver(),doc,doc.items[0].product)


if __name__=='__main__':unittest.main()

import importlib.util
from datetime import date
from pathlib import Path
import sys
import tempfile
import unittest
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from prepare_resiping_item_seed import extract, source_year, match_existing
from seed_resiping_items import seed_plan


class ItemSeedTests(unittest.TestCase):
    def test_year_filter_does_not_guess_unyearred_range(self):
        for raw, year in [(date(2025,12,31),2025),('14-1-26',2026),('1-12 APRIL 26',2026),
                           ('31MAR-14APRIL',None),('1-26',None),('15/11/25',2025),('2025/2026',None)]:
            self.assertEqual(source_year(raw),year)

    def workbook(self, path):
        w=Workbook();i=w.active;i.title='INVOICES';e=w.create_sheet('ITEM_ENTRY')
        for sheet in (i,e):
            sheet.append(['Title']);sheet.append(['Description']);sheet.append([])
        i.append(['Invoice ID','Invoice Date','Supplier','Location'])
        i.append(['INV-000001',date(2025,12,31),'Old supplier','DURI'])
        i.append(['INV-000002',date(2026,1,2),'New supplier','DURI'])
        i.append(['INV-000003','1-12 APRIL 26','New supplier','MINAS'])
        e.append(['Start Invoice ID','tanggal','Item','Unit','Qty','Unit Price'])
        e.append(['INV-000001',date(2025,12,31),'Old item','KG',1,100])
        e.append([None,None,'Old carried item','KG',1,100])
        e.append(['INV-000002',date(2026,1,2),'New item','KG',1,100])
        e.append([None,None,'New item','KG',2,100])
        e.append([None,None,'New item','PCS',2,100])
        e.append(['INV-000003',None,'April item','KG',1,100])
        e.append([None,'31MAR-14APRIL','Needs date review','KG',1,100])
        e.append(['INV-999999',date(2026,1,2),'Orphan item','KG',1,100])
        w.save(path)

    def test_carries_dates_within_invoice_resets_at_new_invoice_and_filters_2025(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'source.xlsx';self.workbook(p);report=extract(p)
        self.assertEqual(report['counts']['included_2026_rows'],4)
        self.assertEqual(report['counts']['excluded_pre_2026_rows'],2)
        self.assertEqual(report['counts']['unique_2026_items'],2)
        self.assertEqual(report['counts']['date_or_link_review_rows'],2)
        self.assertEqual(report['counts']['multiple_unit_items'],1)
        self.assertNotIn('OLD ITEM',[i['name'] for i in report['items']])

    def item(self,name='New ingredient', units=None):
        return {'name':name.upper(),'units':units or ['KG'],'unit_review_required':bool(units and len(units)>1),'source_rows':[]}

    def product(self,name='New ingredient', role='BUY', active=True, pid=1):
        return {'id':pid,'code':f'P{pid}','name':name,'item_type':role,'is_active':active,'uom':'KG'}

    def test_reuses_buy_without_editing_sell_or_existing_profile(self):
        products=[self.product(role='SELL',pid=1),self.product(role='BUY',pid=2)]
        report={'items':[self.item()]};seed_plan(report,products)
        self.assertEqual(report['items'][0]['existing_product']['id'],2)
        self.assertEqual(report['new_master_items'],0)

    def test_new_master_requires_classification_no_coa_or_tax_decision(self):
        report={'items':[self.item()]};seed_plan(report,[])
        p=report['items'][0]['new_product']
        self.assertEqual(p['inventory_treatment'],'REVIEW_REQUIRED')
        self.assertEqual(p['tax_category'],'REVIEW_REQUIRED')
        self.assertTrue(all(p[k] is None for k in ('inventory_account_id','purchase_account_id','cogs_account_id','asset_account_id')))
        self.assertLessEqual(len(p['code']),20)
        second={'items':[self.item()]};seed_plan(second,[])
        self.assertEqual(p['code'],second['items'][0]['new_product']['code'])

    def test_alias_inactive_ambiguous_and_unit_conflicts_do_not_create_products(self):
        for item, products in [
            (self.item('WORTEL/CARROT'),[self.product('WORTEL')]),
            (self.item(),[self.product(active=False)]),
            (self.item(),[self.product(pid=1),self.product(pid=2)]),
            (self.item(units=['KG','PCS']),[])]:
            report={'items':[item]};seed_plan(report,products)
            self.assertEqual(report['new_master_items'],0)

    def test_code_collision_is_deferred(self):
        report={'items':[self.item()]};seed_plan(report,[])
        collision=self.product('Entirely unrelated name');collision['code']=report['items'][0]['new_product']['code']
        second={'items':[self.item()]};seed_plan(second,[collision])
        self.assertEqual(second['new_master_items'],0)
        self.assertEqual(second['items'][0]['match_status'],'PRODUCT_CODE_CONFLICT')


if __name__=='__main__':unittest.main()

# Exercise real ORM inserts and repeat runs without touching finance tables.
def test_pending_master_insert_repeat_and_rollback(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    from app.models.product import Product
    from app.models.item_group import ItemGroup
    from app.models.item_subgroup import ItemSubgroup
    from app.models.inventory import Inventory
    from app.models.journal_entry import JournalEntry
    import app.services.audit as audit
    from seed_resiping_items import insert_items
    captured=[]
    monkeypatch.setattr(audit,'record_audit',lambda *args,**kwargs: captured.append(kwargs))
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        item={'name':'BRAND NEW BUY ITEM','units':['KG'],'unit_review_required':False,
              'source_rows':[{'row':5,'raw_receiving_date':date(2026,1,1)}]}
        report={'items':[item],'source_sha256':'source-hash'}
        seed_plan(report,[])
        inserted=insert_items(db,report)
        db.flush()
        assert len(inserted)==1
        p=db.query(Product).one()
        assert p.item_type=='BUY' and p.inventory_treatment=='REVIEW_REQUIRED'
        assert p.inventory_account_id is None and p.tax_category=='REVIEW_REQUIRED'
        assert db.query(ItemGroup).one().item_type=='BUY'
        assert db.query(ItemSubgroup).one().group_id==db.query(ItemGroup).one().id
        assert captured[0]['details']['source_rows'][0]['raw_receiving_date']=='2026-01-01'
        again={'items':[dict(item)],'source_sha256':'source-hash'}
        again['items'][0].pop('new_product',None)
        seed_plan(again,[{'id':p.id,'code':p.code,'name':p.name,'item_type':'BUY','is_active':True,'uom':'KG'}])
        assert insert_items(db,again)==[]
        assert db.query(Inventory).count()==0 and db.query(JournalEntry).count()==0
        db.rollback()
        assert db.query(Product).count()==0 and db.query(ItemGroup).count()==0

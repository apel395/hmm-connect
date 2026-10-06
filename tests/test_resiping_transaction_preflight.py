import copy
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest
from openpyxl import Workbook, load_workbook

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from prepare_resiping_transactions import exact_date, extract_transactions, validate_database, write_xlsx, summary


class TransactionPreflightTests(unittest.TestCase):
    def workbook(self,path):
        w=Workbook();inv=w.active;inv.title='INVOICES';rows=w.create_sheet('ITEM_ENTRY')
        for s in (inv,rows):s.append(['Title']);s.append([]);s.append([])
        inv.append(['Invoice ID','Invoice Date','Supplier','Location','Invoice Number','Invoice Value','Tax'])
        rows.append(['Start Invoice ID','tanggal','Item','Unit','Qty','Unit Price','Diskon','Tax','Line Total'])
        inv.append(['INV-000001',date(2026,1,31),'Supplier','DURI','REAL-1',300,0])
        inv.append(['INV-000002','2-14 JAN 26','Supplier','DURI','REAL-2',100,None])
        inv.append(['INV-000003',date(2025,12,31),'Supplier','DURI','OLD',100,None])
        inv.append(['INV-000004',date(2026,1,31),'Supplier','DURI','MIXED',200,0])
        rows.append(['INV-000001',date(2026,1,2),'Ingredient','KG',1,100,None,None,'=E5*F5'])
        rows.append([None,None,'Ingredient','KG',2,100,None,None,'=E6*F6'])
        rows.append(['INV-000002','2-14 JAN 26','Ingredient','KG',1,100,None,None,'=E7*F7'])
        rows.append(['INV-000003',date(2025,12,31),'Old item','KG','invalid',100,None,None,None])
        rows.append(['INV-000004',date(2025,12,31),'Old mixed','KG',1,100,None,None,None])
        rows.append([None,date(2026,1,3),'Ingredient','KG',1,100,None,None,None])
        w.save(path)

    def report(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'source.xlsx';self.workbook(p);return extract_transactions(p)

    def test_dates_use_latest_range_date_with_explicit_year(self):
        for raw,expected in [('2-14 JAN 26',date(2026,1,14)),('14FEB&1MARET 26',date(2026,3,1)),('31MAR-14APRIL 26',date(2026,4,14)),
                             ('1 JAN 26',date(2026,1,1)),('2,4 APRIL 26',date(2026,4,4)),
                             ('6,11 & 31 MARET 26',date(2026,3,31)),('1-12 APRI 26',date(2026,4,12)),
                             ('31MAR-14APRIL',None),('1-12 APRIL',None),('31FEB-1MARET 26',None),
                             ('31MAR-14BOGUS 26',None),('14APRIL-31MAR 26',date(2026,4,14)),('03/01/2026',date(2026,1,3)),
                             (datetime(2026,3,1),date(2026,3,1)),('2026-01-09',date(2026,1,9))]:
            self.assertEqual(exact_date(raw),expected)

    def test_exclusion_arithmetic_date_carry_and_mixed_invoice(self):
        r=self.report();inv={x['key']:x for x in r['invoices']}
        self.assertEqual(inv['INV-000001']['status'],'SOURCE_VALIDATED')
        self.assertEqual(inv['INV-000001']['computed_gross'],Decimal(300))
        self.assertEqual(inv['INV-000001']['lines'][1]['received_date'],date(2026,1,2))
        self.assertEqual(inv['INV-000003']['status'],'EXCLUDED_PRE_2026')
        self.assertNotIn('INVALID_QUANTITY_PRICE_DISCOUNT_OR_TAX',inv['INV-000003']['excluded'][0]['errors'])
        self.assertIn('MIXED_2025_2026_INVOICE_REQUIRES_SPLIT',inv['INV-000004']['errors'])
        self.assertEqual(inv['INV-000004']['net_total'],100)
        self.assertIn('INVOICE_GROSS_TOTAL_MISMATCH',inv['INV-000004']['errors'])
        self.assertEqual(summary(r)['excluded_pre_2026_rows'],2)

    def test_omitted_tax_is_zero_for_authorized_historical_import(self):
        x=self.report()['invoices'][1]
        self.assertEqual(x['invoice_date'],date(2026,1,14))
        self.assertEqual(x['lines'][0]['received_date'],date(2026,1,14))
        self.assertEqual(x['raw_invoice_date'],'2-14 JAN 26')
        self.assertNotIn('INVOICE_DATE_NOT_SINGLE_DATE',x['errors'])
        self.assertNotIn('INVOICE_TAX_UNCONFIRMED',x['errors'])
        self.assertNotIn('TAX_EVIDENCE_MISSING',x['lines'][0]['errors'])
        self.assertEqual(x['computed_gross'],Decimal(100))
        self.assertEqual(x['gross_difference'],Decimal(0))
        self.assertIsNone(x['raw_invoice_tax'])
        self.assertIsNone(x['lines'][0]['raw_tax'])
        self.assertEqual(x['declared_tax'],Decimal(0))
        self.assertNotIn('INVOICE_GROSS_TOTAL_MISMATCH',x['errors'])

    def test_entered_tax_is_retained_and_positive_header_is_not_distributed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'source.xlsx';self.workbook(p)
            w=load_workbook(p);w['INVOICES']['G5']=None;w['INVOICES']['F5']=311;w['ITEM_ENTRY']['H5']=11;w.save(p);w.close()
            inv=extract_transactions(p)['invoices'][0]
            self.assertEqual(inv['declared_tax'],Decimal(11))
            self.assertEqual(inv['computed_gross'],Decimal(311))
            self.assertEqual(inv['lines'][0]['tax'],Decimal(11))
            self.assertEqual(inv['lines'][1]['tax'],Decimal(0))
            self.assertNotIn('INVOICE_TAX_TOTAL_MISMATCH',inv['errors'])
            w=load_workbook(p);w['INVOICES']['G5']=11;w['ITEM_ENTRY']['H5']=None;w.save(p);w.close()
            inv=extract_transactions(p)['invoices'][0]
            self.assertIn('TAX_EVIDENCE_MISSING',inv['lines'][0]['errors'])
            self.assertIsNone(inv['computed_gross'])

    def test_historical_invoice_can_precede_or_follow_receiving(self):
        for received in (date(2026,1,2),date(2026,9,1)):
            with tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'source.xlsx';self.workbook(p)
                w=load_workbook(p);w['ITEM_ENTRY']['B5']=received;w.save(p);w.close()
                inv=extract_transactions(p)['invoices'][0]
            self.assertEqual(inv['invoice_date'],date(2026,1,31))
            self.assertEqual(inv['lines'][0]['received_date'],received)
            self.assertEqual(inv['lines'][1]['received_date'],received)
            self.assertNotIn('RECEIPT_AFTER_INVOICE_DATE',inv['lines'][0]['errors'])
            self.assertEqual(inv['status'],'SOURCE_VALIDATED')

    def test_discount_is_recomputed_without_executing_formula(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'source.xlsx';self.workbook(p)
            w=load_workbook(p);s=w['ITEM_ENTRY'];s['E5']=2;s['F5']=50;s['G5']=10;s['H5']=11;s['H6']=0;s['I5']='=1/0'
            w['INVOICES']['F5']=301;w['INVOICES']['G5']=11;w.save(p);w.close()
            x=extract_transactions(p)['invoices'][0]
        self.assertEqual(x['lines'][0]['net'],90)
        self.assertEqual(x['computed_gross'],301)
        self.assertIn('DISCOUNT_POSTING_REVIEW',x['lines'][0]['errors'])

    def catalog(self):
        return {'products':[{'id':1,'code':'P1','name':'Ingredient','item_type':'BUY','is_active':True,'uom':'KG','inventory_treatment':'STOCK','inventory_account_id':167,'tax_category':'NON_TAXABLE'}],
                'suppliers':[{'id':1,'name':'Supplier','code':'S1','is_active':True,'is_pkp':False}],
                'locations':[{'id':1,'name':'DURI','code':'DURI','is_active':True}],
                'departments':[{'id':1,'location_id':1,'name':'Kitchen','is_active':True}],
                'warehouses':[{'id':1,'location_id':1,'name':'Warehouse','is_active':True}],
                'accounts':[{'id':167,'is_active':True,'is_posting':True,'account_type':'ASSET','normal_balance':'DEBIT'}],
                'periods':[{'id':1,'start_date':date(2026,1,1),'end_date':date(2026,1,31),'is_open':True,'is_closed':False,'allow_backdated_entries':True}],
                'invoices':[],'receipts':[]}

    def test_db_mapping_respects_roles_units_periods_and_duplicates(self):
        report=self.report();catalog=self.catalog();original=copy.deepcopy(catalog)
        catalog['products'].append({**catalog['products'][0],'id':2,'item_type':'SELL'})
        catalog['invoices']=[{'id':4,'internal_invoice_number':'SI-1','supplier_invoice_number':'REAL-1','supplier_id':1,'invoice_date':date(2026,1,31),'total_amount':Decimal(300),'status':'POSTED'}]
        catalog['receipts']=[{'id':5,'receipt_number':'GR-1','supplier_id':1,'location_id':1,'received_at':datetime(2026,1,2),'status':'POSTED'}]
        validate_database(report,catalog,date(2026,10,7));x=report['invoices'][0]
        self.assertEqual(x['lines'][0]['product_id'],1)
        self.assertIn('EXISTING_INVOICE_REVIEW',x['errors'])
        self.assertIn('EXISTING_RECEIPT_REVIEW',x['lines'][0]['errors'])
        self.assertEqual(x['lines'][0]['warehouse_id'],1)
        self.assertNotIn('WAREHOUSE_SELECTION_REQUIRED',x['lines'][0]['errors'])
        self.assertIn('DEPARTMENT_SELECTION_REQUIRED',x['errors'])
        self.assertFalse(report['seed_ready'])
        # The validation never changes catalog/master values.
        self.assertEqual(catalog['products'][0],original['products'][0])
        r=self.report();catalog=self.catalog();catalog['products'][0]['uom']='PACK'
        catalog['products'][0]['tax_category']='REVIEW_REQUIRED'
        catalog['periods'][0]['allow_backdated_entries']=False
        validate_database(r,catalog,date(2026,10,7));x=r['invoices'][0]
        self.assertIn('UNIT_OR_CONVERSION_REVIEW',x['lines'][0]['errors'])
        self.assertNotIn('ITEM_TAX_REVIEW_REQUIRED',x['lines'][0]['errors'])
        self.assertTrue(any(e.startswith('BACKDATE_NOT_ALLOWED') for e in x['errors']))

    def test_confirmed_location_aliases_preserve_source_and_target_scope(self):
        cases={'Rumbai':6,'Minas':6,'Hulu Cafe':6,'Hulu Café':6,
               'Libo':10,'Petapahan':10,'Zamrud':4,'Pedada':4}
        for source,target in cases.items():
            report=self.report();report['invoices'][0]['location']=source
            catalog=self.catalog()
            catalog['locations']=[{'id':6,'name':'Rumin','is_active':True},
                                  {'id':10,'name':'Lipet','is_active':True},
                                  {'id':4,'name':'Zamped','is_active':True},
                                  {'id':7,'name':'Pedada','is_active':False}]
            catalog['departments'][0]['location_id']=target
            catalog['warehouses'][0]['location_id']=target
            validate_database(report,catalog)
            inv=report['invoices'][0]
            self.assertEqual(inv['location'],source)
            self.assertEqual(inv['location_id'],target)
            self.assertEqual(inv['location_mapping_rule'],'USER_CONFIRMED_ALIAS')
            self.assertNotIn('LOCATION_NOT_UNIQUELY_MATCHED',inv['errors'])
            self.assertEqual(inv['warehouse_candidates'][0]['location_id'],target)
        report=self.report();report['invoices'][0]['location']='Minas'
        catalog=self.catalog();catalog['locations']=[{'id':6,'name':'Rumin','is_active':False}]
        validate_database(report,catalog)
        self.assertIsNone(report['invoices'][0]['location_id'])
        self.assertIn('LOCATION_NOT_UNIQUELY_MATCHED',report['invoices'][0]['errors'])

    def test_operational_department_and_unique_stock_warehouse(self):
        report=self.report();catalog=self.catalog()
        catalog['departments'][0]['name']='Operasional'
        validate_database(report,catalog)
        inv=report['invoices'][0]
        self.assertEqual(inv['department_id'],1)
        self.assertNotIn('DEPARTMENT_SELECTION_REQUIRED',inv['errors'])
        self.assertEqual(inv['lines'][0]['warehouse_id'],1)
        self.assertEqual(inv['lines'][0]['department_id'],1)
        # Direct-use items have no warehouse, regardless of available warehouses.
        report=self.report();catalog['products'][0].update(inventory_treatment='DIRECT_USE',purchase_account_id=167)
        validate_database(report,catalog)
        self.assertIsNone(report['invoices'][0]['lines'][0]['warehouse_id'])
        self.assertNotIn('WAREHOUSE_SELECTION_REQUIRED',report['invoices'][0]['lines'][0]['errors'])
        # Ambiguous or missing warehouse/departments are never guessed.
        report=self.report();catalog=self.catalog();catalog['warehouses'].append({**catalog['warehouses'][0],'id':2})
        validate_database(report,catalog)
        self.assertIn('WAREHOUSE_SELECTION_REQUIRED',report['invoices'][0]['lines'][0]['errors'])
        self.assertIn('DEPARTMENT_SELECTION_REQUIRED',report['invoices'][0]['errors'])
        report=self.report();report['invoices'][0]['location']='Head Office'
        catalog=self.catalog();catalog['locations'][0]['name']='Head Office';catalog['departments'][0]['name']='Operasional'
        validate_database(report,catalog)
        self.assertIsNone(report['invoices'][0].get('department_id'))
        self.assertIn('DEPARTMENT_SELECTION_REQUIRED',report['invoices'][0]['errors'])

    def test_agro_boga_uses_confirmed_225_without_fallback_to_duplicate(self):
        for label in ('ARGO BOGA UTAMA','AGRO BOGA UTAMA','PT. AGRO BOGA UTAMA','PT.AGRO BOGA UTAMA'):
            report=self.report();report['invoices'][0]['supplier']=label
            catalog=self.catalog();catalog['suppliers']=[
                {'id':225,'name':'PT. AGRO BOGA UTAMA','code':'HIST-SUP-00015','is_active':True,'is_pkp':False},
                {'id':242,'name':'PT.AGRO BOGA UTAMA','code':'HIST-SUP-00020','is_active':True,'is_pkp':False}]
            validate_database(report,catalog)
            inv=report['invoices'][0]
            self.assertEqual(inv['supplier_id'],225)
            self.assertEqual(inv['supplier'],label)
            self.assertEqual(inv['supplier_mapping_rule'],'USER_CONFIRMED_SUPPLIER_225')
            self.assertNotIn('SUPPLIER_NOT_UNIQUELY_MATCHED',inv['errors'])
        for replacement in (None,{'id':225,'name':'Other supplier','is_active':True},
                            {'id':225,'name':'PT. AGRO BOGA UTAMA','is_active':False}):
            report=self.report();report['invoices'][0]['supplier']='ARGO BOGA UTAMA'
            catalog=self.catalog();catalog['suppliers']=[{'id':242,'name':'PT.AGRO BOGA UTAMA','is_active':True}]
            if replacement:catalog['suppliers'].append(replacement)
            validate_database(report,catalog)
            self.assertIsNone(report['invoices'][0]['supplier_id'])
            self.assertIn('SUPPLIER_NOT_UNIQUELY_MATCHED',report['invoices'][0]['errors'])

    def test_xlsx_source_text_is_not_executable_and_summary_is_compact(self):
        r=self.report();r['invoices'][0]['supplier']='=HYPERLINK("bad")'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'review.xlsx';write_xlsx(r,p);w=load_workbook(p,data_only=False)
            self.assertEqual(w['Invoices']['C2'].data_type,'s')
            self.assertEqual(w['Invoices']['C2'].value,'=HYPERLINK("bad")')
            self.assertEqual(w.sheetnames,['Invoices','Receiving','Excluded 2025','Unlinked'])
            w.close()
        self.assertNotIn('invoices',summary(r))
        self.assertFalse(summary(r)['database_checked'])


def test_db_catalog_queries_use_actual_schema_without_writes():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.models import Base
    from prepare_resiping_transactions import db_catalog
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine) as db:
        result=db_catalog(db)
        assert set(result)=={'products','suppliers','locations','departments','warehouses','accounts','periods','invoices','receipts'}
        assert all(rows==[] for rows in result.values())

from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_finance_delivery_1007 import db, ADMIN
from test_pos_ar_invoices import invoice_setup
from app.models.location import Location
from app.models.location_department import LocationDepartment
from app.models.customer import Customer
from app.models.catering_billing import CateringLocationBilling
from app.models.account_receivable import AccountReceivable
from app.models.ar_invoice_layout import ARInvoiceLayout
from app.models.stock_movement import StockMovement
from app.models.general_ledger import GeneralLedger
from app.models.opening_balance import OpeningBalance
from app.api.v1.sales import (save_catering_defaults, catering_defaults, validate_catering_context,
    CateringOrderContext, list_pos_products, get_sale, update_sale)
from app.api.v1.ar_invoice_print import invoice as print_invoice
from app.schemas.catering_billing import CateringLocationSettings, CateringBilling
from app.schemas.sales_transaction import SalesTransactionCreate, SalesTransactionUpdate, SalesTransactionPost
from app.services.sales_transaction_service import SalesTransactionService as Service


def prepare(db,monkeypatch):
    s,tx,c,ar,base,tax=invoice_setup(db,monkeypatch)
    target=Location(code='PHR-OTHER',name='Other Catering',business_unit_id=tx.business_unit_id,is_active=True)
    s.add(target);s.flush()
    s.add(LocationDepartment(location_id=target.id,department_id=tx.department_id))
    c2=Customer(customer_code='PHE-SITE',customer_name='Pertamina Other Site',address='Site billing address',is_active=True)
    s.add(c2);s.flush()
    product=tx.lines[0].product
    product.sales_location_id=tx.location_id;product.sales_business_unit_id=tx.business_unit_id
    s.commit()
    config=CateringLocationSettings(customer_id=c2.id,department_id=tx.department_id,
        revenue_account_id=base[0].id,receivable_account_id=ar.id,payment_term_days=30,
        service_product_ids=[product.id],billing=CateringBilling(contract_number='CONTRACT-OTHER',attention='AP Site'))
    save_catering_defaults(target.id,config,s,ADMIN)
    return s,tx,target,c2,config


def line(tx,**extra):
    return dict(product_id=tx.lines[0].product_id,quantity=2,unit_price=250000,**extra)


def test_explicit_shared_service_and_move_draft_keep_identity_and_financial_scope(db,monkeypatch):
    s,tx,target,c2,config=prepare(db,monkeypatch)
    identity=(tx.id,tx.transaction_number)
    preview=validate_catering_context(target.id,CateringOrderContext(department_id=tx.department_id,items=[line(tx)]),s,ADMIN)
    assert preview['location_id']==target.id and tx.location_id!=target.id
    menu=list_pos_products(location_id=target.id,department_id=tx.department_id,transaction_type='INVOICE',search=None,group_name=None,page=1,page_size=100,db=s,user=ADMIN)
    assert menu['items'][0]['catering_shared']
    Service.update(s,transaction=tx,data=SalesTransactionUpdate(location_id=target.id,department_id=tx.department_id,customer_id=c2.id,
        billing_details=CateringBilling(contract_number='INVOICE-CONTRACT',billing_name=c2.customer_name,billing_address=c2.address),
        notes='Catering January',items=[line(tx,description='Lunch service',registration_number='REG-42',service_period_from='2026-01-01',service_period_to='2026-01-15',uom='Period')]),user=ADMIN)
    assert (tx.id,tx.transaction_number)==identity and tx.status=='DRAFT'
    assert tx.location_id==target.id and tx.total_amount==D('550000')
    assert tx.lines[0].product.sales_location_id!=target.id and tx.lines[0].product.selling_price==100000
    assert not s.query(GeneralLedger).count() and not s.query(StockMovement).count()
    snapshot=dict(tx.billing_details)
    config.billing.contract_number='CHANGED-DEFAULT';save_catering_defaults(target.id,config,s,ADMIN)
    c2.customer_name='Changed Customer Master';c2.address='Changed Address';tx.lines[0].product.name='Changed Service Master';s.commit()
    Service.post(s,transaction_id=tx.id,data=SalesTransactionPost(),user=ADMIN)
    ar=s.query(AccountReceivable).one()
    assert ar.location_id==target.id and ar.customer_id==c2.id and ar.amount==D('550000')
    printed=print_invoice(ar.id,s,ADMIN)
    assert printed['layout']['template']=='phr' and printed['layout']['billing_name']=='Pertamina Other Site'
    assert printed['layout']['billing_address']=='Site billing address'
    assert printed['document']['contract_number']=='INVOICE-CONTRACT'
    assert printed['document']['lines'][0]['registration_number']=='REG-42'
    assert printed['document']['lines'][0]['description']=='Lunch service\n2026-01-01 — 2026-01-15'
    assert printed['print_ready'] and tx.billing_details==snapshot
    assert s.query(StockMovement).count()==s.query(OpeningBalance).count()==0
    ledger=s.query(GeneralLedger).count()
    with pytest.raises(HTTPException):Service.post(s,transaction_id=tx.id,data=SalesTransactionPost(),user=ADMIN)
    with pytest.raises(HTTPException):update_sale(tx.id,SalesTransactionUpdate(location_id=target.id,items=[line(tx)]),s,ADMIN)
    assert s.query(GeneralLedger).count()==ledger


def test_unavailable_or_unscoped_context_does_not_move_draft(db,monkeypatch):
    s,tx,target,c2,config=prepare(db,monkeypatch)
    config.service_product_ids=[];save_catering_defaults(target.id,config,s,ADMIN)
    original=(tx.location_id,tx.department_id,tx.customer_id,tx.total_amount)
    with pytest.raises(HTTPException):validate_catering_context(target.id,CateringOrderContext(department_id=tx.department_id,items=[line(tx)]),s,ADMIN)
    with pytest.raises(HTTPException):update_sale(tx.id,SalesTransactionUpdate(location_id=target.id,department_id=tx.department_id,items=[line(tx)]),s,ADMIN)
    s.rollback()
    assert original==(tx.location_id,tx.department_id,tx.customer_id,tx.total_amount)
    limited=SimpleNamespace(**{**vars(ADMIN),'roles':[SimpleNamespace(name='FINANCE',permissions=[SimpleNamespace(code='pos.sell'),SimpleNamespace(code='pos.view')])],'default_location_id':tx.location_id})
    with pytest.raises(HTTPException):catering_defaults(target.id,s,limited)
    with pytest.raises(HTTPException):validate_catering_context(target.id,CateringOrderContext(items=[line(tx)]),s,limited)
    with pytest.raises(HTTPException):save_catering_defaults(tx.location_id,config,s,limited)
    assert s.query(GeneralLedger).count()==0


def test_shared_location_setting_never_expands_normal_pos(db,monkeypatch):
    s,tx,target,_,_=prepare(db,monkeypatch)
    # Sharing expands only invoice service availability.
    with pytest.raises(HTTPException):Service.create(s,data=SalesTransactionCreate(transaction_type='POS',location_id=target.id,department_id=tx.department_id,items=[line(tx)]),user=ADMIN)
    s.rollback()
    assert tx.status=='DRAFT'
    normal=list_pos_products(location_id=target.id,department_id=tx.department_id,transaction_type='POS',search=None,group_name=None,page=1,page_size=100,db=s,user=ADMIN)
    assert tx.lines[0].product_id not in [p['product_id'] for p in normal['items']]


def test_generic_service_is_shared_without_configuration_and_non_phr_customer_uses_catering_layout(db,monkeypatch):
    s,tx,target,c2,_=prepare(db,monkeypatch)
    s.delete(s.get(CateringLocationBilling,target.id));tx.lines[0].product.sales_location_id=None;s.commit()
    # The existing Item Master all-locations option continues to work.
    context=validate_catering_context(target.id,CateringOrderContext(department_id=tx.department_id,items=[line(tx)]),s,ADMIN)
    assert context['location_id']==target.id
    Service.update(s,transaction=tx,data=SalesTransactionUpdate(location_id=target.id,department_id=tx.department_id,customer_id=c2.id,items=[line(tx)]),user=ADMIN)
    assert tx.billing_details['template']=='phr' and tx.billing_details['billing_name']==c2.customer_name
    Service.post(s,transaction_id=tx.id,data=SalesTransactionPost(),user=ADMIN)
    assert print_invoice(s.query(AccountReceivable).one().id,s,ADMIN)['layout']['template']=='phr'


def test_period_lines_same_price_are_distinct_and_invalid_period_rejected(db,monkeypatch):
    s,tx,_,_,_=prepare(db,monkeypatch)
    Service.update(s,transaction=tx,data=SalesTransactionUpdate(items=[line(tx,description='First period',service_period_from='2026-01-01',service_period_to='2026-01-15'),line(tx,description='Second period',service_period_from='2026-01-16',service_period_to='2026-01-31')]),user=ADMIN)
    assert len(tx.lines)==2 and tx.total_amount==1100000
    saved=get_sale(tx.id,s,ADMIN)
    assert [r['description'] for r in saved['items']]==['First period','Second period']
    with pytest.raises(ValidationError):SalesTransactionUpdate(items=[line(tx,service_period_from='2026-02-01',service_period_to='2026-01-01')])


def test_settings_reject_wrong_accounts_products_and_hotel(db,monkeypatch):
    from app.models.business_unit import BusinessUnit
    s,tx,target,c2,config=prepare(db,monkeypatch)
    for invalid in [config.model_copy(update={'receivable_account_id':tx.lines[0].product.id+999}),config.model_copy(update={'revenue_account_id':999}),config.model_copy(update={'service_product_ids':[999]})]:
        with pytest.raises(HTTPException):save_catering_defaults(target.id,invalid,s,ADMIN)
        s.rollback()
    hotel=BusinessUnit(code='H2',name='Hotel',is_active=True);s.add(hotel);s.flush()
    loc=Location(code='H2',name='Hotel',business_unit_id=hotel.id,is_active=True);s.add(loc);s.commit()
    with pytest.raises(HTTPException):catering_defaults(loc.id,s,ADMIN)
    assert s.query(CateringLocationBilling).count()==1

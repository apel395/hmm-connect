from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models import Base
from app.models.business_unit import BusinessUnit
from app.models.department import Department
from app.models.location import Location
from app.models.location_department import LocationDepartment
from app.models.product import Product
from app.models.item_department import ItemDepartment
from app.models.purchasing_item_policy import is_market_list_product
from app.services.item_departments import assign, options, payloads
from app.services.item_reference_cost import serialize_item
from app.services.receiving_destination import resolve_destination
from app.api.v1.products import _apply_filters
from scripts.audit_item_duplicates_1017 import duplicate_groups

ADMIN=SimpleNamespace(roles=[SimpleNamespace(name='SYSTEM_ADMINISTRATOR')])


@pytest.fixture
def db():
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        h=BusinessUnit(code='H',name='Hotel');c=BusinessUnit(code='C',name='Project Catering')
        session.add_all([h,c]);session.flush()
        hd=Department(code='HK',name='House Keeping',business_unit_id=h.id)
        cd=Department(code='OPS',name='Operasional',business_unit_id=c.id)
        session.add_all([hd,cd]);session.flush()
        loc=Location(code='H',name='Hotel',business_unit_id=h.id);session.add(loc);session.flush()
        session.add(LocationDepartment(location_id=loc.id,department_id=hd.id))
        p=Product(code='TEST',name='Item',group_code='3',group_name='MATERIAL',subgroup_code='3-1',subgroup_name='SUPPLIES',uom='PCS',usage_uom='PCS',catalog_type='HOTEL',inventory_treatment='DIRECT_USE')
        session.add(p);session.commit()
        yield session,p,hd,cd,loc
    engine.dispose()


def test_department_assignment_clear_and_catalog_location_access(db):
    session,p,hd,cd,loc=db
    assign(session,p,hd.id,ADMIN);session.commit()
    assert payloads(session,[p.id])[p.id]=={'department_id':hd.id,'department_name':hd.name}
    with pytest.raises(HTTPException):assign(session,p,cd.id,ADMIN)
    scoped=SimpleNamespace(roles=[],default_location_id=loc.id,location_id=loc.id)
    assert [d.id for d in options(session,scoped,'HOTEL')]==[hd.id]
    assert options(session,scoped,'CATERING')==[]
    assign(session,p,None,ADMIN);session.commit()
    assert payloads(session,[p.id])=={}
    assert session.query(Product).count()==1


def test_missing_migration_keeps_item_reads_and_unassigned_writes_available(db):
    session,p,hd,_,_=db
    ItemDepartment.__table__.drop(session.connection());session.info.clear()
    assert serialize_item(p)['code']=='TEST'
    assert payloads(session,[p.id])=={}
    assign(session,p,None,ADMIN)
    with pytest.raises(HTTPException) as error:assign(session,p,hd.id,ADMIN)
    assert error.value.status_code==503


@pytest.mark.parametrize('family', ['VEGETABLES','FRUIT','HERB','FISH','POULTRY','SNACK'])
def test_market_lookup_policy_and_receiving_destination_agree(db,family):
    session,p,*_=db
    p.subgroup_name=family;p.item_type='BUY';session.commit()
    assert is_market_list_product(p)
    assert _apply_filters(session.query(Product),active_only=True,search=None,market_only=True).one().id==p.id
    assert resolve_destination(p)[0]=='DIRECT_USE'
    # A real warehouse exception needs evidence and does not change the master.
    with pytest.raises(HTTPException):resolve_destination(p,'WAREHOUSE')
    assert resolve_destination(p,'WAREHOUSE','Imported frozen stock')[0]=='WAREHOUSE'
    assert p.inventory_treatment=='DIRECT_USE'


def test_meat_opt_in_sell_exclusion_and_normal_pr_path(db):
    session,p,*_=db
    p.subgroup_name='MEAT';p.inventory_treatment='STOCK';p.is_market_item=False;session.commit()
    assert not is_market_list_product(p)
    assert _apply_filters(session.query(Product),active_only=True,search=None,exclude_market=True).one().id==p.id
    assert resolve_destination(p)[0]=='WAREHOUSE'
    p.is_market_item=True;session.commit()
    assert is_market_list_product(p)
    p.item_type='SELL';session.commit()
    assert not is_market_list_product(p)
    assert not _apply_filters(session.query(Product),active_only=True,search=None,market_only=True).all()


def test_duplicate_review_keeps_catalog_and_buy_sell_separate_and_reports_unit_conflicts():
    rows=[dict(id=i,catalog_type=c,item_type=t,name=n,uom=u) for i,c,t,n,u in [(1,'HOTEL','BUY','Rice','KG'),(2,'HOTEL','BUY','  RICE ','PACK'),(3,'CATERING','BUY','Rice','KG'),(4,'HOTEL','SELL','Rice','KG')]]
    groups=duplicate_groups(rows)
    assert len(groups)==1
    assert {r['id'] for r in groups[0]['items']}=={1,2}
    assert groups[0]['action']=='REVIEW_REFERENCES_AND_UNITS_BEFORE_MERGE'

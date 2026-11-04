from types import SimpleNamespace
from app.services.pos_access_review import review_pos_access
from app.models.business_unit import BusinessUnit
from app.models.location import Location
from test_finance_delivery_1007 import db, ADMIN
from test_pos_sell_catalog_1021 import products


def actor(id, role, permissions=(), **scope):
    return SimpleNamespace(id=id, username=f'admin-{id}',is_active=True,
        roles=[SimpleNamespace(name=role,permissions=[SimpleNamespace(code=p) for p in permissions])],
        **scope)


def test_two_canonical_admin_profiles_see_same_catering_despite_assignments(db):
    s,unit,loc,dept,accounts=db
    products(s)
    first=actor(1,'SYSTEM_ADMINISTRATOR')
    second=actor(2,'SYSTEM_ADMINISTRATOR',default_location_id=999,default_business_unit_id=999)
    a,b=review_pos_access(s,first),review_pos_access(s,second)
    assert a['locations']==b['locations']
    assert a['locations'][0]['catalog_type']=='CATERING'
    assert a['locations'][0]['contexts'][0]['menu_count']==1
    assert a['canonical_admin'] and b['canonical_admin']


def test_custom_admin_requires_explicit_pos_permission_and_retains_scope(db):
    s,unit,loc,dept,accounts=db
    products(s)
    denied=review_pos_access(s,actor(2,'ADMIN',('products.view',)))
    assert denied['findings']==['POS_VIEW_PERMISSION_MISSING'] and not denied['locations']
    allowed=review_pos_access(s,actor(3,'CUSTOM_ADMIN',('pos.manage',),default_location_id=loc.id))
    assert allowed['pos_permissions']=={'pos.view':True,'pos.sell':True,'pos.manage':True}
    assert [row['id'] for row in allowed['locations']]==[loc.id]
    other=BusinessUnit(code='H-ACCESS',name='Hotel',is_active=True);s.add(other);s.flush()
    hotel=Location(code='H-ACCESS',name='Hotel',business_unit_id=other.id,is_active=True);s.add(hotel);s.commit()
    hotel_only=review_pos_access(s,actor(4,'CUSTOM_ADMIN',('pos.view',),default_location_id=hotel.id))
    assert 'NO_CATERING_LOCATION_IN_ACCOUNT_SCOPE' in hotel_only['findings']
    assert [row['id'] for row in hotel_only['locations']]==[hotel.id]
    assert hotel_only['locations'][0]['finding']=='NO_ACTIVE_FNB_OUTLET'
    assert 'pos.view' not in denied['pos_permissions'] or not denied['pos_permissions']['pos.view']

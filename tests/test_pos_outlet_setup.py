from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.models.department import Department
from app.models.department_outlet import DepartmentOutlet
from app.models.location_department import LocationDepartment
from app.models.pos_operations import PosOutletPolicy
from app.models.sales_transaction import SalesTransaction
from app.models.general_ledger import GeneralLedger
from app.schemas.pos_operations import OutletSetupIn
from app.services import pos_outlet_setup as setup
from app.services import pos_operations as ops
from app.api.v1.sales import sale_options
from test_pos_operations import hotel, prepare
from test_finance_delivery_1007 import db, ADMIN


def data(hotel, **values):
    s, scope, *_ = hotel
    parent = s.get(DepartmentOutlet, scope['department_id']).parent_department_id
    return OutletSetupIn(location_id=scope['location_id'], parent_department_id=parent,
                         **{'name': 'Coffee Shop', 'code': 'COF', 'order_mode': 'COUNTER', **values})


def test_create_outlet_and_mode_in_one_transaction_without_accounting(hotel):
    s, scope, *_ = hotel
    before = s.query(SalesTransaction).count(), s.query(GeneralLedger).count()
    result = setup.save_outlet(s, ADMIN, data(hotel))
    row = s.get(Department, result['id'])
    assert row.code == 'COF' and row.name == 'Coffee Shop'
    assert s.get(DepartmentOutlet, row.id).parent_department_id == data(hotel).parent_department_id
    assert s.query(LocationDepartment).filter_by(department_id=row.id).count() == 1
    assert s.query(PosOutletPolicy).filter_by(department_id=row.id).one().order_mode == 'COUNTER'
    assert (s.query(SalesTransaction).count(), s.query(GeneralLedger).count()) == before
    assert setup.list_outlets(s, ADMIN, scope['location_id'])['parents'][0]['name'] == 'Food and Beverage'
    option = next(d for d in sale_options(s, ADMIN)['departments'] if d['id'] == row.id)
    assert option['code'] == 'COF' and option['is_fnb_outlet']


def test_edit_deactivate_reactivate_and_busy_guard(hotel):
    s, scope, *_ = hotel
    result = setup.save_outlet(s, ADMIN, data(hotel))
    changed = setup.save_outlet(s, ADMIN, data(hotel, name='Coffee Corner', is_active=False), result['id'])
    assert not changed['is_active']
    assert result['id'] not in {d['id'] for d in sale_options(s, ADMIN)['departments']}
    setup.save_outlet(s, ADMIN, data(hotel), result['id'])
    prepare(hotel)
    with pytest.raises(HTTPException) as err:
        setup.save_outlet(s, ADMIN, data(hotel, name='Changed', code='CHG'), scope['department_id'])
    assert err.value.status_code == 409


def test_duplicate_name_or_code_returns_actionable_conflict(hotel):
    s, *_ = hotel
    setup.save_outlet(s, ADMIN, data(hotel))
    for values in ({'name':'Another shop'}, {'code':'CAF'}, {'name':'coffee shop', 'code':'CAF'}):
        with pytest.raises(HTTPException) as error:
            setup.save_outlet(s, ADMIN, data(hotel, **values))
        assert error.value.status_code == 409
    assert s.query(Department).filter_by(code='COF').count() == 1


def test_cannot_make_support_department_or_foreign_location_outlet(hotel):
    s, scope, *_ = hotel
    root = s.get(Department, data(hotel).parent_department_id)
    root.name, root.code = 'Accounting', 'ACC'; s.commit()
    assert not setup.list_outlets(s, ADMIN, scope['location_id'])['parents']
    assert not any(d['is_fnb_outlet'] for d in sale_options(s, ADMIN)['departments'])
    with pytest.raises(HTTPException):
        setup.save_outlet(s, ADMIN, data(hotel))
    with pytest.raises(HTTPException):
        ops.outlet(s, ADMIN, **scope)


def test_scoped_and_cashier_access_cannot_create_master(hotel):
    s, scope, *_ = hotel
    cashier = SimpleNamespace(**{**vars(ADMIN), 'roles': []})
    with pytest.raises(HTTPException) as err:
        setup.save_outlet(s, cashier, data(hotel))
    assert err.value.status_code == 403
    scoped = SimpleNamespace(**{**vars(cashier), 'default_location_id': 999})
    with pytest.raises(HTTPException):
        setup.list_outlets(s, scoped, scope['location_id'])


def test_three_letter_code_and_nonempty_name(hotel):
    assert data(hotel, code=' cof ').code == 'COF'
    for values in ({'code':'COFFEE'}, {'code':'CO1'}, {'name':'  '}):
        with pytest.raises(ValidationError):
            data(hotel, **values)


def test_hotel_without_outlets_cannot_fall_back_to_support_department(hotel):
    from app.services.sales_transaction_service import SalesTransactionService as Sales
    from app.schemas.sales_transaction import SalesTransactionCreate
    from datetime import date
    s, scope, product, *_ = hotel
    s.delete(s.get(DepartmentOutlet, scope['department_id'])); s.commit()
    with pytest.raises(HTTPException):
        Sales.create(s, data=SalesTransactionCreate(**scope, sale_date=date(2026,1,5), items=[dict(product_id=product.id, quantity=1)]), user=ADMIN)

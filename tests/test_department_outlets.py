from datetime import date
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from app.models.department import Department
from app.models.location_department import LocationDepartment
from app.models.department_outlet import DepartmentOutlet
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.schemas.organization_dimensions import DepartmentCreate, DepartmentUpdate
from app.api.v1.organization_dimensions import create_department,update_department,list_departments
from app.services.department_outlets import assign,labels
from app.services.financial_reporting_service import FinancialReportingService
from app.services.profit_loss_delivery import deliver,workbook_sheets
from test_profit_loss_formulas import verify_formulas
from test_organization_and_asset_delivery import db,ADMIN,scoped_user


def outlet(db):
    parent=create_department(DepartmentCreate(code='FB',name='Food and Beverage',business_unit_id=1),db,ADMIN)
    db.add(LocationDepartment(location_id=1,department_id=parent['id']));db.commit()
    child=create_department(DepartmentCreate(code='REST',name='Restaurant',business_unit_id=1,parent_department_id=parent['id']),db,ADMIN)
    return parent,child


def test_outlet_inherits_parent_location_and_payload_and_does_not_escape_access(db):
    parent,child=outlet(db)
    assert child['parent_department_id']==parent['id']
    assert child['display_name']=='Food and Beverage / Restaurant'
    assert db.query(LocationDepartment).filter_by(location_id=1,department_id=child['id']).one()
    assert child['id'] in {d['id'] for d in list_departments(location_id=1,db=db,user=ADMIN)}
    assert child['id'] not in {d['id'] for d in list_departments(db=db,user=scoped_user(True))}
    with pytest.raises(HTTPException):
        create_department(DepartmentCreate(code='OTHER',name='Catering outlet',business_unit_id=2,parent_department_id=parent['id']),db,ADMIN)
    db.rollback()


def test_cycles_nested_outlets_and_parent_deactivation_are_rejected(db):
    parent,child=outlet(db)
    for department,parent_id in [(db.get(Department,parent['id']),child['id']),(db.get(Department,child['id']),child['id'])]:
        with pytest.raises(HTTPException):assign(db,department,parent_id)
    with pytest.raises(HTTPException):update_department(parent['id'],DepartmentUpdate(is_active=False),db,ADMIN)
    db.rollback()
    assert db.get(Department,parent['id']).is_active


def test_outlet_activity_is_counted_once_and_uses_fb_report_layout(db):
    parent,child=outlet(db)
    defs=[(20,'400-100-101','Food Revenue','REVENUE'),(21,'500-100-100','Food Cost','EXPENSE'),(22,'600-100-100','Salary','EXPENSE')]
    for aid,code,name,kind in defs:db.add(ChartOfAccount(id=aid,account_number=code,account_name=name,account_type=kind,normal_balance='CREDIT' if kind=='REVENUE' else 'DEBIT',is_posting=True))
    j=JournalEntry(journal_number='OUTLET',posting_date=date(2026,1,5),status='POSTED',reference_type='MANUAL',reference_id=0,business_unit_id=1,location_id=1,department_id=child['id'])
    j.lines=[JournalLine(account_id=20,debit=0,credit=1000),JournalLine(account_id=21,debit=200,credit=0),JournalLine(account_id=22,debit=100,credit=0)]
    db.add(j);db.commit()
    report=deliver(FinancialReportingService(db),as_of_date=date(2026,1,31),report_scope='HOTEL',location_id=1)
    current=lambda r,key:next(v['periods']['YTD']['current'] for v in r['presentation_rows'] if v['key']==key)
    assert current(report,'NOP')==700
    assert sum(current(r,'NOP') for r in report['group_reports'])==700
    restaurant=next(r for r in report['group_reports'] if r['department_id']==child['id'])
    assert restaurant['department_name']=='Food and Beverage / Restaurant'
    assert current(restaurant,'OPERATING_PAYROLL')==100
    verify_formulas(workbook_sheets(report))
    assert db.query(JournalEntry).count()==1


def test_missing_optional_migration_keeps_department_reads_available(db):
    db.execute(text('DROP TABLE department_outlets'));db.commit()
    db.info.clear()
    assert labels(db)=={}
    assert list_departments(db=db,user=ADMIN)

from datetime import date
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.api.v1.financial_reports import executive_overview
from test_organization_and_asset_delivery import db, ADMIN
from test_asset_filters_balance_export import setup_accounts, posting


def test_owner_read_permission_returns_only_scoped_headlines(db):
    setup_accounts(db);posting(db,'OWNER-LOCATION',10,1);posting(db,'OTHER-LOCATION',999,3,2,2)
    owner=SimpleNamespace(id=2,roles=[SimpleNamespace(name='OWNER',permissions=[SimpleNamespace(code='reports.view')])],default_location_id=1,location_id=1,default_department_id=None)
    result=executive_overview(as_of_date=date(2026,10,14),db=db,user=owner)
    assert result['scope']['location_id']==1
    assert result['balance_sheet']['section_totals']['ASSETS']['YTD']['current']=='10.00'
    assert {row['key'] for row in result['profit_loss']['presentation_rows']}=={'REVENUE','BEBAN','GOP','NOP'}
    assert all(set(row)=={'key','label','periods'} for row in result['profit_loss']['presentation_rows'])
    assert set(result['balance_sheet'])=={'section_totals'}
    with pytest.raises(HTTPException):executive_overview(as_of_date=date(2026,10,14),location_id=2,db=db,user=owner)
    owner.roles[0].permissions=[]
    with pytest.raises(HTTPException) as error:executive_overview(as_of_date=date(2026,10,14),db=db,user=owner)
    assert error.value.status_code==403

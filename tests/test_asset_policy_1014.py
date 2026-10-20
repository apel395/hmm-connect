from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.models.fixed_asset import FixedAsset, FixedAssetCategory, FixedAssetDepreciationRun, FixedAssetDepreciationSchedule
from app.models.chart_of_account import ChartOfAccount
from app.models.fiscal_period import FiscalPeriod
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.general_ledger_report import build_ledger_query
from app.models.general_ledger import GeneralLedger
from app.schemas.fixed_asset import CategoryInput, CapitalizeInput, TransferInput, DisposalInput
from app.schemas.amortization import AmortizationCreate
from app.api.v1 import amortizations
from app.services.fixed_asset_service import FixedAssetService, DepreciationRunService
from test_organization_and_asset_delivery import db, ADMIN

@pytest.fixture
def asset(db):
    db.add_all([
        ChartOfAccount(id=4,account_number='100-600-104',account_name='Equipment',account_type='ASSET',normal_balance='DEBIT',is_posting=True),
        ChartOfAccount(id=5,account_number='100-600-100',account_name='Land',account_type='ASSET',normal_balance='DEBIT',is_posting=True),
        ChartOfAccount(id=6,account_number='100-100-100',account_name='Bank',account_type='ASSET',account_subtype='BANK',normal_balance='DEBIT',is_posting=True),
    ])
    cat=FixedAssetCategory(code='EQ',name='Equipment',is_depreciable=True,asset_account_id=4,default_useful_life_months=48,accumulated_depreciation_account_id=3,depreciation_expense_account_id=2)
    db.add(cat);db.flush()
    item=FixedAsset(asset_number='FA-TEST',asset_name='Equipment',asset_category_id=cat.id,acquisition_date=date(2026,10,1),acquisition_cost=Decimal(100),quantity=2,accumulated_depreciation=0,net_book_value=100,residual_value=0,useful_life_months=48,depreciation_method='STRAIGHT_LINE',asset_account_id=4,accumulated_depreciation_account_id=3,depreciation_expense_account_id=2,disposal_loss_account_id=2,business_unit_id=1,location_id=1,department_id=1,created_by_id=1,status='DRAFT')
    db.add(item)
    import calendar
    for index in range(1,48):
        year, month = 2026 + (9+index)//12, (9+index)%12+1
        db.add(FiscalPeriod(fiscal_year=year,fiscal_month=month,period_name=f'{year}-{month}',start_date=date(year,month,1),end_date=date(year,month,calendar.monthrange(year,month)[1]),is_open=True,is_closed=False,allow_backdated_entries=True))
    db.commit();return item


def test_non_depreciable_land_activates_without_fake_life_or_journal(db,asset):
    svc=FixedAssetService(db)
    cat=svc.create_category(CategoryInput(code='LAND',name='Land',asset_account_id=5,is_depreciable=False))
    asset.asset_account_id=5;svc.assign_category(asset,cat.id)
    svc.capitalize(asset,CapitalizeInput(capitalization_date=date(2026,10,1)),ADMIN);db.commit()
    assert asset.status=='ACTIVE' and asset.depreciation_start_date is None
    assert not asset.schedules and asset.net_book_value==100
    assert db.query(JournalEntry).count()==db.query(GeneralLedger).count()==0
    with pytest.raises(HTTPException):svc.create_category(CategoryInput(code='BAD',name='Land',asset_account_id=5,default_useful_life_months=12,accumulated_depreciation_account_id=3,depreciation_expense_account_id=2))


def activate(db,asset):
    svc=FixedAssetService(db);svc.capitalize(asset,CapitalizeInput(capitalization_date=date(2026,10,1),depreciation_start_date=date(2026,10,1)),ADMIN);db.commit();return svc


def test_depreciation_final_month_rounding_post_reverse_and_repost(db,asset):
    activate(db,asset)
    assert [x.depreciation_amount for x in db.query(FixedAssetDepreciationSchedule).order_by(FixedAssetDepreciationSchedule.period_start)]==[Decimal('2.08')]*47+[Decimal('2.24')]
    svc=DepreciationRunService(db);runs=[]
    for index in range(48):
        year, month = 2026 + (9+index)//12, (9+index)%12+1
        run=FixedAssetDepreciationRun(run_number=f'RUN-{index}',period_year=year,period_month=month,business_unit_id=1,location_id=1,created_by_id=1,status='DRAFT');db.add(run);db.flush();svc.calculate(run);svc.post(run,ADMIN);db.commit();runs.append(run)
    assert asset.net_book_value==0 and asset.accumulated_depreciation==100 and asset.status=='FULLY_DEPRECIATED'
    with pytest.raises(HTTPException):svc.unpost(runs[0],ADMIN)
    latest=svc.unpost(runs[-1],ADMIN);db.commit()
    assert latest.status=='VOID' and asset.net_book_value==Decimal('2.24')
    svc.calculate(runs[-1]);svc.post(runs[-1],ADMIN);db.commit()
    assert asset.net_book_value==0 and db.query(JournalEntry).filter(JournalEntry.status=='POSTED').count()==48
    assert sum(r.debit-r.credit for r in db.query(GeneralLedger))==0


def test_run_cannot_skip_earlier_month(db,asset):
    activate(db,asset);svc=DepreciationRunService(db)
    run=FixedAssetDepreciationRun(run_number='LATE',period_year=2026,period_month=11,business_unit_id=1,location_id=1,created_by_id=1,status='DRAFT');db.add(run);db.flush();svc.calculate(run)
    with pytest.raises(HTTPException):svc.post(run,ADMIN)
    assert not db.query(JournalEntry).count()


def test_transfer_reclassifies_gross_cost_and_accumulated_by_dimensions(db,asset):
    svc=activate(db,asset);asset.accumulated_depreciation=20;asset.net_book_value=80
    svc.transfer(asset,TransferInput(movement_date=date(2026,10,15),business_unit_id=2,location_id=2,department_id=3),ADMIN);db.commit()
    rows=db.query(JournalLine).order_by(JournalLine.id).all()
    assert [(r.account_id,r.debit,r.credit,r.location_id) for r in rows]==[(4,100,0,2),(4,0,100,1),(3,20,0,1),(3,0,20,2)]
    assert len(build_ledger_query(db,location_id=2).all())==2
    assert asset.quantity==2 and asset.net_book_value==80
    assert asset.movements[-1].journal_entry_id is not None


def test_disposal_zeros_book_value_without_erasing_acquisition(db,asset):
    svc=activate(db,asset)
    result=svc.dispose(asset,DisposalInput(disposal_date=date(2026,10,15),disposal_proceeds=50,cash_account_id=6),ADMIN);db.commit()
    assert asset.status=='DISPOSED' and asset.net_book_value==0 and asset.acquisition_cost==100
    assert result['gain_loss']==-50
    assert sum(r.debit-r.credit for r in db.query(GeneralLedger))==0
    assert all(r.status=='SKIPPED' for r in asset.schedules)


def test_amortization_final_month_stale_request_and_reversal(db,asset):
    created=amortizations.create_amortization(AmortizationCreate(name='Prepaid',start_date=date(2026,10,1),original_cost=100,useful_life_months=48,business_unit_id=1,location_id=1,department_id=1,asset_account_id=1,accumulated_amortization_account_id=1,amortization_expense_account_id=2),db,ADMIN)
    ident=created['id'];amounts=[]
    for counter in range(48):amounts.append(amortizations.post_next_amortization(ident,db,ADMIN,expected_months_posted=counter)['posted_amount'])
    assert amounts==[Decimal('2.08')]*47+[Decimal('2.24')]
    with pytest.raises(HTTPException):amortizations.post_next_amortization(ident,db,ADMIN,expected_months_posted=47)
    reverted=amortizations.unpost_last_amortization(ident,db,ADMIN,expected_months_posted=48)
    assert reverted['amortization']['net_book_value']==Decimal('2.24')
    amortizations.post_next_amortization(ident,db,ADMIN,expected_months_posted=47)
    assert db.query(JournalEntry).filter(JournalEntry.status=='POSTED').count()==48
    assert sum(r.debit-r.credit for r in db.query(GeneralLedger))==0


def test_regenerated_schedule_keeps_posted_month_and_residual(db,asset):
    asset.residual_value=20;svc=activate(db,asset)
    run=FixedAssetDepreciationRun(run_number='RESIDUAL',period_year=2026,period_month=10,business_unit_id=1,location_id=1,created_by_id=1,status='DRAFT');db.add(run);db.flush()
    runs=DepreciationRunService(db);runs.calculate(run);entry=runs.post(run,ADMIN);db.commit()
    svc.generate_schedule(asset);db.commit()
    rows=db.query(FixedAssetDepreciationSchedule).order_by(FixedAssetDepreciationSchedule.period_start).all()
    assert len(rows)==48 and rows[0].journal_entry_id==entry.id and rows[0].status=='POSTED'
    assert sum(r.depreciation_amount for r in rows)==80 and rows[-1].closing_book_value==20


def test_closed_period_blocks_latest_amortization_reversal_without_mutation(db,asset):
    created=amortizations.create_amortization(AmortizationCreate(name='Prepaid',start_date=date(2026,10,1),original_cost=100,useful_life_months=48,business_unit_id=1,location_id=1,department_id=1,asset_account_id=1,accumulated_amortization_account_id=1,amortization_expense_account_id=2),db,ADMIN)
    amortizations.post_next_amortization(created['id'],db,ADMIN,expected_months_posted=0)
    period=db.query(FiscalPeriod).filter_by(fiscal_year=2026,fiscal_month=10).one();period.is_open=False;period.is_closed=True;db.commit()
    with pytest.raises(HTTPException):amortizations.unpost_last_amortization(created['id'],db,ADMIN,expected_months_posted=1)
    db.rollback()
    assert db.query(JournalEntry).one().status=='POSTED' and db.query(GeneralLedger).count()==2

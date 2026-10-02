import calendar
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
from app.models.chart_of_account import ChartOfAccount
from app.models.fixed_asset import FixedAsset, FixedAssetCategory, FixedAssetDepreciationSchedule, FixedAssetMovement, FixedAssetDepreciationRun
from app.models.goods_receipt import GoodsReceipt
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.document_number import next_document_number
from app.services.organization_dimensions import validate_dimensions

ZERO = Decimal("0.00")
CENT = Decimal("0.01")

def month_start(value: date) -> date:
    return value.replace(day=1)

def next_month(value: date) -> date:
    return date(value.year + (value.month == 12), 1 if value.month == 12 else value.month + 1, 1)

def month_end(value: date) -> date:
    return value.replace(day=calendar.monthrange(value.year, value.month)[1])

class FixedAssetService:
    def __init__(self, db: Session): self.db = db

    def account(self, account_id, account_type, label, credit_normal=False):
        account = self.db.get(ChartOfAccount, account_id)
        allowed = (account_type,) if isinstance(account_type, str) else account_type
        if not account or not account.is_active or not account.is_posting or account.account_type not in allowed:
            raise HTTPException(422, f"{label} must be an active posting {'/'.join(allowed)} account")
        if credit_normal and account.normal_balance != "CREDIT":
            raise HTTPException(422, f"{label} must have CREDIT normal balance")
        return account

    def validate_accounts(self, value):
        self.account(value.asset_account_id, "ASSET", "Asset account")
        self.account(value.accumulated_depreciation_account_id, "ASSET", "Accumulated depreciation", True)
        self.account(value.depreciation_expense_account_id, "EXPENSE", "Depreciation expense")
        if value.disposal_gain_account_id: self.account(value.disposal_gain_account_id, ("INCOME","REVENUE"), "Disposal gain")
        if value.disposal_loss_account_id: self.account(value.disposal_loss_account_id, "EXPENSE", "Disposal loss")

    def validate_asset(self, value):
        category = self.db.get(FixedAssetCategory, value.asset_category_id)
        if not category or not category.is_active: raise HTTPException(422, "Active asset category is required")
        if value.depreciation_method != "STRAIGHT_LINE": raise HTTPException(422, "Only STRAIGHT_LINE depreciation is supported")
        if value.residual_value >= value.acquisition_cost: raise HTTPException(422, "Residual value must be below acquisition cost")
        validate_dimensions(self.db, value.business_unit_id, value.location_id, value.department_id, required=True)
        self.validate_accounts(value)

    def create_category(self, value):
        self.validate_accounts(value)
        category = FixedAssetCategory(**value.model_dump())
        category.code = category.code.strip().upper()
        self.db.add(category); self.db.flush(); return category

    def create_asset(self, value, user):
        self.validate_asset(value)
        if value.purchase_invoice_id:
            duplicate = self.db.query(FixedAsset).filter(FixedAsset.purchase_invoice_id == value.purchase_invoice_id, FixedAsset.external_reference == value.external_reference, FixedAsset.status != "INACTIVE").first()
            if duplicate: raise HTTPException(409, "This invoice source has already been capitalized or registered")
        asset = FixedAsset(asset_number=next_document_number(self.db, "FA"), accumulated_depreciation=ZERO, net_book_value=value.acquisition_cost, created_by_id=user.id, **value.model_dump())
        self.db.add(asset); self.db.flush()
        self.db.add(FixedAssetMovement(fixed_asset_id=asset.id, movement_type="ACQUISITION", to_business_unit_id=asset.business_unit_id, to_location_id=asset.location_id, to_department_id=asset.department_id, movement_date=asset.acquisition_date, reference_number=asset.external_reference, created_by_id=user.id))
        return asset

    def get(self, asset_id):
        asset = self.db.query(FixedAsset).options(joinedload(FixedAsset.category), joinedload(FixedAsset.schedules), joinedload(FixedAsset.movements)).filter(FixedAsset.id == asset_id).first()
        if not asset: raise HTTPException(404, "Fixed asset not found")
        return asset

    @staticmethod
    def actions(asset):
        return {"can_edit": asset.status == "DRAFT", "can_capitalize": asset.status == "DRAFT", "can_generate_schedule": asset.status in ("ACTIVE", "FULLY_DEPRECIATED"), "can_transfer": asset.status in ("ACTIVE", "FULLY_DEPRECIATED"), "can_dispose": asset.status in ("ACTIVE", "FULLY_DEPRECIATED"), "can_write_off": asset.status in ("ACTIVE", "FULLY_DEPRECIATED"), "can_print": True}

    def serialize(self, asset):
        return {"id":asset.id,"asset_number":asset.asset_number,"asset_name":asset.asset_name,"category_id":asset.asset_category_id,"category":asset.category.name,"description":asset.description,"serial_number":asset.serial_number,"barcode":asset.barcode,"acquisition_date":asset.acquisition_date,"capitalization_date":asset.capitalization_date,"acquisition_cost":asset.acquisition_cost,"residual_value":asset.residual_value,"useful_life_months":asset.useful_life_months,"depreciation_method":asset.depreciation_method,"depreciation_start_date":asset.depreciation_start_date,"accumulated_depreciation":asset.accumulated_depreciation,"net_book_value":asset.net_book_value,"status":asset.status,"business_unit_id":asset.business_unit_id,"location_id":asset.location_id,"department_id":asset.department_id,"source_type":asset.source_type,"external_reference":asset.external_reference,"notes":asset.notes,"allowed_actions":self.actions(asset),"schedules":[{"id":s.id,"period":f"{s.period_year}-{s.period_month:02d}","opening_book_value":s.opening_book_value,"depreciation_amount":s.depreciation_amount,"accumulated_depreciation":s.accumulated_depreciation,"closing_book_value":s.closing_book_value,"status":s.status,"journal_entry_id":s.journal_entry_id} for s in sorted(asset.schedules,key=lambda x:(x.period_year,x.period_month))],"movements":[{"id":m.id,"movement_type":m.movement_type,"movement_date":m.movement_date,"from_business_unit_id":m.from_business_unit_id,"to_business_unit_id":m.to_business_unit_id,"from_location_id":m.from_location_id,"to_location_id":m.to_location_id,"notes":m.notes} for m in asset.movements]}

    def capitalize(self, asset, value, user):
        if asset.status != "DRAFT": raise HTTPException(409, "Only draft assets can be capitalized")
        if value.depreciation_start_date < value.capitalization_date: raise HTTPException(422, "Depreciation start cannot precede capitalization")
        if value.create_journal:
            if asset.goods_receipt_id:
                receipt = self.db.get(GoodsReceipt, asset.goods_receipt_id)
                if receipt and receipt.status == "POSTED":
                    raise HTTPException(409, "Receiving has already posted the asset acquisition; capitalize without creating another journal")
            if not value.offset_account_id: raise HTTPException(422, "Offset account is required")
        asset.capitalization_date=value.capitalization_date; asset.depreciation_start_date=value.depreciation_start_date; asset.status="ACTIVE"
        if value.create_journal:
            self._journal(value.capitalization_date,"FIXED_ASSET_CAPITALIZATION",asset.id,asset.asset_number,[(asset.asset_account_id,asset.acquisition_cost,ZERO),(value.offset_account_id,ZERO,asset.acquisition_cost)],asset,user)
        self.generate_schedule(asset)
        return asset

    def generate_schedule(self, asset):
        if asset.status not in ("ACTIVE", "FULLY_DEPRECIATED"): raise HTTPException(409, "Asset must be active")
        if asset.net_book_value <= asset.residual_value: return asset.schedules
        start = month_start(asset.depreciation_start_date)
        if asset.depreciation_start_date.day != 1: start = next_month(start)
        posted = {(s.period_year,s.period_month) for s in asset.schedules if s.status == "POSTED"}
        self.db.query(FixedAssetDepreciationSchedule).filter(FixedAssetDepreciationSchedule.fixed_asset_id==asset.id,FixedAssetDepreciationSchedule.status.in_(["PLANNED","GENERATED"])).delete(synchronize_session=False)
        depreciable = Decimal(asset.acquisition_cost)-Decimal(asset.residual_value)
        monthly = (depreciable/asset.useful_life_months).quantize(CENT, rounding=ROUND_HALF_UP)
        accumulated = Decimal(asset.accumulated_depreciation); opening = Decimal(asset.net_book_value); current=start
        created=[]
        for _ in range(asset.useful_life_months):
            if (current.year,current.month) in posted: current=next_month(current); continue
            remaining=opening-Decimal(asset.residual_value)
            if remaining <= ZERO: break
            amount=min(monthly,remaining)
            schedule=FixedAssetDepreciationSchedule(fixed_asset_id=asset.id,period_year=current.year,period_month=current.month,period_start=current,period_end=month_end(current),opening_book_value=opening,depreciation_amount=amount,accumulated_depreciation=accumulated+amount,closing_book_value=opening-amount,status="PLANNED")
            self.db.add(schedule);created.append(schedule);opening-=amount;accumulated+=amount;current=next_month(current)
        self.db.flush(); return created

    def transfer(self, asset, value, user):
        if asset.status not in ("ACTIVE","FULLY_DEPRECIATED"): raise HTTPException(409,"Asset cannot be transferred")
        validate_dimensions(self.db,value.business_unit_id,value.location_id,value.department_id,required=True)
        movement=FixedAssetMovement(fixed_asset_id=asset.id,movement_type="TRANSFER",from_business_unit_id=asset.business_unit_id,to_business_unit_id=value.business_unit_id,from_location_id=asset.location_id,to_location_id=value.location_id,from_department_id=asset.department_id,to_department_id=value.department_id,movement_date=value.movement_date,reference_number=value.reference_number,notes=value.notes,created_by_id=user.id)
        self.db.add(movement);asset.business_unit_id=value.business_unit_id;asset.location_id=value.location_id;asset.department_id=value.department_id;asset.custodian_user_id=value.custodian_user_id;return asset

    def _journal(self, posting_date, ref_type, ref_id, ref_number, lines, asset, user):
        if self.db.query(JournalEntry).filter(JournalEntry.reference_type==ref_type,JournalEntry.reference_id==ref_id,JournalEntry.status=="POSTED").first(): raise HTTPException(409,"Journal already posted")
        debit=sum((x[1] for x in lines),ZERO);credit=sum((x[2] for x in lines),ZERO)
        if debit!=credit:raise HTTPException(422,"Journal is not balanced")
        entry=JournalEntry(journal_number=next_document_number(self.db,"JV",digits=8),posting_date=posting_date,status="POSTED",document_type="FIXED_ASSET",document_number=ref_number,reference_type=ref_type,reference_id=ref_id,description=f"{ref_type} {ref_number}",created_by_id=user.id,posted_by_id=user.id,business_unit_id=asset.business_unit_id,location_id=asset.location_id,department_id=asset.department_id,fiscal_year=posting_date.year,fiscal_period=posting_date.month)
        self.db.add(entry);self.db.flush()
        for number,(account_id,d,c) in enumerate(lines,1): self.db.add(JournalLine(journal_entry_id=entry.id,line_number=number,account_id=account_id,debit=d,credit=c,description=entry.description,business_unit_id=asset.business_unit_id,location_id=asset.location_id,department_id=asset.department_id))
        self.db.flush();return entry

    def dispose(self, asset, value, user, write_off=False):
        if asset.status not in ("ACTIVE","FULLY_DEPRECIATED"): raise HTTPException(409,"Asset cannot be disposed")
        proceeds=ZERO if write_off else Decimal(value.disposal_proceeds);book=Decimal(asset.net_book_value);gain=proceeds-book
        lines=[]
        if proceeds:
            if not value.cash_account_id:raise HTTPException(422,"Cash account is required when disposal proceeds exist")
            self.account(value.cash_account_id,"ASSET","Cash account")
            lines.append((value.cash_account_id,proceeds,ZERO))
        lines.append((asset.accumulated_depreciation_account_id,Decimal(asset.accumulated_depreciation),ZERO))
        if gain<0:
            if not asset.disposal_loss_account_id:raise HTTPException(422,"Disposal loss account is required")
            lines.append((asset.disposal_loss_account_id,-gain,ZERO))
        elif gain>0:
            if not asset.disposal_gain_account_id:raise HTTPException(422,"Disposal gain account is required")
            lines.append((asset.disposal_gain_account_id,ZERO,gain))
        lines.append((asset.asset_account_id,ZERO,Decimal(asset.acquisition_cost)))
        when=value.write_off_date if write_off else value.disposal_date;kind="FIXED_ASSET_WRITE_OFF" if write_off else "FIXED_ASSET_DISPOSAL"
        entry=self._journal(when,kind,asset.id,asset.asset_number,lines,asset,user)
        self.db.query(FixedAssetDepreciationSchedule).filter(FixedAssetDepreciationSchedule.fixed_asset_id==asset.id,FixedAssetDepreciationSchedule.status.in_(["PLANNED","GENERATED"])).update({"status":"SKIPPED"},synchronize_session=False)
        asset.status="WRITTEN_OFF" if write_off else "DISPOSED";asset.written_off_at=datetime.now(timezone.utc) if write_off else None;asset.disposed_at=None if write_off else datetime.now(timezone.utc)
        self.db.add(FixedAssetMovement(fixed_asset_id=asset.id,movement_type="WRITE_OFF" if write_off else "DISPOSAL",from_business_unit_id=asset.business_unit_id,from_location_id=asset.location_id,from_department_id=asset.department_id,movement_date=when,reference_number=entry.journal_number,notes=value.notes,created_by_id=user.id))
        return {"asset":asset,"journal":entry,"gain_loss":gain}

class DepreciationRunService:
    def __init__(self,db):self.db=db;self.assets=FixedAssetService(db)
    def calculate(self,run):
        if run.status not in ("DRAFT","CALCULATED"):raise HTTPException(409,"Run cannot be calculated")
        q=self.db.query(FixedAssetDepreciationSchedule).join(FixedAsset).filter(FixedAssetDepreciationSchedule.period_year==run.period_year,FixedAssetDepreciationSchedule.period_month==run.period_month,FixedAssetDepreciationSchedule.status.in_(["PLANNED","GENERATED"]),FixedAsset.status=="ACTIVE")
        if run.business_unit_id:q=q.filter(FixedAsset.business_unit_id==run.business_unit_id)
        if run.location_id:q=q.filter(FixedAsset.location_id==run.location_id)
        rows=q.all();run.asset_count=len(rows);run.total_depreciation=sum((Decimal(x.depreciation_amount) for x in rows),ZERO);run.status="CALCULATED";return rows
    def post(self,run,user):
        if run.status!="CALCULATED":raise HTTPException(409,"Run must be calculated")
        rows=self.calculate_rows(run);grouped=defaultdict(lambda:[ZERO,ZERO,None])
        for s in rows:
            a=s.asset;key=(a.depreciation_expense_account_id,a.accumulated_depreciation_account_id,a.business_unit_id,a.location_id,a.department_id);grouped[key][0]+=Decimal(s.depreciation_amount);grouped[key][1]+=Decimal(s.depreciation_amount);grouped[key][2]=a
        lines=[]
        for (expense,accumulated,*_),amounts in grouped.items():lines.extend([(expense,amounts[0],ZERO),(accumulated,ZERO,amounts[1])])
        representative=rows[0].asset if rows else None
        if not representative:raise HTTPException(409,"No depreciation schedules for this run")
        posting=month_end(date(run.period_year,run.period_month,1));entry=self.assets._journal(posting,"FIXED_ASSET_DEPRECIATION",run.id,run.run_number,lines,representative,user)
        now=datetime.now(timezone.utc)
        for s in rows:s.status="POSTED";s.journal_entry_id=entry.id;s.posted_at=now;s.asset.accumulated_depreciation=Decimal(s.asset.accumulated_depreciation)+Decimal(s.depreciation_amount);s.asset.net_book_value=Decimal(s.asset.acquisition_cost)-Decimal(s.asset.accumulated_depreciation);s.asset.status="FULLY_DEPRECIATED" if s.asset.net_book_value<=s.asset.residual_value else "ACTIVE"
        run.status="POSTED";run.journal_entry_id=entry.id;run.posted_by_id=user.id;run.posted_at=now;return entry
    def calculate_rows(self,run):
        q=self.db.query(FixedAssetDepreciationSchedule).options(joinedload(FixedAssetDepreciationSchedule.asset)).join(FixedAsset).filter(FixedAssetDepreciationSchedule.period_year==run.period_year,FixedAssetDepreciationSchedule.period_month==run.period_month,FixedAssetDepreciationSchedule.status.in_(["PLANNED","GENERATED"]),FixedAsset.status=="ACTIVE")
        if run.business_unit_id:q=q.filter(FixedAsset.business_unit_id==run.business_unit_id)
        if run.location_id:q=q.filter(FixedAsset.location_id==run.location_id)
        return q.all()

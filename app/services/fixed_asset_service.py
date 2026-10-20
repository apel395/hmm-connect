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
from app.services.asset_item_master import link_asset_item
from app.services.organization_dimensions import validate_dimensions
from app.services.asset_useful_life import validate_useful_life

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
        account = self.account(value.asset_account_id, "ASSET", "Asset account")
        if account.account_number in ('100-900-101', '100-900-102', '100-900-103'):
            raise HTTPException(422, 'MMH utensils policy excludes chinaware, silverware and glassware from fixed assets')
        if not account.account_number.startswith(("100-600-", "100-900-")) or account.normal_balance != "DEBIT":
            raise HTTPException(422, "Select a debit fixed asset or operating-equipment account")
        depreciable = getattr(value, "is_depreciable", value.depreciation_method != "NONE" if hasattr(value, "depreciation_method") else True)
        if account.account_number == "100-600-100" and depreciable:
            raise HTTPException(422, "Land must use a non-depreciable category")
        if depreciable:
            life = getattr(value, "default_useful_life_months", getattr(value, "useful_life_months", None))
            if not life: raise HTTPException(422, "Depreciable assets require useful life")
            validate_useful_life(life)
            self.account(value.accumulated_depreciation_account_id, "ASSET", "Accumulated depreciation", True)
            expense = self.account(value.depreciation_expense_account_id, "EXPENSE", "Depreciation expense")
            if expense.normal_balance != "DEBIT": raise HTTPException(422, "Depreciation expense must be debit balance")
        elif getattr(value,"default_useful_life_months",getattr(value,"useful_life_months",None)) is not None or value.accumulated_depreciation_account_id or value.depreciation_expense_account_id:
            raise HTTPException(422, "Non-depreciable assets do not use depreciation posting accounts")
        if value.disposal_gain_account_id: self.account(value.disposal_gain_account_id, ("INCOME","REVENUE"), "Disposal gain")
        if value.disposal_loss_account_id: self.account(value.disposal_loss_account_id, "EXPENSE", "Disposal loss")

    def validate_asset(self, value):
        category = self.db.get(FixedAssetCategory, value.asset_category_id)
        if not category or not category.is_active: raise HTTPException(422, "Active asset category is required")
        if value.depreciation_method not in ("STRAIGHT_LINE", "NONE"): raise HTTPException(422, "Select Straight Line or Non-depreciable")
        if category.is_depreciable != (value.depreciation_method != "NONE"):
            raise HTTPException(422, "Asset depreciation method must match its category")
        if value.accumulated_depreciation > value.acquisition_cost - value.residual_value: raise HTTPException(422,"Opening accumulated depreciation exceeds depreciable cost")
        if value.depreciation_method == "NONE" and value.accumulated_depreciation: raise HTTPException(422,"Non-depreciable asset cannot have accumulated depreciation")
        if value.residual_value >= value.acquisition_cost: raise HTTPException(422, "Residual value must be below acquisition cost")
        validate_dimensions(self.db, value.business_unit_id, value.location_id, value.department_id, required=True)
        if category.asset_account_id != value.asset_account_id:
            raise HTTPException(422, "Category must match the asset account")
        self.validate_accounts(value)

    def create_category(self, value):
        self.validate_accounts(value)
        code = value.code.strip().upper()
        if self.db.query(FixedAssetCategory).filter(FixedAssetCategory.code == code).first():
            raise HTTPException(409, "Asset category code already exists")
        category = FixedAssetCategory(**value.model_dump())
        category.code = category.code.strip().upper()
        self.db.add(category); self.db.flush(); return category

    def create_asset(self, value, user):
        self.validate_asset(value)
        if value.purchase_invoice_id:
            duplicate = self.db.query(FixedAsset).filter(FixedAsset.purchase_invoice_id == value.purchase_invoice_id, FixedAsset.external_reference == value.external_reference, FixedAsset.status != "INACTIVE").first()
            if duplicate: raise HTTPException(409, "This invoice source has already been capitalized or registered")
        asset = FixedAsset(asset_number=next_document_number(self.db, "FA"), net_book_value=value.acquisition_cost-value.accumulated_depreciation, created_by_id=user.id, **value.model_dump())
        self.db.add(asset); self.db.flush()
        link_asset_item(self.db, asset, user=user)
        self.db.add(FixedAssetMovement(fixed_asset_id=asset.id, movement_type="ACQUISITION", to_business_unit_id=asset.business_unit_id, to_location_id=asset.location_id, to_department_id=asset.department_id, movement_date=asset.acquisition_date, reference_number=asset.external_reference, created_by_id=user.id))
        return asset

    def complete_registration(self, asset, value, user):
        if asset.status != "PENDING_REGISTRATION" or asset.source_type != "ITEM_MASTER":
            raise HTTPException(409, "Only Item Master registrations can be completed here")
        if asset.business_unit_id and value.business_unit_id != asset.business_unit_id:
            raise HTTPException(422, "Keep the registered catalogue business unit")
        if value.asset_account_id != asset.asset_account_id or value.product_id != asset.product_id:
            raise HTTPException(422, "Keep the registered Item Master and asset account")
        if value.purchase_invoice_id or value.goods_receipt_id:
            raise HTTPException(422, "Use the source document registration flow for a purchase")
        self.validate_asset(value)
        for key, entry in value.model_dump().items(): setattr(asset, key, entry)
        asset.status = "DRAFT"
        asset.source_type = "ITEM_MASTER"
        asset.created_by_id = user.id
        asset.net_book_value = value.acquisition_cost-value.accumulated_depreciation
        link_asset_item(self.db, asset, user=user)
        self.db.add(FixedAssetMovement(fixed_asset_id=asset.id, movement_type="ACQUISITION", to_business_unit_id=asset.business_unit_id, to_location_id=asset.location_id, to_department_id=asset.department_id, movement_date=asset.acquisition_date, reference_number=asset.external_reference, created_by_id=user.id))
        return asset

    def assign_category(self, asset, category_id: int):
        if asset.status not in ("PENDING_SETUP", "DRAFT"):
            raise HTTPException(409, "Only pending or draft assets can change category")
        category = self.db.get(FixedAssetCategory, category_id)
        if not category or not category.is_active:
            raise HTTPException(422, "Active asset category is required")
        if category.asset_account_id != asset.asset_account_id:
            raise HTTPException(422, "Asset category must use the already posted asset COA")
        self.validate_accounts(category)
        asset.asset_category_id = category.id
        asset.useful_life_months = category.default_useful_life_months
        asset.depreciation_method = "STRAIGHT_LINE" if category.is_depreciable else "NONE"
        asset.residual_value = (
            Decimal(asset.acquisition_cost) * Decimal(category.default_residual_percentage or 0) / Decimal("100")
        ).quantize(Decimal("0.01"))
        if asset.residual_value >= asset.acquisition_cost:
            raise HTTPException(422, "Residual value must be below acquisition cost")
        asset.accumulated_depreciation_account_id = category.accumulated_depreciation_account_id
        asset.depreciation_expense_account_id = category.depreciation_expense_account_id
        asset.disposal_gain_account_id = category.disposal_gain_account_id
        asset.disposal_loss_account_id = category.disposal_loss_account_id
        asset.status = "DRAFT"
        return asset

    def get(self, asset_id, lock=False):
        query = self.db.query(FixedAsset).options(joinedload(FixedAsset.category), joinedload(FixedAsset.schedules), joinedload(FixedAsset.movements)).filter(FixedAsset.id == asset_id)
        if lock: query = query.with_for_update(of=FixedAsset)
        asset = query.first()
        if not asset: raise HTTPException(404, "Fixed asset not found")
        return asset

    @staticmethod
    def actions(asset):
        return {"can_complete_registration": asset.status == "PENDING_REGISTRATION", "can_edit": asset.status in ("DRAFT", "PENDING_SETUP"), "can_capitalize": asset.status == "DRAFT" and bool(asset.asset_category_id and (asset.depreciation_method == "NONE" or (asset.useful_life_months and asset.accumulated_depreciation_account_id and asset.depreciation_expense_account_id))), "can_generate_schedule": asset.status in ("ACTIVE", "FULLY_DEPRECIATED") and asset.depreciation_method != "NONE", "can_transfer": asset.status in ("ACTIVE", "FULLY_DEPRECIATED"), "can_dispose": asset.status in ("ACTIVE", "FULLY_DEPRECIATED"), "can_write_off": asset.status in ("ACTIVE", "FULLY_DEPRECIATED"), "can_print": True}

    def serialize(self, asset):
        return {"id":asset.id,"asset_number":asset.asset_number,"asset_name":asset.asset_name,"product_id":asset.product_id,"product_code":asset.product.code if asset.product else None,"product_name":asset.product.name if asset.product else None,"category_id":asset.asset_category_id,"category":asset.category.name if asset.category else None,"source_invoice_line_id":asset.source_invoice_line_id,"purchase_invoice_id":asset.purchase_invoice_id,"goods_receipt_id":asset.goods_receipt_id,"asset_account_id":asset.asset_account_id,"description":asset.description,"serial_number":asset.serial_number,"barcode":asset.barcode,"acquisition_date":asset.acquisition_date,"capitalization_date":asset.capitalization_date,"acquisition_cost":asset.acquisition_cost,"quantity":asset.quantity,"residual_value":asset.residual_value,"useful_life_months":asset.useful_life_months,"depreciation_method":asset.depreciation_method,"depreciation_start_date":asset.depreciation_start_date,"accumulated_depreciation":asset.accumulated_depreciation,"net_book_value":asset.net_book_value,"status":asset.status,"business_unit_id":asset.business_unit_id,"location_id":asset.location_id,"department_id":asset.department_id,"source_type":asset.source_type,"external_reference":asset.external_reference,"notes":asset.notes,"allowed_actions":self.actions(asset),"schedules":[{"id":s.id,"period":f"{s.period_year}-{s.period_month:02d}","opening_book_value":s.opening_book_value,"depreciation_amount":s.depreciation_amount,"accumulated_depreciation":s.accumulated_depreciation,"closing_book_value":s.closing_book_value,"status":s.status,"journal_entry_id":s.journal_entry_id} for s in sorted(asset.schedules,key=lambda x:(x.period_year,x.period_month))],"movements":[{"id":m.id,"movement_type":m.movement_type,"movement_date":m.movement_date,"from_business_unit_id":m.from_business_unit_id,"to_business_unit_id":m.to_business_unit_id,"from_location_id":m.from_location_id,"to_location_id":m.to_location_id,"notes":m.notes,"journal_entry_id":m.journal_entry_id} for m in asset.movements]}

    def capitalize(self, asset, value, user):
        if asset.status != "DRAFT": raise HTTPException(409, "Only configured draft assets can be capitalized")
        if not asset.asset_category_id or (asset.depreciation_method != "NONE" and not all((getattr(asset, "useful_life_months", None), getattr(asset, "accumulated_depreciation_account_id", None), getattr(asset, "depreciation_expense_account_id", None)))):
            raise HTTPException(409, "Set an asset category and depreciation accounts before capitalization")
        if asset.depreciation_method != "NONE" and (not value.depreciation_start_date or value.depreciation_start_date < value.capitalization_date): raise HTTPException(422, "Depreciation start cannot precede capitalization")
        if value.create_journal:
            if asset.accumulated_depreciation: raise HTTPException(422,"Opening depreciation is register history; activate without a new acquisition journal")
            if asset.purchase_invoice_id:
                raise HTTPException(409, "Invoice already posted the asset acquisition; capitalize without another journal")
            if asset.goods_receipt_id:
                receipt = self.db.get(GoodsReceipt, asset.goods_receipt_id)
                if receipt and receipt.status == "POSTED":
                    raise HTTPException(409, "Receiving has already posted the asset acquisition; capitalize without creating another journal")
            if not value.offset_account_id: raise HTTPException(422, "Offset account is required")
        if value.capitalization_date < asset.acquisition_date: raise HTTPException(422,"Capitalization cannot precede acquisition")
        from app.services.fiscal_period_service import FiscalPeriodService
        FiscalPeriodService.validate_posting_date(db=self.db,posting_date=value.capitalization_date)
        self.validate_accounts(asset)
        if value.create_journal: self.account(value.offset_account_id,("ASSET","LIABILITY","EQUITY"),"Acquisition credit")
        asset.capitalization_date=value.capitalization_date; asset.depreciation_start_date=value.depreciation_start_date if asset.depreciation_method != "NONE" else None; asset.status="FULLY_DEPRECIATED" if asset.depreciation_method != "NONE" and asset.net_book_value <= asset.residual_value else "ACTIVE"
        if value.create_journal:
            self._journal(value.capitalization_date,"FIXED_ASSET_CAPITALIZATION",asset.id,asset.asset_number,[(asset.asset_account_id,asset.acquisition_cost,ZERO),(value.offset_account_id,ZERO,asset.acquisition_cost)],asset,user)
        self.generate_schedule(asset)
        return asset

    def generate_schedule(self, asset):
        if asset.status not in ("ACTIVE", "FULLY_DEPRECIATED"): raise HTTPException(409, "Asset must be active")
        if asset.depreciation_method == "NONE": return []
        if asset.net_book_value <= asset.residual_value: return asset.schedules
        start = month_start(asset.depreciation_start_date)
        if asset.depreciation_start_date.day != 1: start = next_month(start)
        posted = {(s.period_year,s.period_month) for s in self.db.query(FixedAssetDepreciationSchedule).filter(FixedAssetDepreciationSchedule.fixed_asset_id==asset.id,FixedAssetDepreciationSchedule.status=="POSTED").all()}
        self.db.query(FixedAssetDepreciationSchedule).filter(FixedAssetDepreciationSchedule.fixed_asset_id==asset.id,FixedAssetDepreciationSchedule.status.in_(["PLANNED","GENERATED"])).delete(synchronize_session=False)
        depreciable = Decimal(asset.acquisition_cost)-Decimal(asset.residual_value)
        monthly = (depreciable/asset.useful_life_months).quantize(CENT, rounding=ROUND_HALF_UP)
        if monthly <= ZERO: raise HTTPException(422,"Monthly depreciation rounds to zero; review cost and useful life")
        accumulated = Decimal(asset.accumulated_depreciation); opening = Decimal(asset.net_book_value); current=start
        created=[]
        for index in range(asset.useful_life_months):
            if (current.year,current.month) in posted: current=next_month(current); continue
            remaining=opening-Decimal(asset.residual_value)
            if remaining <= ZERO: break
            amount=remaining if index == asset.useful_life_months - 1 else min(monthly,remaining)
            schedule=FixedAssetDepreciationSchedule(fixed_asset_id=asset.id,period_year=current.year,period_month=current.month,period_start=current,period_end=month_end(current),opening_book_value=opening,depreciation_amount=amount,accumulated_depreciation=accumulated+amount,closing_book_value=opening-amount,status="PLANNED")
            self.db.add(schedule);created.append(schedule);opening-=amount;accumulated+=amount;current=next_month(current)
        self.db.flush(); self.db.expire(asset,["schedules"]); return created

    def transfer(self, asset, value, user):
        if asset.status not in ("ACTIVE","FULLY_DEPRECIATED"): raise HTTPException(409,"Asset cannot be transferred")
        if value.movement_date < (asset.capitalization_date or asset.acquisition_date): raise HTTPException(422,"Transfer cannot precede acquisition/capitalization")
        from app.services.fiscal_period_service import FiscalPeriodService
        FiscalPeriodService.validate_posting_date(db=self.db,posting_date=value.movement_date)
        validate_dimensions(self.db,value.business_unit_id,value.location_id,value.department_id,required=True)
        if all(getattr(asset,k)==getattr(value,k) for k in ("business_unit_id","location_id","department_id","custodian_user_id")): raise HTTPException(409,"Asset already has this assignment")
        if self.db.query(FixedAssetDepreciationSchedule.id).filter(FixedAssetDepreciationSchedule.fixed_asset_id==asset.id,FixedAssetDepreciationSchedule.status=="POSTED",FixedAssetDepreciationSchedule.period_end>value.movement_date).first(): raise HTTPException(409,"Unpost later depreciation before transfer")
        movement=FixedAssetMovement(fixed_asset_id=asset.id,movement_type="TRANSFER",from_business_unit_id=asset.business_unit_id,to_business_unit_id=value.business_unit_id,from_location_id=asset.location_id,to_location_id=value.location_id,from_department_id=asset.department_id,to_department_id=value.department_id,movement_date=value.movement_date,reference_number=value.reference_number,notes=value.notes,created_by_id=user.id)
        self.db.add(movement); self.db.flush()
        changed = any(getattr(asset,k)!=getattr(value,k) for k in ("business_unit_id","location_id","department_id"))
        if value.create_journal and changed:
            from types import SimpleNamespace
            target = SimpleNamespace(business_unit_id=value.business_unit_id,location_id=value.location_id,department_id=value.department_id)
            cost=Decimal(asset.acquisition_cost); accumulated=Decimal(asset.accumulated_depreciation)
            lines=[(asset.asset_account_id,cost,ZERO,target),(asset.asset_account_id,ZERO,cost,asset)]
            if accumulated: lines.extend([(asset.accumulated_depreciation_account_id,accumulated,ZERO,asset),(asset.accumulated_depreciation_account_id,ZERO,accumulated,target)])
            entry=self._journal(value.movement_date,"FIXED_ASSET_TRANSFER",movement.id,asset.asset_number,lines,asset,user)
            movement.journal_entry_id=entry.id
        asset.business_unit_id=value.business_unit_id;asset.location_id=value.location_id;asset.department_id=value.department_id;asset.custodian_user_id=value.custodian_user_id
        return asset

    def _journal(self, posting_date, ref_type, ref_id, ref_number, lines, asset, user):
        if self.db.query(JournalEntry).filter(JournalEntry.reference_type==ref_type,JournalEntry.reference_id==ref_id,JournalEntry.status=="POSTED").first(): raise HTTPException(409,"Journal already posted")
        debit=sum((x[1] for x in lines),ZERO);credit=sum((x[2] for x in lines),ZERO)
        if debit!=credit:raise HTTPException(422,"Journal is not balanced")
        entry=JournalEntry(journal_number=next_document_number(self.db,"JV",digits=8),posting_date=posting_date,status="POSTED",document_type="FIXED_ASSET",document_number=ref_number,reference_type=ref_type,reference_id=ref_id,description=f"{ref_type} {ref_number}",created_by_id=user.id,posted_by_id=user.id,business_unit_id=asset.business_unit_id,location_id=asset.location_id,department_id=asset.department_id,fiscal_year=posting_date.year,fiscal_period=posting_date.month)
        self.db.add(entry);self.db.flush()
        for number,values in enumerate(lines,1):
            account_id,d,c = values[:3]
            organization = values[3] if len(values) > 3 else asset
            self.db.add(JournalLine(journal_entry_id=entry.id,line_number=number,account_id=account_id,debit=d,credit=c,description=entry.description,business_unit_id=organization.business_unit_id,location_id=organization.location_id,department_id=organization.department_id))
        self.db.flush()
        from app.services.asset_posting import post_asset_ledger
        post_asset_ledger(self.db, entry, user)
        return entry

    def dispose(self, asset, value, user, write_off=False):
        if asset.status not in ("ACTIVE","FULLY_DEPRECIATED"): raise HTTPException(409,"Asset cannot be disposed")
        proceeds=ZERO if write_off else Decimal(value.disposal_proceeds);book=Decimal(asset.net_book_value);gain=proceeds-book
        lines=[]
        if proceeds:
            if not value.cash_account_id:raise HTTPException(422,"Cash account is required when disposal proceeds exist")
            cash = self.account(value.cash_account_id,"ASSET","Cash account")
            if cash.normal_balance != "DEBIT" or cash.account_subtype not in {"CASH","BANK","PETTY_CASH","CASH_AND_BANK"}: raise HTTPException(422,"Select a cash/bank account for proceeds")
            lines.append((value.cash_account_id,proceeds,ZERO))
        if Decimal(asset.accumulated_depreciation) > ZERO:
            if not asset.accumulated_depreciation_account_id: raise HTTPException(422, "Accumulated depreciation account is missing")
            lines.append((asset.accumulated_depreciation_account_id,Decimal(asset.accumulated_depreciation),ZERO))
        if gain<0:
            if not asset.disposal_loss_account_id:raise HTTPException(422,"Disposal loss account is required")
            lines.append((asset.disposal_loss_account_id,-gain,ZERO))
        elif gain>0:
            if not asset.disposal_gain_account_id:raise HTTPException(422,"Disposal gain account is required")
            lines.append((asset.disposal_gain_account_id,ZERO,gain))
        lines.append((asset.asset_account_id,ZERO,Decimal(asset.acquisition_cost)))
        when=value.write_off_date if write_off else value.disposal_date;kind="FIXED_ASSET_WRITE_OFF" if write_off else "FIXED_ASSET_DISPOSAL"
        if when < (asset.capitalization_date or asset.acquisition_date): raise HTTPException(422, "Disposal cannot precede acquisition/capitalization")
        if self.db.query(FixedAssetDepreciationSchedule.id).filter(FixedAssetDepreciationSchedule.fixed_asset_id==asset.id,FixedAssetDepreciationSchedule.status=="POSTED",FixedAssetDepreciationSchedule.period_end>when).first():
            raise HTTPException(409,"Unpost later depreciation before disposal")
        entry=self._journal(when,kind,asset.id,asset.asset_number,lines,asset,user)
        self.db.query(FixedAssetDepreciationSchedule).filter(FixedAssetDepreciationSchedule.fixed_asset_id==asset.id,FixedAssetDepreciationSchedule.status.in_(["PLANNED","GENERATED"])).update({"status":"SKIPPED"},synchronize_session=False)
        asset.net_book_value = ZERO
        asset.status="WRITTEN_OFF" if write_off else "DISPOSED";asset.written_off_at=datetime.now(timezone.utc) if write_off else None;asset.disposed_at=None if write_off else datetime.now(timezone.utc)
        self.db.add(FixedAssetMovement(fixed_asset_id=asset.id,movement_type="WRITE_OFF" if write_off else "DISPOSAL",from_business_unit_id=asset.business_unit_id,from_location_id=asset.location_id,from_department_id=asset.department_id,movement_date=when,reference_number=entry.journal_number,journal_entry_id=entry.id,notes=value.notes,created_by_id=user.id))
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
        rows=self.calculate_rows(run)
        if rows:
            ids = sorted({s.fixed_asset_id for s in rows})
            self.db.query(FixedAsset).filter(FixedAsset.id.in_(ids)).order_by(FixedAsset.id).with_for_update().all()
            rows = self.calculate_rows(run)  # Recheck after acquiring asset locks.
            when = month_end(date(run.period_year,run.period_month,1))
            if self.db.query(FixedAssetDepreciationSchedule.id).filter(FixedAssetDepreciationSchedule.fixed_asset_id.in_(ids), FixedAssetDepreciationSchedule.period_end < when, FixedAssetDepreciationSchedule.status.in_(["PLANNED","GENERATED"])).first():
                raise HTTPException(409,"Post earlier depreciation periods first")
            if len(rows) != run.asset_count or sum((Decimal(s.depreciation_amount) for s in rows),ZERO) != run.total_depreciation:
                raise HTTPException(409,"Depreciation changed; recalculate this run")
        grouped=defaultdict(lambda:[ZERO,ZERO,None])
        for s in rows:
            from app.services.organization_access import resolve_organization_access
            resolve_organization_access(self.db,user,location_id=s.asset.location_id,business_unit_id=s.asset.business_unit_id,department_id=s.asset.department_id)
            a=s.asset;key=(a.depreciation_expense_account_id,a.accumulated_depreciation_account_id,a.business_unit_id,a.location_id,a.department_id);grouped[key][0]+=Decimal(s.depreciation_amount);grouped[key][1]+=Decimal(s.depreciation_amount);grouped[key][2]=a
        lines=[]
        for (expense,accumulated,*_),amounts in grouped.items():lines.extend([(expense,amounts[0],ZERO,amounts[2]),(accumulated,ZERO,amounts[1],amounts[2])])
        representative=rows[0].asset if rows else None
        if not representative:raise HTTPException(409,"No depreciation schedules for this run")
        if len({(s.asset.business_unit_id,s.asset.location_id) for s in rows}) > 1:
            raise HTTPException(409,"Select one business unit and work location per depreciation run")
        if len({s.asset.department_id for s in rows}) > 1:
            from types import SimpleNamespace
            representative=SimpleNamespace(business_unit_id=representative.business_unit_id, location_id=representative.location_id, department_id=None)
        posting=month_end(date(run.period_year,run.period_month,1));entry=self.assets._journal(posting,"FIXED_ASSET_DEPRECIATION",run.id,run.run_number,lines,representative,user)
        now=datetime.now(timezone.utc)
        for s in rows:s.status="POSTED";s.journal_entry_id=entry.id;s.posted_at=now;s.asset.accumulated_depreciation=Decimal(s.asset.accumulated_depreciation)+Decimal(s.depreciation_amount);s.asset.net_book_value=Decimal(s.asset.acquisition_cost)-Decimal(s.asset.accumulated_depreciation);s.asset.status="FULLY_DEPRECIATED" if s.asset.net_book_value<=s.asset.residual_value else "ACTIVE"
        run.status="POSTED";run.journal_entry_id=entry.id;run.posted_by_id=user.id;run.posted_at=now;return entry
    def calculate_rows(self,run):
        q=self.db.query(FixedAssetDepreciationSchedule).options(joinedload(FixedAssetDepreciationSchedule.asset)).join(FixedAsset).filter(FixedAssetDepreciationSchedule.period_year==run.period_year,FixedAssetDepreciationSchedule.period_month==run.period_month,FixedAssetDepreciationSchedule.status.in_(["PLANNED","GENERATED"]),FixedAsset.status=="ACTIVE")
        if run.business_unit_id:q=q.filter(FixedAsset.business_unit_id==run.business_unit_id)
        if run.location_id:q=q.filter(FixedAsset.location_id==run.location_id)
        return q.all()

    def unpost(self, run, user):
        if run.status != "POSTED" or not run.journal_entry_id: raise HTTPException(409,"Only posted runs can be unposted")
        entry = self.db.get(JournalEntry,run.journal_entry_id)
        if not entry: raise HTTPException(409,"Run journal is missing; inspection required")
        rows = self.db.query(FixedAssetDepreciationSchedule).filter(FixedAssetDepreciationSchedule.journal_entry_id==entry.id,FixedAssetDepreciationSchedule.status=="POSTED").with_for_update().all()
        if not rows: raise HTTPException(409,"Posted schedules are missing")
        ids = sorted({s.fixed_asset_id for s in rows})
        assets = self.db.query(FixedAsset).filter(FixedAsset.id.in_(ids)).order_by(FixedAsset.id).with_for_update().all()
        from app.services.organization_access import resolve_organization_access
        for asset in assets: resolve_organization_access(self.db,user,location_id=asset.location_id,business_unit_id=asset.business_unit_id,department_id=asset.department_id)
        if any(a.status not in ("ACTIVE","FULLY_DEPRECIATED") for a in assets): raise HTTPException(409,"Disposed/transferred source changes require inspection")
        if self.db.query(FixedAssetDepreciationSchedule.id).filter(FixedAssetDepreciationSchedule.fixed_asset_id.in_(ids),FixedAssetDepreciationSchedule.status=="POSTED",FixedAssetDepreciationSchedule.period_end>entry.posting_date).first(): raise HTTPException(409,"Unpost later depreciation periods first")
        if self.db.query(FixedAssetMovement.id).filter(FixedAssetMovement.fixed_asset_id.in_(ids),FixedAssetMovement.movement_type=="TRANSFER",FixedAssetMovement.movement_date>=entry.posting_date).first(): raise HTTPException(409,"Asset has subsequent transfers; inspect before unposting")
        from app.services.asset_posting import unpost_asset_ledger
        unpost_asset_ledger(self.db,entry)
        for row in rows:
            asset = row.asset
            asset.accumulated_depreciation = Decimal(asset.accumulated_depreciation)-Decimal(row.depreciation_amount)
            asset.net_book_value = Decimal(asset.acquisition_cost)-asset.accumulated_depreciation
            asset.status = "ACTIVE"
            row.status = "PLANNED"; row.journal_entry_id = None; row.posted_at = None
        run.status = "DRAFT"; run.journal_entry_id = None; run.posted_at = None; run.posted_by_id = None
        return entry

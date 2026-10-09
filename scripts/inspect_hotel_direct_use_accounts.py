"""Inspect live expense COA, departments and Direct Use posting measurements. No writes."""
import json
import sys
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import func
from app.core.database import SessionLocal
from app.models.chart_of_account import ChartOfAccount
from app.models.department import Department
from app.models.location import Location
from app.models.business_unit import BusinessUnit
from app.models.location_department import LocationDepartment
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.goods_receipt import GoodsReceipt

CANDIDATES={
    '500-100-100':'F&B food cost', '500-100-102':'F&B beverage cost',
    '600-100-107':'Staff meals', '700-500-103':'Office / Front Office stationery',
    '700-500-104':'Cleaning / pest control', '700-500-106':'Operational equipment repairs',
    '700-500-119':'Operating / guest supplies (broad existing account)',
    '700-500-123':'Laundry / dry cleaning', '700-500-124':'Building repairs',
    '700-500-120':'Marketing materials',
}


def main():
    with SessionLocal() as db:
        accounts=db.query(ChartOfAccount).filter(ChartOfAccount.account_number.in_(CANDIDATES)).order_by(ChartOfAccount.account_number).all()
        coa=[{'id':row.id,'code':row.account_number,'name':row.account_name,'usage':CANDIDATES[row.account_number], 'eligible':row.is_active and row.is_posting and row.account_type=='EXPENSE' and row.normal_balance=='DEBIT'} for row in accounts]
        locations=db.query(Location.id,Location.name,BusinessUnit.name.label('unit'),Department.id.label('department_id'),Department.name.label('department')).join(BusinessUnit,BusinessUnit.id==Location.business_unit_id).outerjoin(LocationDepartment,LocationDepartment.location_id==Location.id).outerjoin(Department,Department.id==LocationDepartment.department_id).filter(Location.is_active.is_(True)).order_by(BusinessUnit.name,Location.name,Department.name).all()
        activity=db.query(JournalLine.department_id,Department.name.label('department'),ChartOfAccount.account_number,ChartOfAccount.account_name,func.sum(JournalLine.debit).label('debit'),func.sum(JournalLine.credit).label('credit')).join(JournalEntry,JournalEntry.id==JournalLine.journal_entry_id).join(GoodsReceipt,GoodsReceipt.id==JournalEntry.reference_id).join(ChartOfAccount,ChartOfAccount.id==JournalLine.account_id).outerjoin(Department,Department.id==JournalLine.department_id).filter(JournalEntry.reference_type=='GOODS_RECEIPT',JournalEntry.status=='POSTED',GoodsReceipt.destination_type=='DIRECT_USE',JournalEntry.posting_date>=date(2026,1,1),ChartOfAccount.account_type=='EXPENSE').group_by(JournalLine.department_id,Department.name,ChartOfAccount.account_number,ChartOfAccount.account_name).order_by(Department.name,ChartOfAccount.account_number).all()
        print(json.dumps({'candidate_expense_accounts':coa,'missing_candidates':sorted(set(CANDIDATES)-{row.account_number for row in accounts}),'location_departments':[dict(row._mapping) for row in locations],'posted_direct_use_expenses':[dict(row._mapping) for row in activity]},indent=2,default=str))
        print('READ ONLY: no mappings, masters, stock, journals or balances changed.')


if __name__=='__main__':main()

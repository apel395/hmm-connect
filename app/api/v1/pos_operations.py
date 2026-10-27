from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.models.pos_operations import PosTable, PosCashierSession
from app.models.sales_transaction import SalesTransaction
from app.models.journal_entry import JournalEntry
from app.schemas.pos_operations import OutletPolicyIn, TableIn, ShiftOpen, ShiftClose, OutletSetupIn
from app.services import pos_operations as ops
from app.services.sales_transaction_service import SalesTransactionService as Sales

router=APIRouter(prefix='/pos-operations',tags=['Hotel POS operations'])


def manage(user):Sales._require(user,'finance.manage')


@router.get('/context')
def context(location_id:int,department_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    Sales._require(user,'pos.view');ops.outlet(db,user,location_id,department_id)
    p=ops.policy(db,location_id,department_id)
    orders=Sales.scoped_query(db,user).filter_by(location_id=location_id,department_id=department_id,status='DRAFT',transaction_type='POS').all()
    occupied={r.pos_table_id:r for r in orders if r.pos_table_id}
    tables=db.query(PosTable).filter_by(location_id=location_id,department_id=department_id).order_by(PosTable.name).all()
    shifts=db.query(PosCashierSession).filter_by(location_id=location_id,department_id=department_id)
    if not has_permission(user,'finance.manage'):shifts=shifts.filter_by(cashier_id=user.id)
    return {'order_mode':p.order_mode if p else None,'tables':[{'id':t.id,'name':t.name,'seats':t.seats,'is_active':t.is_active,'status':'OCCUPIED' if t.id in occupied else 'AVAILABLE','order_id':occupied[t.id].id if t.id in occupied else None} for t in tables],
        'shifts':[ops.shift_report(db,r) for r in shifts.order_by(PosCashierSession.status.desc(),PosCashierSession.id.desc()).limit(50)],
        'orders':[{'id':r.id,'number':r.transaction_number,'table':r.table_number,'event':r.event_name,'cashier_id':r.created_by_id,'session_id':r.cashier_session_id,'total':r.total_amount,'date':r.sale_date} for r in orders]}


@router.put('/policy')
def configure(data:OutletPolicyIn,db:Session=Depends(get_db),user=Depends(get_current_user)):
    manage(user);r=ops.set_policy(db,data,user);return {'order_mode':r.order_mode}


@router.post('/tables',status_code=201)
def create_table(data:TableIn,db:Session=Depends(get_db),user=Depends(get_current_user)):
    manage(user);r=ops.save_table(db,data,user);return {'id':r.id,'name':r.name}


@router.put('/tables/{table_id}')
def edit_table(table_id:int,data:TableIn,db:Session=Depends(get_db),user=Depends(get_current_user)):
    manage(user);r=ops.save_table(db,data,user,table_id);return {'id':r.id,'name':r.name,'is_active':r.is_active}


@router.post('/shifts',status_code=201)
def open_shift(data:ShiftOpen,db:Session=Depends(get_db),user=Depends(get_current_user)):
    Sales._require(user,'pos.sell');r=ops.open_shift(db,data,user);return ops.shift_report(db,r)


@router.get('/shifts/{shift_id}')
def shift(shift_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    Sales._require(user,'pos.view');return ops.shift_report(db,ops.shift_access(db,shift_id,user))


@router.post('/shifts/{shift_id}/close')
def close(shift_id:int,data:ShiftClose,db:Session=Depends(get_db),user=Depends(get_current_user)):
    Sales._require(user,'pos.sell');r=ops.shift_access(db,shift_id,user,lock=True);return ops.close_shift(db,r,data,user)


@router.get('/report')
def report(location_id:int,department_id:int,date_from:date,date_to:date,cashier_id:int|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    Sales._require(user,'pos.view');loc,dept=ops.outlet(db,user,location_id,department_id)
    if date_to<date_from:raise HTTPException(422,'End date must not precede start date')
    query=Sales.scoped_query(db,user).join(JournalEntry,JournalEntry.id==SalesTransaction.journal_entry_id).filter(SalesTransaction.location_id==location_id,SalesTransaction.department_id==department_id,SalesTransaction.status=='POSTED',SalesTransaction.transaction_type=='POS',JournalEntry.status=='POSTED',SalesTransaction.sale_date>=date_from,SalesTransaction.sale_date<=date_to)
    if cashier_id:query=query.filter(SalesTransaction.posted_by_id==cashier_id)
    rows=query.order_by(SalesTransaction.sale_date,SalesTransaction.id).all()
    result=ops.totals(rows);days={}
    for row in rows:days.setdefault(row.sale_date,[]).append(row)
    result.update({'location':loc.name,'outlet':dept.name,'date_from':date_from,'date_to':date_to,'daily':[{'date':d,**ops.totals(r)} for d,r in days.items()]})
    return result


@router.get('/outlets')
def outlet_setup(location_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    Sales._require(user,'pos.view')
    from app.services.pos_outlet_setup import list_outlets
    return list_outlets(db,user,location_id)


@router.post('/outlets',status_code=201)
def create_outlet(data:OutletSetupIn,db:Session=Depends(get_db),user=Depends(get_current_user)):
    from app.services.pos_outlet_setup import save_outlet
    return save_outlet(db,user,data)


@router.put('/outlets/{outlet_id}')
def edit_outlet(outlet_id:int,data:OutletSetupIn,db:Session=Depends(get_db),user=Depends(get_current_user)):
    from app.services.pos_outlet_setup import save_outlet
    return save_outlet(db,user,data,outlet_id)

"""Operational control only; settlement remains in SalesTransactionService."""
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import func
from app.dependencies.authorization import has_permission
from app.models.department import Department
from app.models.department_outlet import DepartmentOutlet
from app.models.location import Location
from app.models.business_unit import BusinessUnit
from app.models.sales_transaction import SalesTransaction
from app.models.journal_entry import JournalEntry
from app.models.user import User
from app.models.pos_operations import PosTable, PosOutletPolicy, PosCashierSession
from app.services.organization_access import resolve_organization_access
from app.services.activity_service import ActivityService

ZERO = Decimal('0.00')


def outlet(db, user, location_id, department_id):
    scope = resolve_organization_access(db,user,location_id=location_id,department_id=department_id)
    location = db.get(Location,scope['location_id'])
    department = db.get(Department,scope['department_id'])
    unit = db.get(BusinessUnit,location.business_unit_id) if location else None
    link = db.get(DepartmentOutlet,department_id) if department_id else None
    parent = db.get(Department,link.parent_department_id) if link else None
    if not location or not location.is_active or not department or not department.is_active or not unit or not unit.is_active or 'hotel' not in unit.name.casefold() or not parent or not parent.is_active or parent.business_unit_id != unit.id or department.business_unit_id != unit.id:
        raise HTTPException(422,'Choose an active Hotel child outlet assigned to this location')
    return location,department


def policy(db, location_id, department_id):
    return db.query(PosOutletPolicy).filter_by(location_id=location_id,department_id=department_id).first()


def audit(db,user,action,kind,row,details):
    ActivityService.log(db=db,user=user,action=action,entity_type=kind,entity_id=row.id,summary=f'{action} {kind} {row.id}',details=details)


def set_policy(db, data, user):
    outlet(db,user,data.location_id,data.department_id)
    # Lock the outlet master to serialize configuration with shift/table creation.
    db.query(Department).filter_by(id=data.department_id).with_for_update(key_share=True).one()
    row=policy(db,data.location_id,data.department_id)
    if row and row.order_mode != data.order_mode:
        if db.query(PosCashierSession).filter_by(location_id=data.location_id,department_id=data.department_id,status='OPEN').first() or db.query(SalesTransaction).filter_by(location_id=data.location_id,department_id=data.department_id,status='DRAFT',transaction_type='POS').first():
            raise HTTPException(409,'Close shifts and complete open orders before changing outlet mode')
    before=row.order_mode if row else None
    if not row:row=PosOutletPolicy(location_id=data.location_id,department_id=data.department_id);db.add(row)
    row.order_mode=data.order_mode;db.flush()
    audit(db,user,'UPDATE','POS_OUTLET_POLICY',row,{'before':before,'order_mode':row.order_mode})
    db.commit();return row


def save_table(db, data, user, table_id=None):
    outlet(db,user,data.location_id,data.department_id)
    db.query(Department).filter_by(id=data.department_id).with_for_update(key_share=True).one()
    row=db.query(PosTable).filter_by(id=table_id).with_for_update().first() if table_id else None
    if table_id and not row:raise HTTPException(404,'Table not found')
    if row and (row.location_id,row.department_id)!=(data.location_id,data.department_id):raise HTTPException(409,'A table cannot be moved between outlets')
    if row and db.query(SalesTransaction).filter_by(pos_table_id=row.id,status='DRAFT').first():raise HTTPException(409,'Complete the occupied table order before changing the table')
    dupe=db.query(PosTable).filter(PosTable.location_id==data.location_id,PosTable.department_id==data.department_id,func.lower(PosTable.name)==data.name.lower())
    if row:dupe=dupe.filter(PosTable.id!=row.id)
    if dupe.first():raise HTTPException(409,'Table name already exists in this outlet')
    if not row:row=PosTable(location_id=data.location_id,department_id=data.department_id);db.add(row)
    row.name=data.name;row.seats=data.seats;row.is_active=data.is_active;db.flush()
    audit(db,user,'UPDATE' if table_id else 'CREATE','POS_TABLE',row,{'name':row.name,'active':row.is_active,'location_id':row.location_id,'department_id':row.department_id})
    db.commit();return row


def open_shift(db,data,user):
    outlet(db,user,data.location_id,data.department_id)
    db.query(Department).filter_by(id=data.department_id).with_for_update(key_share=True).one()
    if not policy(db,data.location_id,data.department_id):raise HTTPException(409,'Configure this outlet order mode first')
    if db.query(PosCashierSession).filter_by(location_id=data.location_id,department_id=data.department_id,cashier_id=user.id,status='OPEN').first():raise HTTPException(409,'You already have an open shift in this outlet')
    row=PosCashierSession(location_id=data.location_id,department_id=data.department_id,cashier_id=user.id,status='OPEN',opened_at=datetime.now(timezone.utc),opening_cash=data.opening_cash)
    db.add(row);db.flush();audit(db,user,'OPEN','POS_CASHIER_SESSION',row,{'opening_cash':str(row.opening_cash),'department_id':row.department_id,'location_id':row.location_id})
    db.commit();return row


def shift_access(db,session_id,user,lock=False,owner=False):
    row=db.query(PosCashierSession).filter_by(id=session_id)
    if lock:row=row.with_for_update()
    row=row.first()
    if not row:raise HTTPException(404,'Cashier shift not found')
    outlet(db,user,row.location_id,row.department_id)
    if row.cashier_id!=user.id and (owner or not has_permission(user,'finance.manage')):raise HTTPException(403,'This shift belongs to another cashier')
    return row


def is_hotel_outlet(db,transaction):
    unit=db.get(BusinessUnit,transaction.business_unit_id) if transaction.business_unit_id else None
    return bool(unit and 'hotel' in unit.name.casefold() and transaction.department_id and db.get(DepartmentOutlet,transaction.department_id))


def bind_order(db,transaction,data,user):
    if transaction.transaction_type!='POS' or not is_hotel_outlet(db,transaction):
        if data.pos_table_id or data.cashier_session_id or data.event_name:raise HTTPException(422,'Outlet order controls apply only to Hotel POS, not customer AR invoices or Catering')
        return
    outlet(db,user,transaction.location_id,transaction.department_id)
    settings=policy(db,transaction.location_id,transaction.department_id)
    if not settings:raise HTTPException(409,'Configure the outlet order mode before opening an order')
    if not data.cashier_session_id:raise HTTPException(422,'Open and select your cashier shift first')
    shift=shift_access(db,data.cashier_session_id,user,lock=True,owner=True)
    if shift.status!='OPEN' or (shift.location_id,shift.department_id)!=(transaction.location_id,transaction.department_id):raise HTTPException(409,'Choose your open shift in this outlet')
    if settings.order_mode=='TABLE' and not data.pos_table_id:raise HTTPException(422,'Choose an available table')
    if settings.order_mode=='EVENT' and (data.pos_table_id or not (data.event_name or '').strip()):raise HTTPException(422,'Banquet event orders require an event name and no table')
    if data.pos_table_id:
        table=db.query(PosTable).filter_by(id=data.pos_table_id).with_for_update().first()
        if not table or not table.is_active or (table.location_id,table.department_id)!=(transaction.location_id,transaction.department_id):raise HTTPException(422,'Choose an active table belonging to this outlet')
        if db.query(SalesTransaction).filter_by(pos_table_id=table.id,status='DRAFT').first():raise HTTPException(409,'This table already has an active order. Continue that order instead')
        transaction.pos_table_id=table.id;transaction.table_number=table.name
    else:transaction.table_number=None
    transaction.cashier_session_id=shift.id;transaction.order_mode=settings.order_mode;transaction.event_name=(data.event_name or '').strip() or None
    if not data.order_request_key:raise HTTPException(422,'An order retry key is required')
    transaction.order_request_key=data.order_request_key


def assert_open_order(db,transaction,user):
    if transaction.cashier_session_id:
        row=shift_access(db,transaction.cashier_session_id,user,lock=True,owner=True)
        if row.status!='OPEN':raise HTTPException(409,'Cashier shift is closed')
        return
    if transaction.transaction_type=='POS' and is_hotel_outlet(db,transaction):
        raise HTTPException(409,'Legacy draft has no outlet shift. Void and re-enter this unposted order under an open shift')


def totals(rows):
    result={'sales':len(rows),'gross':ZERO,'subtotal':ZERO,'discount':ZERO,'service_charge':ZERO,'pbjt':ZERO,'other_tax':ZERO,'payments':{'CASH':ZERO,'CARD':ZERO,'BANK_TRANSFER':ZERO}}
    cashiers={}
    for row in rows:
        result['gross']+=Decimal(row.total_amount or 0);result['subtotal']+=Decimal(row.subtotal or 0);result['discount']+=Decimal(row.discount_amount or 0);result['service_charge']+=Decimal(row.service_charge_amount or 0)
        for line in row.lines:result['pbjt' if line.tax_type=='PBJT' else 'other_tax']+=Decimal(line.tax_amount or 0)
        if row.payment_method in result['payments']:result['payments'][row.payment_method]+=Decimal(row.total_amount or 0)
        cid=row.posted_by_id or row.created_by_id
        cashier=cashiers.setdefault(cid,{'cashier_id':cid,'name':(row.posted_by.full_name or row.posted_by.username) if row.posted_by else str(cid),'sales':0,'gross':ZERO})
        cashier['sales']+=1;cashier['gross']+=Decimal(row.total_amount or 0)
    result['cashiers']=list(cashiers.values());return result


def shift_report(db,row):
    sales=db.query(SalesTransaction).join(JournalEntry,JournalEntry.id==SalesTransaction.journal_entry_id).filter(SalesTransaction.cashier_session_id==row.id,SalesTransaction.status=='POSTED',SalesTransaction.transaction_type=='POS',JournalEntry.status=='POSTED').order_by(SalesTransaction.id).all()
    result=totals(sales)
    cashier=db.get(User,row.cashier_id)
    result.update({'id':row.id,'cashier_name':(cashier.full_name or cashier.username) if cashier else str(row.cashier_id),'location_name':db.get(Location,row.location_id).name,'outlet_name':db.get(Department,row.department_id).name,'cashier_id':row.cashier_id,'location_id':row.location_id,'department_id':row.department_id,'status':row.status,'opened_at':row.opened_at,'closed_at':row.closed_at,'opening_cash':row.opening_cash,'expected_cash':row.expected_cash if row.status=='CLOSED' else row.opening_cash+result['payments']['CASH'],'counted_cash':row.counted_cash,'cash_difference':row.cash_difference,'difference_reason':row.difference_reason,
        'open_orders':db.query(SalesTransaction).filter_by(cashier_session_id=row.id,status='DRAFT').count(),
        'transactions':[{'id':s.id,'number':s.transaction_number,'date':s.sale_date,'method':s.payment_method,'total':s.total_amount,'journal_id':s.journal_entry_id} for s in sales]})
    return result


def close_shift(db,row,data,user):
    if row.status!='OPEN':raise HTTPException(409,'This shift is already closed')
    report=shift_report(db,row)
    if report['open_orders']:raise HTTPException(409,'Settle or void all open orders before closing this shift')
    expected=report['expected_cash'];difference=data.counted_cash-expected
    if difference and not (data.difference_reason or '').strip():raise HTTPException(422,'Enter the reason for the cash difference')
    row.expected_cash=expected;row.counted_cash=data.counted_cash;row.cash_difference=difference;row.difference_reason=data.difference_reason;row.closed_at=datetime.now(timezone.utc);row.closed_by_id=user.id;row.status='CLOSED'
    audit(db,user,'CLOSE','POS_CASHIER_SESSION',row,{'expected_cash':str(expected),'counted_cash':str(data.counted_cash),'difference':str(difference),'reason':data.difference_reason})
    db.commit();return shift_report(db,row)

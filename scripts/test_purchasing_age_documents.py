"""Create/inspect/exercise nine marked purchasing age fixtures on EC2."""
import argparse
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.audit_log import AuditLog
from app.models.business_unit import BusinessUnit
from app.models.department import Department
from app.models.location import Location
from app.models.location_department import LocationDepartment
from app.models.product import Product
from app.models.purchasing_item_policy import is_market_list_product
from app.models.supplier import Supplier
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_requisition import PurchaseRequisition
from app.models.purchase_requisition_item import PurchaseRequisitionItem
from app.models.market_list import MarketList, MarketListItem
from app.services.activity_service import ActivityService
from app.services.purchasing_retention import cleanup, months_before, today

MARKER='TEST_PURCHASING_AGE_V1'
KINDS=[('PR','PURCHASE_REQUISITION',PurchaseRequisition,'pr_number','request_date'),
       ('PO','PURCHASE_ORDER',PurchaseOrder,'po_number','order_date'),
       ('ML','MARKET_LIST',MarketList,'ml_number','request_date')]


def batch_key(as_of, location_id):
    return f'DUMMY-AGE-{as_of:%Y%m%d}-L{location_id}'


def inspect_batch(db, *, as_of, location_id):
    batch=batch_key(as_of,location_id);result=[]
    for short,kind,model,number,field in KINDS:
        for age in (7,4,2):
            value=f'{batch}-{short}-{age}M'
            created=db.query(AuditLog).filter_by(action='AGE_TEST_CREATED',entity_type=kind,document_number=value).first()
            doc=db.query(model).filter(getattr(model,number)==value).first()
            expected='DELETE' if short=='PR' and age>3 else 'TRASH' if short=='PO' and age>6 else 'KEEP'
            if doc and (not created or created.entity_id!=doc.id or (created.details or {}).get('batch')!=batch or doc.source_type!=MARKER or doc.notes!=f'{MARKER}:{batch}' or getattr(doc,field)!=months_before(as_of,age) or doc.location_id!=location_id):
                raise ValueError(f'{value}: identity or fixture data changed; no test writes allowed')
            result.append({'kind':short,'entity_type':kind,'number':value,'id':doc.id if doc else created.entity_id if created else None,
                           'date':str(months_before(as_of,age)),'months_old':age,'expected':expected,
                           'status':doc.status if doc else 'REMOVED' if created else 'NOT_CREATED'})
    return result


def create_batch(db, *, as_of, location_id):
    if as_of>today() or months_before(as_of,7)<date(2026,1,1):
        raise ValueError('Use a current/past test date whose seven-month fixture stays in 2026 or later')
    location=db.get(Location,location_id)
    if not location or not location.is_active: raise ValueError('Choose an active location')
    unit=db.get(BusinessUnit,location.business_unit_id)
    if not unit or not unit.is_active: raise ValueError('Location requires an active business unit')
    departments=db.query(Department).join(LocationDepartment).filter(LocationDepartment.location_id==location_id,Department.is_active.is_(True)).order_by(Department.id).all()
    department=next((d for d in departments if d.name.casefold().replace('&','and')=='food and beverage'), departments[0] if departments else None)
    supplier=db.query(Supplier).filter(Supplier.is_active.is_(True)).order_by(Supplier.id).first()
    if not department or not supplier: raise ValueError('Location needs a department and an existing active supplier')
    catalog='HOTEL' if 'HOTEL' in f'{unit.code} {unit.name}'.upper() else 'CATERING'
    products=db.query(Product).filter(Product.item_type=='BUY',Product.is_active.is_(True),Product.catalog_type==catalog).order_by(Product.id).all()
    market=next((p for p in products if is_market_list_product(p)),None)
    ordinary=next((p for p in products if not is_market_list_product(p)),None)
    if not market or not ordinary: raise ValueError('Existing BUY catalogue needs both a Market List item and a non-market PR item; no master data is created')
    current=inspect_batch(db,as_of=as_of,location_id=location_id);batch=batch_key(as_of,location_id)
    for row in current:
        # An audit marker prevents recreating PRs already removed by retention.
        if row['status']!='NOT_CREATED': continue
        kind=row['kind'];product=market if kind=='ML' else ordinary
        common=dict(status='DRAFT',source_type=MARKER,notes=f'{MARKER}:{batch}',business_unit_id=unit.id,location_id=location_id,department_id=department.id,subtotal=Decimal(1),tax_amount=Decimal(0),total_amount=Decimal(1))
        if kind=='PR':
            doc=PurchaseRequisition(pr_number=row['number'],request_date=date.fromisoformat(row['date']),external_reference=batch,**common)
            doc.items=[PurchaseRequisitionItem(product_id=product.id,quantity=1,estimated_price=1,total_price=1)]
        elif kind=='PO':
            doc=PurchaseOrder(po_number=row['number'],order_date=date.fromisoformat(row['date']),external_reference=batch,supplier_id=supplier.id,**common)
            doc.items=[PurchaseOrderItem(product_id=product.id,uom=product.uom,description='DUMMY retention test — do not submit',quantity=1,received_quantity=0,unit_price=1,total_price=1)]
        else:
            doc=MarketList(ml_number=row['number'],request_date=date.fromisoformat(row['date']),external_reference=batch,**common)
            doc.items=[MarketListItem(product_id=product.id,quantity=1,estimated_price=1,total_price=1)]
        db.add(doc);db.flush()
        ActivityService.log(db=db,user=None,action='AGE_TEST_CREATED',entity_type=row['entity_type'],entity_id=doc.id,
                            document_number=row['number'],document_status='DRAFT',summary=f'System test fixture: {row["number"]}',
                            details={'batch':batch,'source':MARKER,'as_of':str(as_of),'months_old':row['months_old'],'expected':row['expected']})
        db.flush()
    return inspect_batch(db,as_of=as_of,location_id=location_id)


def exercise_batch(db, *, as_of, location_id, apply=False):
    before=inspect_batch(db,as_of=as_of,location_id=location_id)
    if any(row['status']=='NOT_CREATED' for row in before): raise ValueError('Create the complete test batch first')
    ids={kind:[row['id'] for row in before if row['entity_type']==kind and row['status']!='REMOVED']
         for kind in ('PURCHASE_ORDER','PURCHASE_REQUISITION')}
    result=cleanup(db,as_of=as_of,apply=apply,only_ids=ids)
    db.flush();db.expire_all()
    return {'before':before,'retention':result,'after':inspect_batch(db,as_of=as_of,location_id=location_id)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action',choices=('create','inspect','exercise'),default='create')
    parser.add_argument('--as-of',type=date.fromisoformat,default=today())
    parser.add_argument('--location-id',type=int,default=8)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    from app.core.database import SessionLocal
    from sqlalchemy import text
    with SessionLocal() as db:
        if args.apply and db.bind.dialect.name=='postgresql':
            if not db.execute(text('SELECT pg_try_advisory_xact_lock(20261020,17)')).scalar():
                raise SystemExit('Purchasing retention is running; retry after it completes')
        if args.action=='create': result=create_batch(db,as_of=args.as_of,location_id=args.location_id)
        elif args.action=='inspect': result=inspect_batch(db,as_of=args.as_of,location_id=args.location_id)
        else: result=exercise_batch(db,as_of=args.as_of,location_id=args.location_id,apply=args.apply)
        if args.apply and args.action!='inspect': db.commit()
        else: db.rollback()
        print(json.dumps({'mode':'APPLY' if args.apply and args.action!='inspect' else 'READ_ONLY' if args.action=='inspect' else 'DRY_RUN','batch':batch_key(args.as_of,args.location_id),'result':result},indent=2))
    print('Only marked DRAFT test PR/PO/ML and their age actions are in scope. No receiving, stock, invoices, AP, journals, GL or opening balances created.')


if __name__=='__main__':main()

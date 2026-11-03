from math import ceil
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.models.goods_receipt import GoodsReceipt
from app.models.inventory_return import InventoryReturn
from app.models.supplier_invoice import SupplierInvoice
from app.schemas.inventory_return import ReturnInput, ReplacementInput, ReturnCreditInput
from app.services.inventory_return_service import (
    create_return, post_return, replace_goods, settle_credit, serialize, receipt, source_lines, get_return, audit,
)
from app.services.location_access import apply_location_scope

router = APIRouter(prefix='/inventory/returns', tags=['Inventory Returns'])


def require(user, permission):
    if not has_permission(user, permission):
        raise HTTPException(403, f'{permission} permission required')


def view_user(user=Depends(get_current_user)):
    if not any(has_permission(user, p) for p in ('inventory.view', 'receiving.view', 'finance.manage')):
        raise HTTPException(403, 'Inventory access required')
    return user


@router.get('/sources')
def sources(search: str = '', page: int = Query(1, ge=1), db=Depends(get_db), user=Depends(view_user)):
    q = apply_location_scope(db.query(GoodsReceipt), GoodsReceipt.location_id, user).filter(
        GoodsReceipt.status == 'POSTED', GoodsReceipt.warehouse_id.is_not(None),
        GoodsReceipt.source_type != 'SUPPLIER_REPLACEMENT')
    if search.strip():
        q = q.filter(GoodsReceipt.receipt_number.ilike(f'%{search.strip()}%'))
    total = q.count()
    return {'items': [{'id': row.id, 'number': row.receipt_number, 'supplier': row.supplier.name if row.supplier else None}
        for row in q.order_by(GoodsReceipt.id.desc()).offset((page - 1) * 30).limit(30)], 'total_pages': ceil(total / 30)}


@router.get('/sources/{receipt_id}')
def source_detail(receipt_id: int, db=Depends(get_db), user=Depends(view_user)):
    row = receipt(db, receipt_id, user)
    invoices = db.query(SupplierInvoice).filter(SupplierInvoice.goods_receipt_id == row.id,
        SupplierInvoice.status.notin_(['VOID', 'REJECTED'])).all()
    return {'id': row.id, 'number': row.receipt_number, 'supplier': row.supplier.name if row.supplier else None,
        'warehouse_id': row.warehouse_id, 'items': source_lines(db, row),
        'invoices': [{'id': i.id, 'number': i.internal_invoice_number, 'status': i.status,
                      'balance': i.balance_amount, 'total': i.total_amount} for i in invoices]}


@router.get('')
def listing(search: str = '', page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=100),
            db=Depends(get_db), user=Depends(view_user)):
    q = apply_location_scope(db.query(InventoryReturn).join(GoodsReceipt,
        GoodsReceipt.id == InventoryReturn.goods_receipt_id), GoodsReceipt.location_id, user)
    if search.strip():
        q = q.filter(or_(InventoryReturn.number.ilike(f'%{search.strip()}%'), GoodsReceipt.receipt_number.ilike(f'%{search.strip()}%')))
    total = q.count()
    rows = q.order_by(InventoryReturn.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {'items': [serialize(db, row) for row in rows], 'total_items': total, 'total_pages': ceil(total / page_size)}


@router.get('/{document_id}')
def detail(document_id: int, db=Depends(get_db), user=Depends(view_user)):
    row, _ = get_return(db, document_id, user)
    return serialize(db, row)


def commit_result(db, operation):
    try:
        row = operation()
        db.commit()
        db.refresh(row)
        return serialize(db, row)
    except IntegrityError as error:
        db.rollback()
        if 'request_key' in str(error.orig):
            raise HTTPException(409, 'Return request key was already registered; refresh before retrying') from error
        raise
    except Exception:
        db.rollback()
        raise


@router.post('', status_code=201)
def create(data: ReturnInput, db=Depends(get_db), user=Depends(view_user)):
    require(user, 'receiving.return')
    return commit_result(db, lambda: create_return(db, data, user))


@router.post('/{document_id}/post')
def post(document_id: int, db=Depends(get_db), user=Depends(view_user)):
    require(user, 'receiving.return')
    return commit_result(db, lambda: post_return(db, document_id, user))


@router.post('/{document_id}/void')
def void(document_id: int, db=Depends(get_db), user=Depends(view_user)):
    require(user, 'receiving.return')
    def operation():
        row, _ = get_return(db, document_id, user)
        if row.status != 'DRAFT':
            raise HTTPException(409, 'Only draft returns can be voided')
        row.status = 'VOID'
        audit(db, row, user, 'VOID')
        return row
    return commit_result(db, operation)


@router.post('/{document_id}/replacement')
def replacement(document_id: int, data: ReplacementInput, db=Depends(get_db), user=Depends(view_user)):
    require(user, 'receiving.post')
    return commit_result(db, lambda: replace_goods(db, document_id, data, user))


@router.post('/{document_id}/credit')
def credit(document_id: int, data: ReturnCreditInput, db=Depends(get_db), user=Depends(view_user)):
    require(user, 'finance.manage')
    return commit_result(db, lambda: settle_credit(db, document_id, data, user))

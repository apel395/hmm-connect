"""Audit print attempts and explicit PDF downloads, never physical printer output."""
from datetime import datetime, timezone
from hashlib import sha256
import json

from fastapi import HTTPException
from sqlalchemy import inspect
from app.models.audit_log import AuditLog
from app.models.document_sequence import DocumentSequence
from app.models.store_request import StoreRequest
from app.models.stock_opname import StockOpname
from app.services.purchasing_exceptions import SOURCES
from app.services.activity_service import ActivityService
from app.dependencies.authorization import has_permission
from app.services.location_access import enforce_location_access

DOCUMENTS = {**SOURCES, 'STORE_REQUEST': (StoreRequest, 'sr_number', None, 'store_request.view'),
             'STOCK_OPNAME': (StockOpname, 'opname_number', None, 'stock_opname.view')}
REPORTS = {'PURCHASE_REQUISITION_LIST': 'pr.view', 'MARKET_LIST_LIST': 'market_list.view',
           'PURCHASE_ORDER_LIST': 'po.view', 'GOODS_RECEIPT_LIST': 'receiving.view',
           'PURCHASING_REPORT': 'reports.purchasing', 'EXPECTED_RECEIVING': 'receiving.view'}
ACTIONS = {'PRINT_DIALOG': 'PRINT', 'PDF_DOWNLOAD': 'PDF_DOWNLOAD'}


def _source(db, user, kind, document_id, lock=False):
    if kind in REPORTS:
        if not has_permission(user, REPORTS[kind]):
            raise HTTPException(403, 'Report view permission required')
        if document_id != 0:
            if kind != 'EXPECTED_RECEIVING':
                raise HTTPException(422, 'Report ID must be zero')
            model, field, *_ = SOURCES['PURCHASE_ORDER']
            query = db.query(model).filter_by(id=document_id)
            document = (query.with_for_update() if lock else query).first()
            if not document:
                raise HTTPException(404, 'Purchase order not found')
            enforce_location_access(user, document.location_id)
            return document, getattr(document, field)
        if lock:
            # Report prints have no source row. Serialize their sequence using
            # the existing transactional allocator table, without a migration.
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
            insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
            key = f'PRINT_TRACKING:{kind}:{user.id}'
            db.execute(insert(DocumentSequence).values(sequence_key=key, current_value=0).on_conflict_do_nothing(index_elements=['sequence_key']))
            db.query(DocumentSequence).filter_by(sequence_key=key).with_for_update().one()
        return None, kind.replace('_', ' ')
    source = DOCUMENTS.get(kind)
    if not source:
        raise HTTPException(422, 'Unsupported print document')
    model, number, _, permission, *_ = source
    if not has_permission(user, permission):
        raise HTTPException(403, 'Document view permission required')
    query = db.query(model).filter_by(id=document_id)
    document = (query.with_for_update() if lock else query).first()
    if not document:
        raise HTTPException(404, 'Document not found')
    enforce_location_access(user, document.location_id)
    return document, getattr(document, number)


def revision_hash(db, document):
    def columns(row):
        return {column.key: getattr(row, column.key) for column in inspect(type(row)).columns
                if column.key not in {'updated_at'}}
    payload = {'header': columns(document), 'items': []}
    for line in sorted(getattr(document, 'items', []), key=lambda row: row.id or 0):
        item = columns(line)
        product = getattr(line, 'product', None)
        if product:
            item['product_identity'] = {'code': product.code, 'name': product.name}
        payload['items'].append(item)
    # Printed master names and approval decisions are part of the revision.
    for relation in ('supplier', 'location', 'department', 'requester', 'created_by'):
        row = getattr(document, relation, None)
        if row is not None:
            payload[relation] = getattr(row, 'name', getattr(row, 'full_name', None))
    from app.models.approval_request import ApprovalRequest
    approvals = db.query(ApprovalRequest).filter_by(entity_type=_kind_for(document), entity_id=document.id).order_by(ApprovalRequest.id).all()
    payload['approvals'] = [[columns(step) for step in sorted(request.steps, key=lambda step: step.id or 0)] for request in approvals]
    return sha256(json.dumps(payload, sort_keys=True, default=str, separators=(',', ':')).encode()).hexdigest()


def _kind_for(document):
    return next((kind for kind, source in DOCUMENTS.items() if isinstance(document, source[0])), '')


def _events(db, user, kind, document_id):
    query = db.query(AuditLog).filter_by(entity_type=kind, entity_id=document_id).filter(AuditLog.action.in_(('PRINT', 'PDF_DOWNLOAD')))
    if kind in REPORTS:
        query = query.filter(AuditLog.user_id == user.id)
    return query


def _summary(events):
    return {'print_count': sum(event.action == 'PRINT' for event in events),
            'pdf_download_count': sum(event.action == 'PDF_DOWNLOAD' for event in events)}


def print_context(db, user, kind, document_id):
    document, _ = _source(db, user, kind, document_id)
    events = _events(db, user, kind, document_id).order_by(AuditLog.id).all()
    return {'print_tracking': {**_summary(events), 'revision_hash': revision_hash(db, document) if document else None,
                              'physical_print_confirmed': False}}


def print_history(db, user, kind, document_id):
    context = print_context(db, user, kind, document_id)['print_tracking']
    events = _events(db, user, kind, document_id).order_by(AuditLog.id.desc()).limit(100).all()
    return {**context, 'events': [{'id': event.id, 'action': 'PRINT_DIALOG' if event.action == 'PRINT' else 'PDF_DOWNLOAD',
        'actor_name': event.actor_name, 'occurred_at': event.created_at, 'details': event.details or {}} for event in events]}


def record_print(db, user, kind, document_id, request_id, *, action='PRINT_DIALOG', expected_revision=None, snapshot_hash=None, commit=True):
    if action not in ACTIONS:
        raise HTTPException(422, 'Unsupported print action')
    if kind in REPORTS and not snapshot_hash:
        raise HTTPException(422, 'Report snapshot hash is required')
    document, number = _source(db, user, kind, document_id, lock=True)
    query = _events(db, user, kind, document_id)
    existing = query.filter(AuditLog.details['request_id'].as_string() == request_id).first()
    if existing:
        if existing.user_id != user.id or existing.action != ACTIONS[action]:
            raise HTTPException(409, 'Print request ID is already used')
        previous = query.filter(AuditLog.id <= existing.id).order_by(AuditLog.id).all()
        response = {**_summary(previous), **(existing.details or {}), 'physical_print_confirmed': False}
        response.setdefault('reprint_number', max(0, response['print_count'] - 1))
        response.setdefault('correction_count', 0)
        if commit:
            db.commit()
        return response
    revision = revision_hash(db, document) if document else snapshot_hash
    if expected_revision and expected_revision != revision:
        raise HTTPException(409, 'Document changed after preview. Refresh the preview before printing or downloading.')
    events = query.order_by(AuditLog.id).all()
    counts = _summary(events)
    revisions = list(dict.fromkeys((event.details or {}).get('revision_hash') for event in events if (event.details or {}).get('revision_hash')))
    revision_number = revisions.index(revision) + 1 if revision in revisions else len(revisions) + 1
    counts['print_count' if action == 'PRINT_DIALOG' else 'pdf_download_count'] += 1
    details = {**counts, 'request_id': request_id, 'channel': action, 'document_number': number,
        'revision_hash': revision, 'revision_number': revision_number, 'rendered_snapshot_hash': snapshot_hash,
        'reprint_number': max(0, counts['print_count'] - 1), 'correction_count': max(0, revision_number - 1),
        'requested_at': datetime.now(timezone.utc).isoformat(), 'actor_name': getattr(user, 'full_name', None) or getattr(user, 'username', None),
        'outcome': 'REQUESTED', 'physical_print_confirmed': False}
    event_label = f"Print attempt #{counts['print_count']}" if action == 'PRINT_DIALOG' else f"PDF download request #{counts['pdf_download_count']}"
    event = ActivityService.log(db=db, user=user, action=ACTIONS[action], entity_type=kind, entity_id=document_id,
        summary=f'{event_label} · {number} · revision {revision_number}'[:255], document_number=number,
        document_status=getattr(document, 'status', None), document_type=kind, details=details)
    if document is not None:
        event.location_id = document.location_id
    event.actor_name = details['actor_name'] or event.actor_name
    db.flush()
    if commit:
        db.commit()
    return details

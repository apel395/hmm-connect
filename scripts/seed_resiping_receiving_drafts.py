#!/usr/bin/env python3
"""Selectively seed 2026 receiving DRAFTS. Never posts or seeds invoices."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from prepare_resiping_transactions import extract_transactions, validate_database, db_catalog, money


def plan_receiving(report, locations):
    groups=defaultdict(list);skipped=[]
    location_by_id={x['id']:x for x in locations}
    for inv in report['invoices']:
        if inv['status']=='EXCLUDED_PRE_2026':continue
        for line in inv['lines']:
            reasons=list(line['errors'])
            for field in ('supplier_id','location_id','department_id'):
                if not inv.get(field):reasons.append('MISSING_'+field.upper())
            day=line.get('received_date');treatment=line.get('treatment')
            if day is None or day.year!=2026:reasons.append('REQUIRES_EXACT_2026_DATE')
            if treatment not in ('STOCK','DIRECT_USE'):reasons.append('UNSUPPORTED_RECEIVING_TREATMENT')
            reasons.extend(e for e in inv['errors'] if e.startswith(('ACCOUNTING_PERIOD_NOT_OPEN:','BACKDATE_NOT_ALLOWED:','INVALID_SUPPLIER_LITERAL','INVALID_LOCATION_LITERAL')))
            if line.get('tax') is None:reasons.append('UNRESOLVED_TAX')
            if reasons:
                skipped.append({'invoice_key':inv['key'],'row':line['row'],'item':line['item'],'reasons':sorted(set(reasons))});continue
            key=(inv['key'],day,treatment)
            groups[key].append((inv,line))
    planned=[]
    for (key,day,treatment),members in sorted(groups.items()):
        inv=members[0][0];lines=[x[1] for x in members]
        loc=location_by_id.get(inv['location_id'],{})
        planned.append({'number':f'RSP-{key}-{day:%Y%m%d}-{treatment}',
            'invoice_key':key,'source_supplier':inv['supplier'],'source_location':inv['location'],
            'supplier_id':inv['supplier_id'],'location_id':inv['location_id'],'department_id':inv['department_id'],
            'business_unit_id':loc.get('business_unit_id'),'date':day,'treatment':treatment,
            'warehouse_id':lines[0].get('warehouse_id') if treatment=='STOCK' else None,
            'subtotal':sum((l['net'] for l in lines),Decimal(0)),
            'tax_amount':sum((l['tax'] for l in lines),Decimal(0)),
            'lines':[{'row':l['row'],'product_id':l['product_id'],'quantity':l['quantity'],'unit_cost':l['unit_price'],
                      'tax_amount':l['tax'],'raw_tax':l['raw_tax'],'raw_date':l['raw_received_date']} for l in lines]})
    return {'groups':planned,'skipped':skipped,'source_sha256':report['source_sha256']}


def signature(group):
    return sha256(json.dumps(group,sort_keys=True,default=str).encode()).hexdigest()


def save_drafts(db, plan, apply=False):
    from app.models.goods_receipt import GoodsReceipt,GoodsReceiptItem
    from app.models.audit_log import AuditLog
    counts=Counter()
    for group in plan['groups']:
        if group['date'].year!=2026:raise ValueError('Non-2026 receiving refused')
        fingerprint=signature(group)
        existing=db.query(GoodsReceipt).filter_by(receipt_number=group['number']).one_or_none()
        if existing:
            try:meta=json.loads(existing.notes or '{}')
            except ValueError:raise ValueError('Existing receipt reference is not this import')
            expected=sorted((l['product_id'],l['quantity'],l['unit_cost'],l['tax_amount']) for l in group['lines'])
            actual=sorted((l.product_id,l.quantity,l.unit_cost,l.tax_amount) for l in existing.items)
            if (meta.get('fingerprint')!=fingerprint or expected!=actual or existing.status not in ('DRAFT','POSTED')
                or existing.supplier_id!=group['supplier_id'] or existing.location_id!=group['location_id']
                or existing.department_id!=group['department_id'] or existing.warehouse_id!=group['warehouse_id']
                or existing.received_at.date()!=group['date'] or existing.subtotal!=group['subtotal']
                or existing.tax_amount!=group['tax_amount']
                or existing.total_amount!=group['subtotal']+group['tax_amount']
                or existing.business_unit_id!=group['business_unit_id']
                or existing.destination_type!=('INVENTORY' if group['treatment']=='STOCK' else 'DIRECT_USE')):
                raise ValueError(f"{group['number']} changed; import refused")
            counts['already_seeded']+=1;continue
        counts['new_drafts']+=1;counts['new_rows']+=len(group['lines'])
        if not apply:continue
        meta={'source_sha256':plan['source_sha256'],'fingerprint':fingerprint,'source_invoice_key':group['invoice_key'],
              'source_supplier':group['source_supplier'],'work_location':group['source_location'],
              'tax_policy':'IMPORT_ENTERED_TAX_ONLY','source_rows':group['lines'],
              'scope':'Selected receiving rows only; supplier invoice not imported.'}
        receipt=GoodsReceipt(receipt_number=group['number'],status='DRAFT',source_type='HISTORICAL_IMPORT',
            external_reference=group['number'],supplier_id=group['supplier_id'],location_id=group['location_id'],
            department_id=group['department_id'],business_unit_id=group['business_unit_id'],
            warehouse_id=group['warehouse_id'],destination_type='INVENTORY' if group['treatment']=='STOCK' else 'DIRECT_USE',
            received_at=datetime.combine(group['date'],datetime.min.time(),tzinfo=timezone.utc),
            subtotal=group['subtotal'],tax_amount=group['tax_amount'],total_amount=group['subtotal']+group['tax_amount'],
            notes=json.dumps(meta,default=str),imported_at=datetime.now(timezone.utc))
        for line in group['lines']:
            base=line['quantity']*line['unit_cost'];tax=line['tax_amount']
            receipt.items.append(GoodsReceiptItem(product_id=line['product_id'],quantity=line['quantity'],unit_cost=line['unit_cost'],
                tax_amount=tax,is_taxable=tax>0,tax_rate=money(tax*100/base) if base else Decimal(0)))
        db.add(receipt);db.flush()
        db.add(AuditLog(action='RESIPING_RECEIVING_DRAFT_SEEDED',entity_type='GOODS_RECEIPT',entity_id=receipt.id,
            summary=f"Historical receiving draft {receipt.receipt_number}",
            details=json.loads(json.dumps(meta,default=str)),source='SYSTEM',
            document_number=receipt.receipt_number,document_status='DRAFT',document_type='GOODS_RECEIPT'))
    return dict(counts)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    from sqlalchemy import text
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        try:
            if args.apply:db.execute(text('SELECT pg_advisory_xact_lock(4742477,20261007)'))
            else:db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            db.execute(text("SET LOCAL statement_timeout = '60s'"))
            report=extract_transactions(args.file);catalog=db_catalog(db)
            # Own seed receipts are verified by exact number, fingerprint and values.
            catalog['receipts']=[r for r in catalog['receipts'] if not r['receipt_number'].startswith('RSP-INV-')]
            validate_database(report,catalog)
            locations=[dict(r) for r in db.execute(text('SELECT id,business_unit_id FROM locations')).mappings()]
            plan=plan_receiving(report,locations)
            counts=save_drafts(db,plan,args.apply)
            plan['mode']='APPLY' if args.apply else 'DRY_RUN';plan['counts']=counts
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(plan,indent=2,default=str),encoding='utf-8')
            if args.apply:db.commit()
            else:db.rollback()
        except Exception:
            db.rollback();raise
    print(json.dumps({'mode':plan['mode'],'source_sha256':plan['source_sha256'],'counts':counts,
        'skipped_rows':len(plan['skipped']),'skip_reasons':dict(Counter(e for r in plan['skipped'] for e in r['reasons']))},indent=2))
    print('COMMITTED receiving DRAFTS only.' if args.apply else 'DRY RUN: no writes. Use --apply to create eligible drafts.')
    print('No invoices, stock movements, journals, GL, AP or opening balances created. Full report:',args.output)


if __name__=='__main__':main()

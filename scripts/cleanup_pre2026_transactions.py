"""One-time HMM Connect pre-2026 transaction cleanup. Run on EC2 only."""

from datetime import date
from decimal import Decimal
from pathlib import Path
import argparse

from sqlalchemy import text
from app.core.database import engine

BACKUP = Path('/opt/hmm-connect/private-backups/before-2025-cleanup-20260928T064541Z.dump')
CUTOFF = date(2026, 1, 1)


def scalar(db, sql, **params):
    return db.execute(text(sql), params).scalar()


def require(test, message):
    if not test:
        raise RuntimeError(message)


def run(*, apply: bool):
    require(BACKUP.is_file() and BACKUP.stat().st_size > 500000,
            f'Verified backup missing: {BACKUP}')
    with engine.connect() as db:
        tx = db.begin()
        try:
            db.exec_driver_sql('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
            db.exec_driver_sql('SELECT pg_advisory_xact_lock(20260928, 2025)')
            db.exec_driver_sql('LOCK TABLE goods_receipts, goods_receipt_items, supplier_invoices, '
                               'supplier_invoice_lines, stock_movements, inventory, journal_entries, '
                               'journal_lines, general_ledger, account_payables, payments, '
                               'payment_allocations, payment_voucher_allocations, '
                               'supplier_adjustments, document_attachments IN SHARE ROW EXCLUSIVE MODE')
            counts = {
                'receipts': scalar(db, 'SELECT count(*) FROM goods_receipts WHERE received_at < :cutoff', cutoff=CUTOFF),
                'invoices': scalar(db, 'SELECT count(*) FROM supplier_invoices WHERE invoice_date < :cutoff', cutoff=CUTOFF),
                'journals': scalar(db, 'SELECT count(*) FROM journal_entries WHERE posting_date < :cutoff', cutoff=CUTOFF),
                'payments': scalar(db, 'SELECT count(*) FROM payments WHERE payment_date < :cutoff', cutoff=CUTOFF),
            }
            print('Target:', counts)
            require(counts == {'receipts': 83, 'invoices': 27, 'journals': 110, 'payments': 0},
                    'Target changed since review; transaction rolled back')
            require(scalar(db, """SELECT count(*) FROM journal_entries WHERE posting_date < :cutoff
                AND (status <> 'POSTED' OR reference_type NOT IN ('GOODS_RECEIPT','SUPPLIER_INVOICE'))""",
                cutoff=CUTOFF) == 0, 'Unexpected 2025 journal; rolled back')
            require(scalar(db, """SELECT count(*) FROM supplier_invoice_lines il
                JOIN goods_receipt_items gi ON gi.id=il.goods_receipt_item_id
                JOIN goods_receipts g ON g.id=gi.goods_receipt_id
                JOIN supplier_invoices i ON i.id=il.supplier_invoice_id
                WHERE g.received_at < :cutoff AND i.invoice_date >= :cutoff""",
                cutoff=CUTOFF) == 0, '2026 invoice depends on 2025 receipt; rolled back')
            require(scalar(db, """SELECT count(*) FROM payment_voucher_allocations a
                JOIN supplier_invoices i ON i.id=a.supplier_invoice_id
                WHERE i.invoice_date < :cutoff""", cutoff=CUTOFF) == 0,
                'Payment voucher depends on 2025 invoice; rolled back')
            require(scalar(db, """SELECT count(*) FROM supplier_adjustments a
                JOIN supplier_invoices i ON i.id=a.supplier_invoice_id
                WHERE i.invoice_date < :cutoff""", cutoff=CUTOFF) == 0,
                'Supplier adjustment depends on 2025 invoice; rolled back')
            require(scalar(db, """SELECT count(*) FROM goods_receipt_items gi
                JOIN goods_receipts g ON g.id=gi.goods_receipt_id
                WHERE g.received_at < :cutoff AND gi.purchase_order_item_id IS NOT NULL""",
                cutoff=CUTOFF) == 0, 'PO-linked receipt found; rolled back')
            require(scalar(db, """SELECT count(*) FROM stock_movements m
                JOIN goods_receipts g ON g.id=m.goods_receipt_id
                WHERE g.received_at < :cutoff
                  AND (m.movement_type <> 'IN' OR m.reference_type <> 'GOODS_RECEIPT')""",
                cutoff=CUTOFF) == 0, 'Nonstandard historical stock movement; rolled back')
            require(scalar(db, """SELECT count(*) FROM (
                SELECT m.product_id, m.warehouse_id FROM stock_movements m
                JOIN goods_receipts g ON g.id=m.goods_receipt_id
                LEFT JOIN inventory i ON i.product_id=m.product_id AND i.warehouse_id=m.warehouse_id
                WHERE g.received_at < :cutoff
                GROUP BY m.product_id,m.warehouse_id,i.quantity
                HAVING COALESCE(i.quantity,0) < sum(m.quantity)) t""",
                cutoff=CUTOFF) == 0, 'Removing historical stock would make inventory negative; rolled back')
            allocations = db.execute(text("""SELECT p.id,p.payment_number,a.id,a.allocated_amount
                FROM payment_allocations a JOIN supplier_invoices i ON i.id=a.supplier_invoice_id
                JOIN payments p ON p.id=a.payment_id WHERE i.invoice_date < :cutoff
                ORDER BY a.id"""), {'cutoff': CUTOFF}).all()
            print('2026 allocations to detach:', [tuple(a) for a in allocations])
            require(len(allocations) == 1 and allocations[0][0] == 46
                    and allocations[0][2] == 48
                    and allocations[0][3] == Decimal('7316281.00'),
                    'Payment allocation changed; rolled back')
            opening = scalar(db, 'SELECT count(*) FROM opening_balances WHERE fiscal_year=2026')
            payment_journal = scalar(db, "SELECT count(*) FROM journal_entries WHERE id=1344 AND status='POSTED' AND posting_date >= :cutoff", cutoff=CUTOFF)
            require(payment_journal == 1, '2026 payment journal missing; rolled back')
            payment = db.execute(text('SELECT amount,status,journal_entry_id FROM payments WHERE id=46')).one()
            require(payment.amount == Decimal('7316281.00') and payment.status == 'POSTED'
                    and payment.journal_entry_id == 1344, '2026 payment changed; rolled back')
            require(scalar(db, """SELECT count(*) FROM document_attachments a WHERE
                (a.entity_type='GOODS_RECEIPT' AND EXISTS
                  (SELECT 1 FROM goods_receipts g WHERE g.id=a.entity_id AND g.received_at < :cutoff))
                OR (a.entity_type='SUPPLIER_INVOICE' AND EXISTS
                  (SELECT 1 FROM supplier_invoices i WHERE i.id=a.entity_id AND i.invoice_date < :cutoff))""",
                cutoff=CUTOFF) == 0, 'Historical documents have attachments; rolled back')
            require(scalar(db, """SELECT count(*) FROM journal_entries j
                WHERE j.posting_date >= :cutoff AND (
                 (j.reference_type='GOODS_RECEIPT' AND EXISTS
                   (SELECT 1 FROM goods_receipts g WHERE g.id=j.reference_id AND g.received_at < :cutoff))
                 OR (j.reference_type='SUPPLIER_INVOICE' AND EXISTS
                   (SELECT 1 FROM supplier_invoices i WHERE i.id=j.reference_id AND i.invoice_date < :cutoff)))""",
                cutoff=CUTOFF) == 0, '2026 journal references historical document; rolled back')

            affected = db.execute(text("""SELECT m.product_id,m.warehouse_id,sum(m.quantity) old_qty,
                i.quantity current_qty FROM stock_movements m
                JOIN goods_receipts g ON g.id=m.goods_receipt_id
                JOIN inventory i ON i.product_id=m.product_id AND i.warehouse_id=m.warehouse_id
                WHERE g.received_at < :cutoff
                GROUP BY m.product_id,m.warehouse_id,i.quantity"""), {'cutoff': CUTOFF}).all()
            print('Affected inventory rows:', len(affected),
                  'historical quantity:', sum((a.old_qty for a in affected), Decimal(0)))
            removed_allocations = db.execute(text("""DELETE FROM payment_allocations
                WHERE supplier_invoice_id IN (SELECT id FROM supplier_invoices WHERE invoice_date < :cutoff)"""),
                {'cutoff': CUTOFF}).rowcount
            detached_payable = db.execute(text("""UPDATE payments SET account_payable_id=NULL
                WHERE account_payable_id IN
                (SELECT id FROM account_payables WHERE invoice_date < :cutoff OR
                 invoice_number IN (SELECT internal_invoice_number FROM supplier_invoices WHERE invoice_date < :cutoff))"""),
                {'cutoff': CUTOFF}).rowcount
            inventory_updated = db.execute(text("""WITH old AS (
                SELECT m.product_id,m.warehouse_id,sum(m.quantity) AS qty
                FROM stock_movements m JOIN goods_receipts g ON g.id=m.goods_receipt_id
                WHERE g.received_at < :cutoff GROUP BY m.product_id,m.warehouse_id)
                UPDATE inventory i SET quantity=i.quantity-old.qty,
                average_cost=CASE WHEN i.quantity-old.qty=0 THEN 0 ELSE i.average_cost END
                FROM old WHERE i.product_id=old.product_id AND i.warehouse_id=old.warehouse_id"""),
                {'cutoff': CUTOFF}).rowcount
            deleted_movements = db.execute(text("""DELETE FROM stock_movements m USING goods_receipts g
                WHERE m.goods_receipt_id=g.id AND g.received_at < :cutoff"""),
                {'cutoff': CUTOFF}).rowcount
            deleted_gl = db.execute(text('DELETE FROM general_ledger WHERE posting_date < :cutoff'),
                                    {'cutoff': CUTOFF}).rowcount
            deleted_payables = db.execute(text("""DELETE FROM account_payables WHERE invoice_date < :cutoff OR
                invoice_number IN (SELECT internal_invoice_number FROM supplier_invoices WHERE invoice_date < :cutoff)"""),
                                          {'cutoff': CUTOFF}).rowcount
            db.execute(text("""DELETE FROM supplier_invoice_lines WHERE supplier_invoice_id IN
                (SELECT id FROM supplier_invoices WHERE invoice_date < :cutoff)"""), {'cutoff': CUTOFF})
            deleted_invoices = db.execute(text('DELETE FROM supplier_invoices WHERE invoice_date < :cutoff'),
                                          {'cutoff': CUTOFF}).rowcount
            db.execute(text("""DELETE FROM journal_lines WHERE journal_entry_id IN
                (SELECT id FROM journal_entries WHERE posting_date < :cutoff)"""), {'cutoff': CUTOFF})
            deleted_journals = db.execute(text('DELETE FROM journal_entries WHERE posting_date < :cutoff'),
                                          {'cutoff': CUTOFF}).rowcount
            db.execute(text("""DELETE FROM goods_receipt_items WHERE goods_receipt_id IN
                (SELECT id FROM goods_receipts WHERE received_at < :cutoff)"""), {'cutoff': CUTOFF})
            deleted_receipts = db.execute(text('DELETE FROM goods_receipts WHERE received_at < :cutoff'),
                                          {'cutoff': CUTOFF}).rowcount
            result = dict(receipts=deleted_receipts, invoices=deleted_invoices,
                          journals=deleted_journals, general_ledger=deleted_gl,
                          stock_movements=deleted_movements, inventory_rows=inventory_updated,
                          account_payables=deleted_payables, payment_allocations=removed_allocations,
                          payment_payable_links=detached_payable)
            print('Deleted / updated:', result)
            require((deleted_receipts,deleted_invoices,deleted_journals,removed_allocations)
                    == (83,27,110,1), 'Unexpected deletion count; rolled back')
            require(inventory_updated == len(affected), 'Inventory row count changed; rolled back')
            require(scalar(db, 'SELECT count(*) FROM opening_balances WHERE fiscal_year=2026') == opening,
                    '2026 opening entries changed; rolled back')
            require(scalar(db, 'SELECT count(*) FROM general_ledger WHERE posting_date < :cutoff',
                           cutoff=CUTOFF) == 0, 'Historical GL still present; rolled back')
            require(scalar(db, 'SELECT count(*) FROM payments WHERE id=46 AND status=\'POSTED\'') == 1,
                    '2026 payment missing; rolled back')
            require(scalar(db, "SELECT count(*) FROM journal_entries WHERE id=1344 AND status='POSTED'") == 1,
                    '2026 payment journal missing; rolled back')
            require(all(scalar(db, f'SELECT count(*) FROM {table} WHERE {field} < :cutoff', cutoff=CUTOFF) == 0
                        for table, field in (('goods_receipts','received_at'),
                                             ('supplier_invoices','invoice_date'),
                                             ('journal_entries','posting_date'),
                                             ('account_payables','invoice_date'))),
                    'Pre-2026 rows remain; rolled back')
            db.execute(text("""INSERT INTO audit_logs
                (action,entity_type,summary,details,source)
                VALUES ('PRE2026_CLEANUP','SYSTEM',:summary,CAST(:details AS json),'SYSTEM')"""),
                {'summary':'Removed pre-2026 receiving, invoices, stock and journal activity',
                 'details':'{"backup":"before-2025-cleanup-20260928T064541Z.dump",'
                           '"receipts":83,"invoices":27,"journals":110,'
                           '"payment_46_allocation_detached":true,"opening_unchanged":true}'})
            if apply:
                tx.commit()
                print('COMMITTED. Payment 46 preserved; opening balances untouched.')
            else:
                tx.rollback()
                print('DRY RUN succeeded. All changes rolled back. Run with --apply to commit.')
        except Exception:
            tx.rollback()
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Commit the validated deletion')
    run(apply=parser.parse_args().apply)

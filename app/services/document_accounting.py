"""Subledger visibility follows recognized open journals without changing document status."""
from sqlalchemy import and_, or_, select
from app.models.journal_entry import JournalEntry
from app.models.supplier_invoice import SupplierInvoice
from app.models.payment import Payment
from app.models.supplier_adjustment import SupplierAdjustment
from app.services.journal_recognition import recognized_journal_filter


def _source_journal(source, source_id, model):
    return select(JournalEntry.id).where(JournalEntry.reference_type==source,JournalEntry.reference_id==source_id,
        recognized_journal_filter()).correlate(model).exists()


def accounted_invoice_filter():
    return or_(SupplierInvoice.status=='POSTED',and_(SupplierInvoice.status=='VERIFIED',
        _source_journal('SUPPLIER_INVOICE',SupplierInvoice.id,SupplierInvoice)))


def accounted_payment_filter():
    return or_(Payment.status=='POSTED',and_(Payment.status=='APPROVED',
        select(JournalEntry.id).where(JournalEntry.id==Payment.journal_entry_id,JournalEntry.reference_type=='SUPPLIER_PAYMENT',
            JournalEntry.reference_id==Payment.id,recognized_journal_filter()).correlate(Payment).exists()))


def accounted_adjustment_filter():
    return or_(SupplierAdjustment.status=='POSTED',and_(SupplierAdjustment.status=='DRAFT',
        _source_journal('SUPPLIER_ADJUSTMENT',SupplierAdjustment.id,SupplierAdjustment)))


def invoice_is_accounted(db, invoice):
    return bool(db.query(SupplierInvoice.id).filter(SupplierInvoice.id==invoice.id,accounted_invoice_filter()).first())

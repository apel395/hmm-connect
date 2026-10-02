"""Idempotent fixed-asset intake from posted supplier invoice lines."""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.fixed_asset import FixedAsset, FixedAssetCategory, FixedAssetMovement
from app.models.journal_entry import JournalEntry
from app.models.location import Location
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.services.audit import record_audit
from app.services.document_number import next_document_number


RECLASS_TYPE = "SUPPLIER_INVOICE_ASSET_RECLASS"


def register_invoice_asset(
    db: Session, *, invoice: SupplierInvoice, line: SupplierInvoiceLine,
    account_id: int, journal: JournalEntry, user,
) -> FixedAsset:
    """Store the asset source once. Accounting was already posted by the journal."""
    db.query(SupplierInvoice.id).filter(SupplierInvoice.id == invoice.id).with_for_update().one()
    if invoice.status != "POSTED" or journal.status != "POSTED":
        raise HTTPException(409, "A posted invoice and accounting journal are required for asset registration")
    existing = db.query(FixedAsset).filter(
        FixedAsset.source_invoice_line_id == line.id,
    ).with_for_update().one_or_none()
    if existing:
        if existing.asset_account_id != account_id or Decimal(existing.acquisition_cost) != Decimal(line.line_amount):
            raise HTTPException(409, "Existing fixed asset differs from its posted invoice line")
        if existing.status == "SOURCE_UNPOSTED":
            existing.status = "DRAFT" if existing.asset_category_id else "PENDING_SETUP"
        return existing
    if invoice.goods_receipt_id or line.goods_receipt_item_id:
        raise HTTPException(409, "Receipt-backed assets must use the receiving asset flow")
    if Decimal(line.line_amount or 0) <= 0:
        raise HTTPException(409, "Fixed asset invoice line has no cost")

    location_id = invoice.location_id or journal.location_id
    location = db.get(Location, location_id) if location_id else None
    business_unit_id = invoice.business_unit_id or journal.business_unit_id or (
        location.business_unit_id if location else None
    )
    if not business_unit_id:
        raise HTTPException(409, "Invoice asset requires a business unit before registration")
    categories = db.query(FixedAssetCategory).filter(
        FixedAssetCategory.is_active.is_(True),
        FixedAssetCategory.asset_account_id == account_id,
    ).limit(2).all()
    category = categories[0] if len(categories) == 1 else None
    cost = Decimal(line.line_amount)
    residual = (
        (cost * Decimal(category.default_residual_percentage or 0) / Decimal("100")).quantize(Decimal("0.01"))
        if category else Decimal("0")
    )
    asset = FixedAsset(
        asset_number=next_document_number(db, "FA"),
        asset_name=(line.product.name if line.product else line.description or f"Invoice line {line.id}")[:180],
        asset_category_id=category.id if category else None,
        description=line.description,
        acquisition_date=invoice.invoice_date,
        acquisition_cost=cost,
        residual_value=residual,
        useful_life_months=category.default_useful_life_months if category else None,
        accumulated_depreciation=Decimal("0"),
        net_book_value=cost,
        status="DRAFT" if category else "PENDING_SETUP",
        business_unit_id=business_unit_id,
        location_id=location_id,
        department_id=line.department_id or invoice.department_id,
        supplier_id=invoice.supplier_id,
        purchase_invoice_id=invoice.id,
        source_invoice_line_id=line.id,
        purchase_order_id=invoice.purchase_order_id,
        asset_account_id=account_id,
        accumulated_depreciation_account_id=category.accumulated_depreciation_account_id if category else None,
        depreciation_expense_account_id=category.depreciation_expense_account_id if category else None,
        disposal_gain_account_id=category.disposal_gain_account_id if category else None,
        disposal_loss_account_id=category.disposal_loss_account_id if category else None,
        source_type="SUPPLIER_INVOICE",
        external_reference=invoice.internal_invoice_number,
        notes=f"Registered from posted invoice line {line.id}; no extra acquisition journal.",
        created_by_id=user.id,
    )
    db.add(asset)
    db.flush()
    db.add(FixedAssetMovement(
        fixed_asset_id=asset.id, movement_type="ACQUISITION",
        to_business_unit_id=business_unit_id, to_location_id=location_id,
        to_department_id=asset.department_id, movement_date=invoice.invoice_date,
        reference_number=invoice.internal_invoice_number, created_by_id=user.id,
    ))
    record_audit(
        db, user, "FIXED_ASSET_REGISTERED", "FIXED_ASSET",
        f"Registered {asset.asset_number} from invoice {invoice.internal_invoice_number} line {line.id}",
        entity_id=asset.id, reference_document=invoice.internal_invoice_number,
        after_data={"source_invoice_line_id": line.id, "journal_id": journal.id, "account_id": account_id},
    )
    return asset


def sync_posted_invoice_assets(db: Session, *, user) -> int:
    """Catch source journals posted before automatic registration was deployed."""
    from app.models.chart_of_account import ChartOfAccount

    registered = 0
    corrections = db.query(JournalEntry).filter(
        JournalEntry.document_type == RECLASS_TYPE,
        JournalEntry.reference_type == "MANUAL",
        JournalEntry.status == "POSTED",
    ).order_by(JournalEntry.id).all()
    for journal in corrections:
        line = db.get(SupplierInvoiceLine, journal.reference_id)
        invoice = line.invoice if line else None
        if not invoice or invoice.status != "POSTED":
            continue
        debit = next((item for item in journal.lines if Decimal(item.debit or 0) > 0), None)
        account = db.get(ChartOfAccount, debit.account_id) if debit else None
        if not account or not account.account_number.startswith("100-600-"):
            continue
        if not db.query(FixedAsset.id).filter(FixedAsset.source_invoice_line_id == line.id).first():
            register_invoice_asset(db, invoice=invoice, line=line, account_id=account.id, journal=journal, user=user)
            registered += 1

    invoices = db.query(SupplierInvoice).filter(
        SupplierInvoice.status == "POSTED", SupplierInvoice.goods_receipt_id.is_(None),
    ).order_by(SupplierInvoice.id).all()
    for invoice in invoices:
        source = db.query(JournalEntry).filter(
            JournalEntry.reference_type == "SUPPLIER_INVOICE",
            JournalEntry.reference_id == invoice.id,
            JournalEntry.status == "POSTED",
        ).order_by(JournalEntry.id.desc()).first()
        if not source:
            continue
        for line in invoice.lines:
            if line.goods_receipt_item_id or not line.account_id:
                continue
            account = db.get(ChartOfAccount, line.account_id)
            if not account or not account.account_number.startswith("100-600-"):
                continue
            if not db.query(FixedAsset.id).filter(FixedAsset.source_invoice_line_id == line.id).first():
                register_invoice_asset(db, invoice=invoice, line=line, account_id=account.id, journal=source, user=user)
                registered += 1
    return registered

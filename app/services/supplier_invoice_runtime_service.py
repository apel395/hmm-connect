from fastapi import HTTPException

from app.services.supplier_invoice_accounting import accounting_state
from app.services.supplier_invoice_service import SupplierInvoiceService as BaseSupplierInvoiceService


class SupplierInvoiceService(BaseSupplierInvoiceService):
    """Runtime supplier-invoice policy built on the canonical tax-aware matching engine."""

    def serialize(self, invoice):
        data = super().serialize(invoice)
        data.update(accounting_state(self.db, invoice))
        data["supplier_is_pkp"] = bool(invoice.supplier.is_pkp) if invoice.supplier else False
        return data

    def match_summary(self, invoice):
        # Keep a single authoritative implementation for quantity, price, UOM,
        # supplier and PPN matching. The previous runtime-specific copy had
        # drifted and silently omitted tax applicability/rate checks.
        return super().match_summary(invoice)

    def assert_match(self, invoice):
        summary = self.match_summary(invoice)
        if not summary["can_verify"]:
            detail = summary["issues"][0] if summary["issues"] else "Three-way matching failed"
            raise HTTPException(status_code=409, detail=f"Three-way match required: {detail}")
        return summary

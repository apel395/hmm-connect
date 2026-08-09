from decimal import Decimal

from fastapi import HTTPException

from app.services.supplier_invoice_service import SupplierInvoiceService as BaseSupplierInvoiceService

ZERO = Decimal("0")
PRICE_TOLERANCE = Decimal("0.01")


class SupplierInvoiceService(BaseSupplierInvoiceService):
    """Hotel AP matching policy: posted Goods Receipt ↔ Supplier Invoice only."""

    def match_summary(self, invoice):
        if not invoice.goods_receipt_id:
            return {
                "status": "NOT_APPLICABLE",
                "can_verify": True,
                "message": "Direct supplier invoice; receipt matching is not applicable.",
                "supplier_match": True,
                "line_count": len(invoice.lines),
                "matched_lines": len(invoice.lines),
                "issues": [],
                "lines": [],
            }

        receipt = invoice.goods_receipt
        issues: list[str] = []
        line_results = []
        receipt_supplier_id = receipt.supplier_id or (
            receipt.purchase_order.supplier_id
            if receipt and receipt.purchase_order
            else None
        )
        supplier_match = bool(receipt and invoice.supplier_id == receipt_supplier_id)
        if not supplier_match:
            issues.append("Supplier does not match the goods receipt.")
        if not receipt or receipt.status != "POSTED":
            issues.append("Goods receipt must be posted before invoice verification.")

        receipt_items = {item.id: item for item in receipt.items} if receipt else {}
        for line in invoice.lines:
            receipt_item = receipt_items.get(line.goods_receipt_item_id) if line.goods_receipt_item_id else None
            line_issues = []
            if not receipt_item:
                line_issues.append("Invoice line is not linked to the selected receipt line.")
            elif line.product_id and receipt_item.product_id != line.product_id:
                line_issues.append("Product does not match the receipt line.")

            received_quantity = Decimal(receipt_item.quantity) if receipt_item else ZERO
            previously_invoiced = self._previous_invoiced_quantity(invoice, receipt_item.id) if receipt_item else ZERO
            available_quantity = max(ZERO, received_quantity - previously_invoiced)
            invoice_quantity = Decimal(line.quantity)
            if receipt_item and invoice_quantity > available_quantity:
                line_issues.append(
                    f"Invoice quantity {invoice_quantity} exceeds uninvoiced received quantity {available_quantity}."
                )

            receipt_unit_cost = Decimal(receipt_item.unit_cost) if receipt_item else None
            invoice_unit_price = Decimal(line.unit_price)
            price_difference = (
                abs(invoice_unit_price - receipt_unit_cost)
                if receipt_unit_cost is not None
                else None
            )
            if receipt_unit_cost is not None and price_difference > PRICE_TOLERANCE:
                line_issues.append(
                    f"Invoice unit price {invoice_unit_price} differs from received unit cost {receipt_unit_cost}."
                )

            receipt_uom = receipt_item.product.uom if receipt_item and receipt_item.product else None
            if line.uom and receipt_uom and line.uom.strip().upper() != receipt_uom.strip().upper():
                line_issues.append(
                    f"Invoice UOM {line.uom} differs from receipt UOM {receipt_uom}."
                )

            line_results.append({
                "invoice_line_id": line.id,
                "product_id": line.product_id,
                "product_code": line.product.code if line.product else None,
                "product_name": line.product.name if line.product else line.description,
                "receipt_item_id": receipt_item.id if receipt_item else None,
                "purchase_order_item_id": line.purchase_order_item_id,
                "received_quantity": received_quantity,
                "previously_invoiced_quantity": previously_invoiced,
                "available_quantity": available_quantity,
                "invoice_quantity": invoice_quantity,
                "po_unit_price": None,
                "receipt_unit_cost": receipt_unit_cost,
                "invoice_unit_price": invoice_unit_price,
                "price_difference": price_difference,
                "uom": line.uom,
                "reference_uom": receipt_uom,
                "status": "MATCHED" if not line_issues else "MISMATCH",
                "issues": line_issues,
            })
            issues.extend(
                f"{line.product.name if line.product else line.description}: {issue}"
                for issue in line_issues
            )

        matched_lines = sum(1 for line in line_results if line["status"] == "MATCHED")
        status = "MATCHED" if supplier_match and not issues and len(line_results) == len(invoice.lines) else "MISMATCH"
        return {
            "status": status,
            "can_verify": status == "MATCHED",
            "message": "Goods receipt and supplier invoice match." if status == "MATCHED" else "Resolve receipt/invoice matching exceptions before verification.",
            "supplier_match": supplier_match,
            "line_count": len(invoice.lines),
            "matched_lines": matched_lines,
            "issues": issues,
            "lines": line_results,
        }

    def assert_match(self, invoice):
        summary = self.match_summary(invoice)
        if not summary["can_verify"]:
            detail = summary["issues"][0] if summary["issues"] else "Receipt/invoice matching failed"
            raise HTTPException(status_code=409, detail=f"Receipt match required: {detail}")
        return summary

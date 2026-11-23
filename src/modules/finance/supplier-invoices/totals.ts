import type { InvoiceLine, InvoicePayload } from "./api";

const num = (value: unknown) => Number(value || 0);

export const roundMoney = (value: unknown) => Math.round((num(value) + Number.EPSILON) * 100) / 100;

export function computeInvoiceTotals(lines: InvoiceLine[] = [], values: Record<string, unknown> = {}) {
  const subtotal = lines.reduce((sum, line) => sum + num(line.quantity) * num(line.unit_price), 0);
  const tax = lines.reduce((sum, line) => {
    const base = num(line.quantity) * num(line.unit_price);
    return sum + (line.is_taxable ? base * num(line.tax_rate) / 100 : 0);
  }, 0);
  const total = subtotal
    - num(values.discount_amount)
    + tax
    - num(values.withholding_tax_amount)
    + num(values.shipping_fee_amount)
    + num(values.admin_fee_amount)
    + num(values.other_fee_amount);
  return { subtotal: roundMoney(subtotal), tax: roundMoney(tax), total: roundMoney(total) };
}

/**
 * Keep the supplier's printed document total in step with a PPN correction,
 * but only when it was tracking the old calculated total. A manually edited
 * document total is left alone so AP can investigate a genuine difference.
 */
export function withSyncedDocumentTotal(
  form: Record<string, any>,
  lines: InvoiceLine[],
  previousTotal: number,
  extra: Record<string, unknown> = {},
) {
  const nextForm = { ...form, ...extra, lines };
  const nextTotal = computeInvoiceTotals(lines, nextForm).total;
  const currentDocumentTotal = num(form.supplier_document_total);
  const wasTrackingCalculation = !currentDocumentTotal || Math.abs(currentDocumentTotal - roundMoney(previousTotal)) < 0.01;
  return {
    ...nextForm,
    supplier_document_total: wasTrackingCalculation ? (nextTotal || null) : currentDocumentTotal,
  };
}

/**
 * Explicit allowlist: server-derived fields (total_amount, subtotal, balance,
 * status, ids, display names...) must never be echoed back. Pydantic derives
 * those from lines, and stale values are exactly what breaks PPN corrections.
 */
export function buildInvoicePayload(form: Record<string, any>, totals: { tax: number }): InvoicePayload {
  return {
    supplier_invoice_number: String(form.supplier_invoice_number || ""),
    supplier_document_total: form.supplier_document_total === null || form.supplier_document_total === "" || form.supplier_document_total === undefined
      ? null
      : Number(form.supplier_document_total),
    supplier_document_url: form.supplier_document_url || null,
    shipping_fee_amount: num(form.shipping_fee_amount),
    admin_fee_amount: num(form.admin_fee_amount),
    other_fee_amount: num(form.other_fee_amount),
    other_fee_description: form.other_fee_description || null,
    shipping_fee_account_id: form.shipping_fee_account_id ?? null,
    admin_fee_account_id: form.admin_fee_account_id ?? null,
    other_fee_account_id: form.other_fee_account_id ?? null,
    supplier_id: Number(form.supplier_id),
    invoice_date: String(form.invoice_date || ""),
    received_date: form.received_date || null,
    due_date: form.due_date || null,
    purchase_order_id: form.purchase_order_id ?? null,
    goods_receipt_id: form.goods_receipt_id ?? null,
    business_unit_id: form.business_unit_id ?? null,
    department_id: form.department_id ?? null,
    location_id: form.location_id ?? null,
    currency: form.currency || "IDR",
    discount_amount: num(form.discount_amount),
    withholding_tax_amount: num(form.withholding_tax_amount),
    tax_amount: roundMoney(totals.tax),
    tax_invoice_number: form.tax_invoice_number || null,
    tax_invoice_date: form.tax_invoice_date || null,
    notes: form.notes || null,
    source_type: form.source_type || "LIVE",
    lines: (form.lines ?? []).map((line: InvoiceLine) => ({
      product_id: line.product_id ?? null,
      purchase_order_item_id: line.purchase_order_item_id ?? null,
      goods_receipt_item_id: line.goods_receipt_item_id ?? null,
      description: String(line.description || ""),
      quantity: Number(line.quantity || 0),
      uom: line.uom || null,
      unit_price: Number(line.unit_price || 0),
      is_taxable: Boolean(line.is_taxable),
      tax_rate: Number(line.tax_rate || 0),
      account_id: line.account_id ?? null,
      department_id: line.department_id ?? null,
      notes: line.notes || null,
    })),
  };
}

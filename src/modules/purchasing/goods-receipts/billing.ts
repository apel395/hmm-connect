export type ReceivingBilling = {
  supplier_invoice_number: string;
  supplier_document_total: number | null;
  supplier_invoice_date: string;
  supplier_invoice_due_date: string;
  tax_invoice_number: string;
  tax_invoice_date: string;
  supplier_document_url: string;
  discount_amount: number;
  shipping_fee_amount: number;
  admin_fee_amount: number;
  other_fee_amount: number;
  other_fee_description: string;
  shipping_fee_account_id: number | null;
  admin_fee_account_id: number | null;
  other_fee_account_id: number | null;
};
export const emptyReceivingBilling = (): ReceivingBilling => ({
  supplier_invoice_number: "", supplier_document_total: null, supplier_invoice_date: "", supplier_invoice_due_date: "",
  tax_invoice_number: "", tax_invoice_date: "", supplier_document_url: "",
  discount_amount: 0, shipping_fee_amount: 0, admin_fee_amount: 0, other_fee_amount: 0,
  other_fee_description: "", shipping_fee_account_id: null,
  admin_fee_account_id: null, other_fee_account_id: null,
});
export const fromReceiptBilling = (receipt: any): ReceivingBilling => {
  const empty = emptyReceivingBilling();
  return Object.fromEntries(Object.keys(empty).map(key => [
    key, receipt[key] ?? empty[key as keyof ReceivingBilling],
  ])) as ReceivingBilling;
};
export const billingTotal = (subtotal: number, tax: number, b: ReceivingBilling) =>
  subtotal + tax - b.discount_amount + b.shipping_fee_amount + b.admin_fee_amount + b.other_fee_amount;
export const validateReceivingBilling = (b: ReceivingBilling, subtotal: number): string | null => {
  if (b.discount_amount < 0 || b.discount_amount > subtotal) return "Discount must not exceed the received goods subtotal.";
  if (["shipping_fee_amount", "admin_fee_amount", "other_fee_amount"].some(key => Number(b[key as keyof ReceivingBilling]) < 0)) return "Supplier charges cannot be negative.";
  for (const key of ["shipping", "admin", "other"] as const) {
    if (b[`${key}_fee_amount`] > 0 && !b[`${key}_fee_account_id`])
      return `Select an expense account for the ${key} fee.`;
  }
  if (b.other_fee_amount > 0 && !b.other_fee_description.trim()) return "Describe the other supplier charge.";
  if (b.supplier_invoice_number.trim() && !b.supplier_invoice_date) return "Enter the supplier invoice date.";
  if (b.supplier_invoice_number.trim() && (!b.supplier_document_total || b.supplier_document_total <= 0)) return "Enter the total printed on the supplier invoice.";
  if (b.supplier_invoice_due_date && b.supplier_invoice_date && b.supplier_invoice_due_date < b.supplier_invoice_date)
    return "Supplier due date must not precede invoice date.";
  return null;
};

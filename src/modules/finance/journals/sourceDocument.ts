export function sourceDocumentPath(referenceType: string | null | undefined, referenceId: number | null | undefined): string | null {
  if (!referenceId || referenceId <= 0) return null;
  const routes: Record<string, string> = {
    SUPPLIER_INVOICE: "/supplier-invoices",
    SUPPLIER_PAYMENT: "/payments",
    GOODS_RECEIPT: "/receiving",
    PURCHASE_ORDER: "/purchase-orders",
    BANK_TRANSFER: "/bank-transfers",
    PAYMENT_VOUCHER: "/finance/payment-vouchers",
  };
  const base = routes[(referenceType || "").toUpperCase()];
  return base ? `${base}/${referenceId}` : null;
}

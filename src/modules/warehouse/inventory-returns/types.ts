/** Response contracts shared by the supplier-return screens. */

export type ReturnLine = {
  id: number;
  product_id: number;
  code: string;
  name: string;
  uom: string;
  quantity: number;
  replaced_quantity: number;
  line_cost: number;
};

export type SourceLine = {
  id: number;
  code: string;
  name: string;
  uom: string;
  received: number;
  returned: number;
  remaining: number;
  available: number;
};

export type ReturnEvent = {
  id: number;
  kind: string;
  date: string;
  amount: number;
  reference: string;
  reason: string;
  journal_entry_id: number;
  reversed: boolean;
};

export type ReturnDocument = {
  id: number;
  number: string;
  goods_receipt_id: number;
  warehouse_id: number;
  receipt_number: string;
  supplier_name: string;
  purpose: string;
  status: string;
  reason: string;
  return_date: string;
  total_cost: number;
  clearing_balance: number;
  journal_entry_id: number | null;
  credit_journal_id: number | null;
  credit_reference: string | null;
  credit_applied: number | null;
  supplier_credit: number | null;
  items: ReturnLine[];
  remaining_supplier_credit: number;
  events: ReturnEvent[];
  replacement_receipts: Array<{ id: number; number: string }>;
};

export type ReturnSourceInvoice = {
  id: number;
  number: string;
  status: string;
  balance: number;
  total: number;
};

export type ReturnSource = {
  id: number;
  warehouse_id: number;
  number: string;
  supplier: string;
  items: SourceLine[];
  invoices: ReturnSourceInvoice[];
};

export type ReturnListResponse = {
  items: ReturnDocument[];
  total_pages: number;
};

export type ReturnSourceOption = {
  id: number;
  number: string;
  supplier: string;
};

export type ReturnSourceListResponse = {
  items: ReturnSourceOption[];
  total_pages: number;
};

export type CreditInvoice = {
  id: number;
  number: string;
  balance: number;
};

export type CreditInvoiceListResponse = {
  items: CreditInvoice[];
  total_pages: number;
};

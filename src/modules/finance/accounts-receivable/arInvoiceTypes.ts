export type ServiceLine = {
  registration_number: string;
  description: string;
  amount: string;
};
export type InvoiceDocument = {
  description: string;
  contract_number: string;
  contract_date: string | null;
  lines: ServiceLine[];
  tax_label: string;
  tax_amount: string;
  amount_in_words: string;
};
export type Layout = {
  template: "standard" | "phr";
  title: string;
  billing_name: string;
  billing_address: string;
  company_address: string;
  attention: string;
  contract_number: string;
  contract_date: string | null;
  signer_name: string;
  signer_position: string;
  description: string;
  payment_instructions: string;
  footer: string;
  show_settlement: boolean;
};
export type Invoice = {
  source_sale_id?: number | null;
  account_id?: number | null;
  receipts?: Array<{ id: number; payment_number: string; payment_date: string; amount: string; payment_method: string; reference_number: string | null }>;

  id: number;
  invoice_number: string;
  invoice_date: string;
  due_date: string;
  amount: string;
  received_amount: string;
  outstanding_amount: string;
  customer_id: number;
  customer_name: string;
  customer_address: string | null;
  layout: Layout;
  document: InvoiceDocument;
  print_ready: boolean;
};
export const money = (value: unknown) =>
  Number(value || 0).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

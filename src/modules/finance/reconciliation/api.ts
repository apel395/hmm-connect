import api from "@/api/client";

export type ReconciliationAccount = {
  account_id: number;
  account_code: string;
  account_name: string;
  normal_balance: string;
};

export type ReconciliationDetail = {
  control: string;
  account_id?: number;
  account_code?: string | null;
  account_name?: string | null;
  source_balance?: number | null;
  gl_balance: number;
  variance?: number | null;
  movement_value?: number;
  status: string;
};

export type ReconciliationException = {
  kind: "UNALLOCATED_PAYMENT" | "SUSPENSE_JOURNAL";
  document_id: number;
  document_number: string;
  date: string;
  supplier_id?: number | null;
  reference_type?: string | null;
  reference_id?: number | null;
  amount: number;
  debit?: number;
  credit?: number;
};

export type ReconciliationCounterpart = {
  account_id: number;
  counterpart_account_id: number;
  counterpart_code: string;
  counterpart_name: string;
  journal_count: number;
  counterpart_debit: number;
  counterpart_credit: number;
};

export type ReconciliationReceipt = {
  receipt_id: number;
  receipt_number: string;
  date: string;
  supplier_id: number | null;
  received_amount: number;
  invoiced_amount: number;
  outstanding_amount: number;
  invoice_numbers: string[];
};

export type ReconciliationApDocument = {
  kind: "INVOICE" | "PAYMENT" | "GL_ONLY_JOURNAL" | "OPENING_GL" | "SOURCE_BALANCE_DRIFT";
  document_id: number | null;
  document_number: string;
  date: string | null;
  supplier_id: number | null;
  source_amount: number | null;
  gl_amount: number;
  difference: number;
  journal_ids: number[];
  reference_type?: string | null;
};

export type ReconciliationRow = {
  control: "ACCOUNTS_PAYABLE" | "ACCOUNTS_RECEIVABLE" | "CLEARING_SUSPENSE" | "INVENTORY";
  source_balance: number | null;
  gl_balance: number;
  difference: number | null;
  status: "RECONCILED" | "OUT_OF_BALANCE" | "OPEN_ITEMS" | "NOT_CONFIGURED" | "HISTORY_UNAVAILABLE";
  note?: string;
  accounts: ReconciliationAccount[];
  detail?: ReconciliationDetail[];
  counterparts?: ReconciliationCounterpart[];
  exceptions?: ReconciliationException[];
  receipt_evidence?: ReconciliationReceipt[];
  ap_documents?: ReconciliationApDocument[];
  ap_document_summary?: {
    source_activity: number;
    source_balance_drift: number;
    opening_gl: number;
    document_difference_total: number;
  };
  period?: {
    opening_source: number | null;
    opening_gl: number;
    source_change: number | null;
    gl_change: number;
  };
};

export type ReconciliationReport = {
  items: ReconciliationRow[];
  summary: {
    reconciled: number;
    out_of_balance: number;
    open_items: number;
    not_configured: number;
    history_unavailable: number;
  };
  scope: "CURRENT_BALANCE" | "DATE_RANGE";
  date_from: string | null;
  date_to: string | null;
  read_only: true;
};

export type ReconciliationFilters = { date_from?: string; date_to?: string };

export const reconciliationApi = {
  report: async (filters: ReconciliationFilters = {}) =>
    (await api.get<ReconciliationReport>("/financial-reconciliation", { params: filters })).data,
};

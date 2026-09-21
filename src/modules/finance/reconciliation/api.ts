import api from "@/api/client";

export type ReconciliationAccount = {
  account_id: number;
  account_code: string;
  account_name: string;
  normal_balance: string;
};

export type ReconciliationRow = {
  control: "ACCOUNTS_PAYABLE" | "ACCOUNTS_RECEIVABLE" | "CLEARING_SUSPENSE" | "INVENTORY";
  source_balance: number;
  gl_balance: number;
  difference: number;
  status: "RECONCILED" | "OUT_OF_BALANCE" | "NOT_CONFIGURED";
  accounts: ReconciliationAccount[];
};

export type ReconciliationReport = {
  items: ReconciliationRow[];
  summary: {
    reconciled: number;
    out_of_balance: number;
    not_configured: number;
  };
  scope: "CURRENT_BALANCE";
  read_only: true;
};

export const reconciliationApi = {
  report: async () =>
    (await api.get<ReconciliationReport>("/financial-reconciliation")).data,
};

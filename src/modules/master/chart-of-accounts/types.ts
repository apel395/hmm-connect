export type AccountType = "ASSET" | "LIABILITY" | "EQUITY" | "REVENUE" | "EXPENSE";
export type NormalBalance = "DEBIT" | "CREDIT";
export type AccountSubtype = "CASH" | "BANK" | "PETTY_CASH" | "OTHER";
export type CashFlowCategory = "OPERATING" | "INVESTING" | "FINANCING" | "NON_CASH" | "UNCLASSIFIED";
export type FinancialStatementGroup = "CURRENT_ASSET" | "NON_CURRENT_ASSET" | "CURRENT_LIABILITY" | "NON_CURRENT_LIABILITY" | "EQUITY" | "OPERATING_REVENUE" | "OTHER_REVENUE" | "COST_OF_REVENUE" | "OPERATING_EXPENSE" | "OTHER_EXPENSE";

export interface ChartOfAccount {
  id: number;
  account_code: string;
  account_name: string;
  account_type: AccountType;
  parent_account_id: number | null;
  normal_balance: NormalBalance;
  description: string | null;
  account_subtype: AccountSubtype;
  cash_flow_category: CashFlowCategory | null;
  financial_statement_group: FinancialStatementGroup | null;
  is_posting: boolean;
  is_system: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ChartOfAccountNode extends ChartOfAccount {
  children: ChartOfAccountNode[];
}

export type AccountPayload = Pick<ChartOfAccount,
  "account_code" | "account_name" | "account_type" | "parent_account_id" |
  "normal_balance" | "description" | "account_subtype" | "cash_flow_category" | "financial_statement_group" | "is_posting" | "is_active">;

export interface AccountPage {
  items: ChartOfAccount[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface AccountLookup {
  id: number;
  account_code: string;
  account_name: string;
  account_type: AccountType;
  normal_balance: NormalBalance;
  is_posting: boolean;
  is_active: boolean;
  account_subtype: AccountSubtype;
  cash_flow_category: CashFlowCategory | null;
  financial_statement_group: FinancialStatementGroup | null;
}

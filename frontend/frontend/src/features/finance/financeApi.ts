import api from "../../api/client";

export interface AccountPayable {
  id: number;
  supplier_id: number;
  purchase_order_id: number | null;
  invoice_number: string | null;
  invoice_date: string | null;
  due_date: string | null;
  amount: number;
  status: string;
}

export interface AccountReceipt {
  id: number;
  goods_receipt_id: number;
  product_id: number;
  account_id: number;
  quantity: number;
  unit_cost: number;
  total_amount: number;
  created_at: string;
}

export async function getAccountPayables(): Promise<AccountPayable[]> {
  const response = await api.get<AccountPayable[]>("/finance/account-payables");
  return response.data;
}

export async function getAccountReceipts(): Promise<AccountReceipt[]> {
  const response = await api.get<AccountReceipt[]>("/finance/account-receipts");
  return response.data;
}

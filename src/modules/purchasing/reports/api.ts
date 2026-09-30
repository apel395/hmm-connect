import api from "@/api/client";

export type PurchasingSummaryParams = {
  date_from?: string;
  date_to?: string;
};

export type PriceHistoryRow = {
  receipt_item_id: number;
  receipt_id: number;
  receipt_number: string;
  received_at: string;
  purchase_order_id: number | null;
  purchase_order_number: string | null;
  supplier_id: number | null;
  supplier_name: string;
  product_id: number;
  product_code: string;
  product_name: string;
  uom: string;
  quantity: string;
  unit_cost: string;
  line_value: string;
};
export type PriceHistoryPage = {
  items: PriceHistoryRow[];
  page: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
  cost_basis: string;
};

export const purchasingReportsApi = {
  summary: (params: PurchasingSummaryParams = {}) => api.get("/purchasing/summary", { params }),
  priceHistory: async (params: PurchasingSummaryParams & { search?: string; page?: number; page_size?: number } = {}) =>
    (await api.get<PriceHistoryPage>("/purchasing/price-history", { params })).data,
};
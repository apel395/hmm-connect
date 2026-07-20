import api from "../../api/client";

export interface PurchaseOrderItem {
  id: number;
  purchase_order_id: number;
  purchase_requisition_item_id: number | null;
  product_id: number;
  quantity: number;
  received_quantity: number;
  unit_price: number;
  total_price: number;
}

export interface PurchaseOrder {
  id: number;
  po_number: string;
  supplier_id: number;
  purchase_requisition_id: number | null;
  purchase_requisition_ids: number[];
  status: string;
  order_date: string;
  expected_date?: string | null;
  expiry_date?: string | null;
  receipt_tolerance_percent: number;
  total_amount: number;
  notes?: string | null;
  items: PurchaseOrderItem[];
}

export interface CreatePurchaseOrderData {
  supplier_id: number;
  purchase_requisition_ids?: number[];
  expected_date?: string;
  expiry_date?: string;
  receipt_tolerance_percent?: number;
  notes?: string;
  items: {
    product_id: number;
    quantity: number;
    unit_price: number;
    purchase_requisition_item_id?: number;
  }[];
}

export interface GoodsReceiptData {
  destination_type: "INVENTORY" | "DIRECT_CONSUMPTION";
  warehouse_id?: number;
  items: {
    purchase_order_item_id: number;
    quantity: number;
  }[];
}

export async function getPurchaseOrders(): Promise<PurchaseOrder[]> {
  const response = await api.get<PurchaseOrder[]>("/purchase-orders");
  return response.data;
}

export async function createPurchaseOrder(
  data: CreatePurchaseOrderData,
): Promise<PurchaseOrder> {
  const response = await api.post<PurchaseOrder>(
    "/purchase-orders",
    data,
  );
  return response.data;
}

export async function submitPurchaseOrder(
  purchaseOrderId: number,
): Promise<PurchaseOrder> {
  const response = await api.patch<PurchaseOrder>(
    `/purchase-orders/${purchaseOrderId}/submit`,
  );
  return response.data;
}

export async function approvePurchaseOrder(
  purchaseOrderId: number,
): Promise<PurchaseOrder> {
  const response = await api.patch<PurchaseOrder>(
    `/purchase-orders/${purchaseOrderId}/approve`,
  );
  return response.data;
}

export async function rejectPurchaseOrder(
  purchaseOrderId: number,
): Promise<PurchaseOrder> {
  const response = await api.patch<PurchaseOrder>(
    `/purchase-orders/${purchaseOrderId}/reject`,
  );
  return response.data;
}

export async function receiveGoods(
  purchaseOrderId: number,
  data: GoodsReceiptData,
) {
  const response = await api.post(
    `/goods-receipts/purchase-orders/${purchaseOrderId}/receive`,
    data,
  );
  return response.data;
}

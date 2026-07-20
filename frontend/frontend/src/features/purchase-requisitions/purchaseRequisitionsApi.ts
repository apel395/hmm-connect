import api from "../../api/client";

export interface PurchaseRequisitionItem {
  id: number;
  product_id: number;
  product_code: string;
  product_name: string;
  product_uom: string;
  quantity: number;
  estimated_price: number;
  total_price: number;
}

export interface PurchaseRequisition {
  id: number;
  pr_number: string;
  status: string;
  request_date: string;
  total_amount: number;
  items: PurchaseRequisitionItem[];
}

export interface PurchaseRequisitionItemCreate {
  product_id: number;
  quantity: number;
  estimated_price: number;
}

export interface PurchaseRequisitionCreate {
  notes?: string;
  items: PurchaseRequisitionItemCreate[];
}

export async function getPurchaseRequisitions(): Promise<
  PurchaseRequisition[]
> {
  const response = await api.get<PurchaseRequisition[]>(
    "/purchase-requisitions",
  );

  return response.data;
}


export async function getPurchaseRequisition(
  purchaseRequisitionId: number,
): Promise<PurchaseRequisition> {
  const response = await api.get<PurchaseRequisition>(
    `/purchase-requisitions/${purchaseRequisitionId}`,
  );

  return response.data;
}

export async function createPurchaseRequisition(
  data: PurchaseRequisitionCreate,
): Promise<PurchaseRequisition> {
  const response = await api.post<PurchaseRequisition>(
    "/purchase-requisitions",
    data,
  );

  return response.data;
}

export async function submitPurchaseRequisition(
  purchaseRequisitionId: number,
): Promise<PurchaseRequisition> {
  const response = await api.patch<PurchaseRequisition>(
    `/purchase-requisitions/${purchaseRequisitionId}/submit`,
  );

  return response.data;
}

export async function approvePurchaseRequisition(
  purchaseRequisitionId: number,
): Promise<PurchaseRequisition> {
  const response = await api.patch<PurchaseRequisition>(
    `/purchase-requisitions/${purchaseRequisitionId}/approve`,
  );

  return response.data;
}

export async function rejectPurchaseRequisition(
  purchaseRequisitionId: number,
): Promise<PurchaseRequisition> {
  const response = await api.patch<PurchaseRequisition>(
    `/purchase-requisitions/${purchaseRequisitionId}/reject`,
  );

  return response.data;
}

export interface TraceabilityEvent {
  id: number;
  action: string;
  entity_type: string;
  entity_id: number | null;
  summary: string;
  user_name: string | null;
  created_at: string;
}

export interface TraceabilityPurchaseOrder {
  id: number;
  po_number: string;
  status: string;
}

export interface TraceabilityGoodsReceipt {
  id: number;
  receipt_number: string;
  purchase_order_id: number;
}

export interface TraceabilityStockMovement {
  id: number;
  product_id: number;
  quantity: number;
  goods_receipt_id: number | null;
}

export interface PurchaseRequisitionTraceability {
  purchase_requisition_id: number;
  pr_number: string;
  purchase_orders: TraceabilityPurchaseOrder[];
  goods_receipts: TraceabilityGoodsReceipt[];
  stock_movements: TraceabilityStockMovement[];
  events: TraceabilityEvent[];
}

export async function getPurchaseRequisitionTraceability(
  purchaseRequisitionId: number,
): Promise<PurchaseRequisitionTraceability> {
  const response =
    await api.get<PurchaseRequisitionTraceability>(
      `/purchase-requisitions/${purchaseRequisitionId}/traceability`,
    );

  return response.data;
}

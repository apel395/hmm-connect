import api from "@/api/client";

export interface PurchaseOrderItemPayload {
  product_id: number;

  quantity: number;

  unit_price: number;

  purchase_requisition_item_id?: number | null;
}

export interface PurchaseOrderCreatePayload {
  supplier_id: number;

  expected_date: string;

  expiry_date?: string | null;

  receipt_tolerance_percent?: number;

  notes?: string;

  purchase_requisition_ids?: number[];

  items: PurchaseOrderItemPayload[];
}

export const purchaseOrderApi = {

  list: (scope = "active") =>
    api.get(
      "/purchase-orders",
      { params: { scope } }
    ),

  detail: (
    id: number
  ) =>
    api.get(
      `/purchase-orders/${id}`
    ),

  create: (
    payload: PurchaseOrderCreatePayload
  ) =>
    api.post(
      "/purchase-orders",
      payload
    ),

  update: (
    id: number,
    payload: PurchaseOrderCreatePayload
  ) =>
    api.put(
      `/purchase-orders/${id}`,
      payload
    ),

  submit: (
    id: number
  ) =>
    api.post(
      `/purchase-orders/${id}/submit`
    ),

  approve: (
    id: number,
    comment = ""
  ) =>
    api.post(
      `/purchase-orders/${id}/approve`,
      {
        comment,
      }
    ),

  reject: (
    id: number,
    comment = ""
  ) =>
    api.post(
      `/purchase-orders/${id}/reject`,
      {
        comment,
      }
    ),

  cancel: (
    id: number
  ) =>
    api.post(
      `/purchase-orders/${id}/cancel`
    ),

  delete: (
    id: number
  ) =>
    api.delete(
      `/purchase-orders/${id}`
    ),

  approvedPurchaseRequisitions: () =>

    api.get(
      "/purchase-requisitions/eligible-for-po"
    ),

};

export default purchaseOrderApi;
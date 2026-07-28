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

  list: () =>
    api.get(
      "/purchase-orders"
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
    api.patch(
      `/purchase-orders/${id}/submit`
    ),

  approve: (
    id: number,
    comment = ""
  ) =>
    api.patch(
      `/purchase-orders/${id}/approve`,
      {
        comment,
      }
    ),

  reject: (
    id: number,
    comment = ""
  ) =>
    api.patch(
      `/purchase-orders/${id}/reject`,
      {
        comment,
      }
    ),

  cancel: (
    id: number
  ) =>
    api.patch(
      `/purchase-orders/${id}/cancel`
    ),

  delete: (
    id: number
  ) =>
    api.delete(
      `/purchase-orders/${id}`
    ),

  /*
    Approved PR source for PO creation.

    Backend:
    GET /purchase-requisitions

    We filter APPROVED here because
    backend currently does not expose:
    /purchase-requisitions/approved
  */
  approvedPurchaseRequisitions: async () => {

    const res =
      await api.get(
        "/purchase-requisitions"
      );

    const rows =
      Array.isArray(res.data)
        ? res.data
        : [];

    return {
      data: rows.filter(
        (item: any) =>
          item.status === "APPROVED"
      ),
    };

  },

};

export default purchaseOrderApi;
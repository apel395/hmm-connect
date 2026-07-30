import api from "@/api/client";

export const requisitionApi = {

  list: (scope = "active") =>

    api.get(
      "/purchase-requisitions",
      { params: { scope } },
    ),

  detail: (
    id: number,
  ) =>

    api.get(
      `/purchase-requisitions/${id}`,
    ),

  create: (
    payload: any,
  ) =>

    api.post(
      "/purchase-requisitions",
      payload,
    ),

  update: (
    id: number,
    payload: any,
  ) =>

    api.put(
      `/purchase-requisitions/${id}`,
      payload,
    ),

  submit: (
    id: number,
  ) =>

    api.post(
      `/purchase-requisitions/${id}/submit`,
    ),

  approve: (
    id: number,
    comment?: string,
  ) =>

    api.post(
      `/purchase-requisitions/${id}/approve`,
      {
        comment,
      },
    ),

  reject: (
    id: number,
    comment?: string,
  ) =>

    api.post(
      `/purchase-requisitions/${id}/reject`,
      {
        comment,
      },
    ),

  cancel: (
    id: number,
  ) =>

    api.patch(
      `/purchase-requisitions/${id}/cancel`,
    ),

  traceability: (
    id: number,
  ) =>

    api.get(
      `/traceability/purchase-requisitions/${id}`,
    ),

  convertToPO: (
    id: number,
    supplier_id: number,
  ) =>

    api.post(
      `/purchase-requisitions/${id}/convert-to-po`,
      {
        supplier_id,
      },
    ),

};

export default requisitionApi;
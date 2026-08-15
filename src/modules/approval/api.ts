import api from "@/api/client";

export type ApprovalStep = {
  id: number;
  step_order: number;
  name: string;
  approver_role_name: string;
  department_name?: string | null;
  location_name?: string | null;
  status: string;
  approved_by_name?: string | null;
  decided_at?: string | null;
  decision_comment?: string | null;
};

export type ApprovalRequestRow = {
  id: number;
  entity_type: string;
  entity_id: number;
  workflow_code: string;
  workflow_name: string;
  status: string;
  current_step_order?: number | null;
  current_stage: string[];
  created_by_name?: string | null;
  created_at: string;
  completed_at?: string | null;
  can_decide: boolean;
  steps?: ApprovalStep[];
};

export type ApprovalInboxPage = {
  items: ApprovalRequestRow[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
};

export type ApprovalWorkflowStep = {
  id?: number;
  step_order: number;
  name: string;
  approver_role_id: number;
  approver_role_name?: string;
  department_id?: number | null;
  department_name?: string | null;
  location_id?: number | null;
  location_name?: string | null;
  mode?: "SEQUENTIAL" | "PARALLEL";
};

export type ApprovalWorkflow = {
  id: number;
  code: string;
  name: string;
  entity_type: string;
  is_active: boolean;
  steps: ApprovalWorkflowStep[];
};

export type WorkflowPayload = Omit<ApprovalWorkflow, "id" | "steps"> & { steps: ApprovalWorkflowStep[] };

export const approvalApi = {
  inbox: async (view: string, page = 1, pageSize = 20) =>
    (await api.get<ApprovalInboxPage>("/approvals/inbox", { params: { view, page, page_size: pageSize } })).data,
  workflows: async () => (await api.get<ApprovalWorkflow[]>("/approvals/workflows")).data,
  createWorkflow: async (payload: WorkflowPayload) => (await api.post<ApprovalWorkflow>("/approvals/workflows", payload)).data,
  updateWorkflow: async (id: number, payload: WorkflowPayload) => (await api.put<ApprovalWorkflow>(`/approvals/workflows/${id}`, payload)).data,
  detail: async (entityType: string, entityId: number) => (await api.get<ApprovalRequestRow>(`/approvals/${entityType}/${entityId}`)).data,
  approveDocument: async (row: ApprovalRequestRow, comment?: string) => {
    if (row.entity_type === "PURCHASE_REQUISITION") return api.post(`/purchase-requisitions/${row.entity_id}/approve`, { comment: comment || null });
    if (row.entity_type === "PURCHASE_ORDER") return api.post(`/purchase-orders/${row.entity_id}/approve`, { comment: comment || null });
    throw new Error("This document type is not yet connected to Approval Center decisions.");
  },
  rejectDocument: async (row: ApprovalRequestRow, comment: string) => {
    if (row.entity_type === "PURCHASE_REQUISITION") return api.post(`/purchase-requisitions/${row.entity_id}/reject`, { comment });
    if (row.entity_type === "PURCHASE_ORDER") return api.post(`/purchase-orders/${row.entity_id}/reject`, { comment });
    throw new Error("This document type is not yet connected to Approval Center decisions.");
  },
};

export function approvalDocumentPath(row: ApprovalRequestRow): string | null {
  if (row.entity_type === "PURCHASE_REQUISITION") return `/purchase-requisitions/${row.entity_id}`;
  if (row.entity_type === "PURCHASE_ORDER") return `/purchase-orders/${row.entity_id}`;
  if (row.entity_type === "SUPPLIER_INVOICE") return `/supplier-invoices/${row.entity_id}`;
  if (row.entity_type === "PAYMENT") return `/payments/${row.entity_id}`;
  return null;
}

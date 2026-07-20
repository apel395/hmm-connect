import api from "../../api/client";

export interface ApprovalWorkflowStep {
  id: number;
  step_order: number;
  name: string;
  approver_role_id: number;
  approver_role_name: string;
  department_id: number | null;
  department_name: string | null;
  location_id: number | null;
  location_name: string | null;
}

export interface ApprovalWorkflow {
  id: number;
  code: string;
  name: string;
  entity_type: string;
  is_active: boolean;
  steps: ApprovalWorkflowStep[];
}

export interface ApprovalWorkflowStepInput {
  step_order: number;
  name: string;
  approver_role_id: number;
  department_id?: number | null;
  location_id?: number | null;
}

export interface ApprovalWorkflowInput {
  code: string;
  name: string;
  entity_type: string;
  steps: ApprovalWorkflowStepInput[];
}

export interface ApprovalStep {
  step_order: number;
  name: string;
  approver_role_name: string;
  department_name: string | null;
  location_name: string | null;
  status: string;
  approved_by_name: string | null;
  decided_at: string | null;
  decision_comment: string | null;
}

export interface ApprovalStatus {
  entity_type: string;
  entity_id: number;
  workflow_code: string;
  workflow_name: string;
  status: string;
  current_step_order: number | null;
  current_step_name: string | null;
  current_approver_role: string | null;
  steps: ApprovalStep[];
}

export async function getApprovalWorkflows(): Promise<ApprovalWorkflow[]> {
  const response = await api.get<ApprovalWorkflow[]>("/approval-workflows");
  return response.data;
}

export async function updateApprovalWorkflow(
  workflowId: number,
  data: ApprovalWorkflowInput,
): Promise<ApprovalWorkflow> {
  const response = await api.put<ApprovalWorkflow>(
    `/approval-workflows/${workflowId}`,
    data,
  );
  return response.data;
}

export async function getApprovalStatus(
  entityType: string,
  entityId: number,
): Promise<ApprovalStatus> {
  const response = await api.get<ApprovalStatus>(
    `/approvals/${entityType}/${entityId}`,
  );
  return response.data;
}

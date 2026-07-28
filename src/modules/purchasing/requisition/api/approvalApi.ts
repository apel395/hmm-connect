import api from "@/api/client";

export interface ApprovalStep {

  step_order: number;

  name: string;

  approver_role_name: string;

  department_name?: string;

  location_name?: string;

  status: string;

  approved_by_name?: string | null;

  decided_at?: string | null;

  decision_comment?: string | null;

}

export interface ApprovalWorkflow {

  entity_type: string;

  entity_id: number;

  workflow_code: string;

  workflow_name: string;

  status: string;

  current_step_order?: number;

  current_step_name?: string;

  current_approver_role?: string;

  steps: ApprovalStep[];

}

export const approvalApi = {

  detail(

    entityType: string,

    entityId: number,

  ) {

    return api.get<ApprovalWorkflow>(

      `/approvals/${entityType}/${entityId}`,

    );

  },

};

export default approvalApi;
import {
  useQuery,
} from "@tanstack/react-query";

import approvalApi from "../api/approvalApi";

export interface ApprovalStep {

  id: number;

  step_order: number;

  approver_role_name: string;

  approver_name?: string;

  status: string;

  comment?: string;

  action_date?: string;

}

export interface ApprovalData {

  id: number;

  status: string;

  current_approver_role?: string;

  workflow?: {

    id: number;

    name: string;

  };

  steps: ApprovalStep[];

}

function normalizeApproval(
  data: any,
): ApprovalData {

  return {

    ...data,

    status:
      data?.status ??
      "PENDING",

    current_approver_role:

      data?.current_approver_role ??

      data?.current_role ??

      data?.current_step
        ?.approver_role_name ??

      undefined,

    workflow:

      data?.workflow ??

      undefined,

    steps:

      data?.steps ??

      [],

  };

}

export function useApproval(

  entityType: string,

  entityId: number,

) {

  return useQuery({

    queryKey: [

      "approval",

      entityType,

      entityId,

    ],

    queryFn: async () => {

      const res =

        await approvalApi.detail(

          entityType,

          entityId,

        );

      return normalizeApproval(
        res.data,
      );

    },

    enabled:

      Boolean(
        entityType,
      ) &&

      Boolean(
        entityId,
      ),

    staleTime:

      60 * 1000,

  });

}
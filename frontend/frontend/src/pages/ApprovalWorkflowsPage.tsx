import { useState } from "react";
import { Plus, Save, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Modal } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { Select } from "../components/ui/Select";
import {
  getApprovalWorkflows,
  updateApprovalWorkflow,
  type ApprovalWorkflow,
  type ApprovalWorkflowStepInput,
} from "../features/approval-workflows/approvalWorkflowsApi";
import { getDepartments } from "../features/departments/departmentsApi";
import { getLocations } from "../features/locations/locationsApi";
import { getRoles } from "../features/roles/rolesApi";

interface EditableStep extends ApprovalWorkflowStepInput {
  localId: string;
}

export default function ApprovalWorkflowsPage() {
  const queryClient = useQueryClient();
  const [selectedWorkflow, setSelectedWorkflow] = useState<ApprovalWorkflow | null>(null);
  const [steps, setSteps] = useState<EditableStep[]>([]);

  const workflowsQuery = useQuery({ queryKey: ["approval-workflows"], queryFn: getApprovalWorkflows });
  const rolesQuery = useQuery({ queryKey: ["roles"], queryFn: getRoles });
  const departmentsQuery = useQuery({ queryKey: ["departments"], queryFn: getDepartments });
  const locationsQuery = useQuery({ queryKey: ["locations"], queryFn: getLocations });

  const updateMutation = useMutation({
    mutationFn: ({ workflowId, data }: { workflowId: number; data: Parameters<typeof updateApprovalWorkflow>[1] }) => updateApprovalWorkflow(workflowId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["approval-workflows"] });
      setSelectedWorkflow(null);
    },
  });

  const workflows = workflowsQuery.data ?? [];
  const roles = rolesQuery.data ?? [];
  const departments = departmentsQuery.data ?? [];
  const locations = locationsQuery.data ?? [];

  function openWorkflow(workflow: ApprovalWorkflow) {
    setSelectedWorkflow(workflow);
    setSteps(workflow.steps.map((step) => ({
      localId: String(step.id),
      step_order: step.step_order,
      name: step.name,
      approver_role_id: step.approver_role_id,
      department_id: step.department_id,
      location_id: step.location_id,
    })));
  }


  function addStep() {
    const nextOrder = steps.length === 0 ? 1 : Math.max(...steps.map((step) => step.step_order)) + 1;
    setSteps((current) => [
      ...current,
      {
        localId: crypto.randomUUID(),
        step_order: nextOrder,
        name: `Approval Step ${nextOrder}`,
        approver_role_id: roles[0]?.id ?? 0,
        department_id: null,
        location_id: null,
      },
    ]);
  }

  function updateStep(localId: string, patch: Partial<EditableStep>) {
    setSteps((current) => current.map((step) => step.localId === localId ? { ...step, ...patch } : step));
  }

  function removeStep(localId: string) {
    setSteps((current) => current.filter((step) => step.localId !== localId).map((step, index) => ({ ...step, step_order: index + 1 })));
  }

  function saveWorkflow() {
    if (!selectedWorkflow || steps.length === 0) return;
    updateMutation.mutate({
      workflowId: selectedWorkflow.id,
      data: {
        code: selectedWorkflow.code,
        name: selectedWorkflow.name,
        entity_type: selectedWorkflow.entity_type,
        steps: steps
          .sort((a, b) => a.step_order - b.step_order)
          .map((step) => ({
            step_order: step.step_order,
            name: step.name,
            approver_role_id: step.approver_role_id,
            department_id: step.department_id,
            location_id: step.location_id,
          })),
      },
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Approval Workflows"
        description="Configure the approval layers used by PR and PO without changing application code."
      />

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 p-6">
          <h2 className="font-semibold text-slate-900">Configured workflows</h2>
          <p className="mt-1 text-sm text-slate-500">The workflow definition is copied into each document approval for audit safety.</p>
        </div>

        {workflowsQuery.isLoading && <div className="p-8 text-center text-sm text-slate-500">Loading workflows...</div>}
        {!workflowsQuery.isLoading && workflows.length === 0 && <EmptyState title="No approval workflows" description="Create a workflow through the API before using layered approvals." />}

        {workflows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px]">
              <thead>
                <tr className="border-b border-slate-200 text-left">
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Workflow</th>
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Document</th>
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Approval layers</th>
                  <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Action</th>
                </tr>
              </thead>
              <tbody>
                {workflows.map((workflow) => (
                  <tr key={workflow.id} className="border-b border-slate-100 last:border-0">
                    <td className="px-6 py-4"><p className="text-sm font-medium text-slate-900">{workflow.name}</p><p className="text-xs text-slate-500">{workflow.code}</p></td>
                    <td className="px-6 py-4 text-sm text-slate-600">{workflow.entity_type}</td>
                    <td className="px-6 py-4 text-sm text-slate-600">{workflow.steps.map((step) => step.name).join(" → ")}</td>
                    <td className="px-6 py-4 text-right"><Button type="button" variant="secondary" onClick={() => openWorkflow(workflow)}>Configure</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal
        open={selectedWorkflow !== null}
        onClose={() => setSelectedWorkflow(null)}
        title={selectedWorkflow ? `Configure ${selectedWorkflow.name}` : "Configure workflow"}
        description="The order of the steps is the order required before the document becomes approved."
        size="xl"
        closeDisabled={updateMutation.isPending}
        footer={<><Button type="button" variant="secondary" onClick={() => setSelectedWorkflow(null)} disabled={updateMutation.isPending}>Cancel</Button><Button type="button" onClick={saveWorkflow} loading={updateMutation.isPending} disabled={steps.length === 0}><Save size={16} className="mr-2" />Save workflow</Button></>}
      >
        <div className="space-y-4">
          {steps.map((step, index) => (
            <div key={step.localId} className="rounded-xl border border-slate-200 p-4">
              <div className="mb-3 flex items-center justify-between">
                <div><p className="text-sm font-semibold text-slate-900">Layer {index + 1}</p><p className="text-xs text-slate-500">Step {step.step_order}</p></div>
                <button type="button" onClick={() => removeStep(step.localId)} className="text-slate-400 hover:text-red-600"><Trash2 size={16} /></button>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <input value={step.name} onChange={(event) => updateStep(step.localId, { name: event.target.value })} placeholder="Step name" className="h-10 rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10" />
                <Select value={String(step.approver_role_id)} onChange={(value) => updateStep(step.localId, { approver_role_id: Number(value) })} placeholder="Approver role" options={roles.map((role) => ({ value: String(role.id), label: role.name }))} />
                <Select value={step.department_id ? String(step.department_id) : ""} onChange={(value) => updateStep(step.localId, { department_id: value ? Number(value) : null })} placeholder="Any department" options={departments.map((department) => ({ value: String(department.id), label: `${department.code} - ${department.name}` }))} />
                <Select value={step.location_id ? String(step.location_id) : ""} onChange={(value) => updateStep(step.localId, { location_id: value ? Number(value) : null })} placeholder="Any location" options={locations.map((location) => ({ value: String(location.id), label: `${location.code} - ${location.name}` }))} />
              </div>
            </div>
          ))}

          <Button type="button" variant="secondary" onClick={addStep}><Plus size={16} className="mr-2" />Add approval layer</Button>
          {updateMutation.isError && <p className="text-sm text-red-600">Failed to update approval workflow.</p>}
        </div>
      </Modal>
    </div>
  );
}

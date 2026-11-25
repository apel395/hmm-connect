import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {Plus, Settings2, Trash2, Printer} from "lucide-react";
import { toast } from "sonner";

import ModuleSummary from "@/components/common/ModuleSummary";
import PageHeader from "@/components/common/PageHeader";
import { FORM_UI } from "@/config/formUi";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import Empty from "@/components/ui/Empty";
import Input from "@/components/ui/Input";
import Loading from "@/components/ui/Loading";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import { apiErrorMessage } from "@/utils/apiError";

import { roleApi } from "@/modules/admin/roles/roleApi";
import { listDepartments, listLocations } from "@/modules/admin/organization/api";
import { approvalApi, type ApprovalWorkflow, type ApprovalWorkflowStep } from "./api";
const selectClass = `${FORM_UI.controlBase} ${FORM_UI.density.compact.control} mt-1 w-full`;

const entityTypes = ["PURCHASE_REQUISITION", "PURCHASE_ORDER", "SUPPLIER_INVOICE", "PAYMENT", "CREDIT_NOTE", "SALES_ORDER", "AR_INVOICE", "FIXED_ASSET"];
const blankStep = (): ApprovalWorkflowStep => ({ step_order: 1, name: "Approval Level 1", approver_role_id: 0, department_id: null, location_id: null });

export default function ApprovalConfigurationPage() {
  const qc = useQueryClient();
  const workflows = useQuery({ queryKey: ["approval-workflows"], queryFn: approvalApi.workflows });
  const roles = useQuery({ queryKey: ["managed-roles"], queryFn: roleApi.list });
  const departments = useQuery({ queryKey: ["approval-departments"], queryFn: () => listDepartments({ is_active: true }) });
  const locations = useQuery({ queryKey: ["approval-locations"], queryFn: () => listLocations({ is_active: true }) });
  const [editing, setEditing] = useState<ApprovalWorkflow | "new" | null>(null);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [entityType, setEntityType] = useState("PURCHASE_REQUISITION");
  const [active, setActive] = useState(true);
  const [steps, setSteps] = useState<ApprovalWorkflowStep[]>([blankStep()]);

  const workflowList = workflows.data ?? [];
  const activeWorkflows = workflowList.filter((workflow) => workflow.is_active).length;
  const totalSteps = workflowList.reduce((total, workflow) => total + workflow.steps.length, 0);

  const save = useMutation({
    mutationFn: async () => {
      const payload = { code: code.trim().toUpperCase(), name: name.trim(), entity_type: entityType, is_active: active, steps };
      return editing === "new" ? approvalApi.createWorkflow(payload) : approvalApi.updateWorkflow((editing as ApprovalWorkflow).id, payload);
    },
    onSuccess: () => { toast.success("Approval workflow saved."); setEditing(null); qc.invalidateQueries({ queryKey: ["approval-workflows"] }); },
    onError: (error: unknown) => toast.error(apiErrorMessage(error, "Workflow could not be saved.")),
  });

  function open(workflow?: ApprovalWorkflow) {
    if (!workflow) { setEditing("new"); setCode(""); setName(""); setEntityType("PURCHASE_REQUISITION"); setActive(true); setSteps([blankStep()]); return; }
    setEditing(workflow); setCode(workflow.code); setName(workflow.name); setEntityType(workflow.entity_type); setActive(workflow.is_active); setSteps(workflow.steps.map((step) => ({ ...step })));
  }

  const updateStep = (index: number, patch: Partial<ApprovalWorkflowStep>) => setSteps((current) => current.map((step, i) => i === index ? { ...step, ...patch } : step));

  return <DataWorkspace area="Admin">
    <div className="workspace-body">
      <PageHeader title="Approval Configuration" description="Configure sequential and parallel approval stages by document type. Steps with the same stage number run in parallel." actions={<>
<Button onClick={() => open()}><Plus className="h-4 w-4"/> New Workflow</Button>
<Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
</>} />

      <ModuleSummary metrics={[
        { label: "Workflows", value: workflowList.length },
        { label: "Active", value: activeWorkflows },
        { label: "Inactive", value: workflowList.length - activeWorkflows },
        { label: "Approval Steps", value: totalSteps },
      ]}/>

      <Card className="workspace-data p-0 overflow-hidden">{workflows.isLoading ? <div className="py-12"><Loading message="Loading workflows…"/></div> : workflows.isError ? <div role="alert" className="m-5 rounded border border-red-200 bg-red-50 p-4 text-sm text-red-700"><p className="font-semibold">Approval workflows could not be loaded.</p><p>{apiErrorMessage(workflows.error, "Please try again.")}</p></div> : workflowList.length === 0 ? <Empty title="No approval workflows" description="Create a workflow to configure approval stages by document type."/> : <div className="overflow-x-auto"><table className="min-w-[900px] w-full text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="p-3">Workflow</th><th className="p-3">Document</th><th className="p-3">Stages</th><th className="p-3">Status</th><th className="p-3 text-right">Action</th></tr></thead><tbody className="divide-y">{workflowList.map((workflow) => <tr key={workflow.id}><td className="p-3"><div className="font-medium">{workflow.name}</div><div className="text-xs text-slate-500">{workflow.code}</div></td><td className="p-3">{workflow.entity_type.replaceAll("_", " ")}</td><td className="p-3">{new Set(workflow.steps.map((step) => step.step_order)).size} stages · {workflow.steps.length} approvals</td><td className="p-3"><Badge variant={workflow.is_active ? "success" : "secondary"}>{workflow.is_active ? "Active" : "Inactive"}</Badge></td><td className="p-3 text-right"><Button size="sm" variant="outline" onClick={() => open(workflow)}><Settings2 className="h-4 w-4"/> Configure</Button></td></tr>)}</tbody></table></div>}</Card>
    </div>

    <Dialog open={editing !== null} onOpenChange={(value) => !value && setEditing(null)}><DialogContent className="max-h-[92vh] max-w-5xl overflow-y-auto"><DialogHeader><DialogTitle>{editing === "new" ? "Create Approval Workflow" : "Configure Approval Workflow"}</DialogTitle></DialogHeader><DialogBody className="space-y-5">
      <div className="grid gap-3 md:grid-cols-3"><label className="text-sm">Code *<Input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())}/></label><label className="text-sm">Name *<Input value={name} onChange={(e) => setName(e.target.value)}/></label><label className="text-sm">Document Type<select className={selectClass} value={entityType} onChange={(e) => setEntityType(e.target.value)}>{entityTypes.map((value) => <option key={value}>{value}</option>)}</select></label></div>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)}/> Active workflow</label>
      <div><div className="mb-2 flex items-end justify-between"><div><h3 className="font-semibold">Approval Steps</h3><p className="text-sm text-slate-500">Use the same stage number for parallel approvals. Higher stage numbers wait until the previous stage is complete.</p></div><Button size="sm" variant="outline" onClick={() => setSteps((current) => [...current, { ...blankStep(), step_order: Math.max(...current.map((step) => step.step_order), 0) + 1, name: `Approval Level ${current.length + 1}` }])}>Add Step</Button></div><div className="space-y-3">{steps.map((step, index) => <div key={index} className="grid gap-3 rounded-lg border p-3 md:grid-cols-[100px_1fr_1fr_1fr_1fr_auto]"><label className="text-xs">Stage<Input type="number" min={1} value={step.step_order} onChange={(e) => updateStep(index, { step_order: Number(e.target.value) })}/></label><label className="text-xs">Step Name<Input value={step.name} onChange={(e) => updateStep(index, { name: e.target.value })}/></label><label className="text-xs">Approver Role<select className={selectClass} value={step.approver_role_id || ""} onChange={(e) => updateStep(index, { approver_role_id: Number(e.target.value) })}><option value="">Select role</option>{(roles.data ?? []).map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</select>{roles.isError && <span role="alert" className={FORM_UI.errorText}>Roles could not be loaded: {apiErrorMessage(roles.error, "Unknown error")}</span>}</label><label className="text-xs">Department<select className={selectClass} value={step.department_id || ""} onChange={(e) => updateStep(index, { department_id: e.target.value ? Number(e.target.value) : null })}><option value="">Any</option>{(departments.data ?? []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>{departments.isError && <span role="alert" className={FORM_UI.errorText}>Departments could not be loaded: {apiErrorMessage(departments.error, "Unknown error")}</span>}</label><label className="text-xs">Location<select className={selectClass} value={step.location_id || ""} onChange={(e) => updateStep(index, { location_id: e.target.value ? Number(e.target.value) : null })}><option value="">Any</option>{(locations.data ?? []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>{locations.isError && <span role="alert" className={FORM_UI.errorText}>Locations could not be loaded: {apiErrorMessage(locations.error, "Unknown error")}</span>}</label><Button variant="outline" disabled={steps.length === 1} onClick={() => setSteps((current) => current.filter((_, i) => i !== index))}><Trash2 className="h-4 w-4"/></Button></div>)}</div></div>
      {save.isError && <div role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">Workflow could not be saved. {apiErrorMessage(save.error, "Please try again.")}</div>}
    </DialogBody><DialogFooter><Button variant="outline" onClick={() => setEditing(null)}>Cancel</Button><Button loading={save.isPending} disabled={!code.trim() || !name.trim() || steps.some((step) => !step.name.trim() || !step.approver_role_id)} onClick={() => save.mutate()}>Save Workflow</Button></DialogFooter></DialogContent></Dialog>
  </DataWorkspace>;
}

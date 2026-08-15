import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";

interface Props { approval?: any }

function badgeVariant(status?: string) {
  switch ((status ?? "").toUpperCase()) {
    case "APPROVED": return "success";
    case "PENDING": return "warning";
    case "REJECTED": return "danger";
    case "CANCELLED": return "secondary";
    case "WAITING": return "outline";
    default: return "outline";
  }
}

const isLocalRole = (role?: string) => ["STORE", "CHEF", "PM/CAMP BOSS"].includes((role ?? "").toUpperCase());

export default function ApprovalSummary({ approval }: Props) {
  const workflow = approval?.workflow;
  const steps = approval?.steps ?? [];
  const current = steps.find((step:any) => step.status === "PENDING");

  return <Card>
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div><h3 className="text-lg font-semibold">Approval Workflow</h3><p className="mt-1 text-sm text-slate-500">Store → Chef → PM/Camp Boss → HO Purchasing → Finance → General Manager</p></div>
      {approval?.status && <Badge variant={badgeVariant(approval.status) as any}>{approval.status}</Badge>}
    </div>
    <div className="space-y-4">
      <div className="grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 sm:grid-cols-2">
        <div><div className="text-xs uppercase tracking-wide text-slate-500">Workflow</div><div className="mt-1 font-semibold">{workflow?.name ?? "Purchasing Approval"}</div></div>
        <div><div className="text-xs uppercase tracking-wide text-slate-500">Current Stage</div><div className="mt-1 font-semibold">{current ? `${current.name ?? current.approver_role_name}` : approval?.status === "APPROVED" ? "Completed" : "—"}</div></div>
      </div>
      {steps.length === 0 && <div className="py-6 text-center text-sm text-slate-500">Approval starts after the document is submitted.</div>}
      {steps.map((step:any,index:number) => {
        const local = isLocalRole(step.approver_role_name);
        return <div key={step.id ?? index} className={`rounded-lg border p-4 ${step.status === "PENDING" ? "border-amber-300 bg-amber-50/50" : "border-slate-200"}`}>
          <div className="flex items-start justify-between gap-3">
            <div><div className="flex items-center gap-2"><span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold">{step.step_order}</span><span className="font-medium">{step.name ?? step.approver_role_name}</span></div><div className="mt-1 pl-8 text-sm text-slate-500">Role: {step.approver_role_name}</div><div className="mt-1 pl-8 text-xs text-slate-500">{local ? `Location scope: ${step.location_name ?? "document location"}` : "Head Office / cross-location approval"}</div></div>
            <Badge variant={badgeVariant(step.status) as any}>{step.status}</Badge>
          </div>
          {(step.approver_name || step.action_date || step.decided_at) && <div className="mt-4 border-t pt-3 text-sm text-slate-600">{step.approver_name && <div><span className="font-medium">By:</span> {step.approver_name}</div>}{(step.action_date || step.decided_at) && <div><span className="font-medium">Date:</span> {new Date(step.action_date || step.decided_at).toLocaleString()}</div>}</div>}
          {(step.comment || step.decision_comment) && <div className="mt-3 rounded-md bg-slate-50 p-3 text-sm text-slate-700">{step.comment || step.decision_comment}</div>}
        </div>
      })}
    </div>
  </Card>;
}
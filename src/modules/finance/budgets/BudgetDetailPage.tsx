import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { Printer } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/Table";
import { budgetAction, getBudget } from "./api";

const money = (value: unknown) => Number(value || 0).toLocaleString("id-ID");

export default function BudgetDetailPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["budget", id], queryFn: () => getBudget(id) });
  const budget = query.data;
  const actions = budget?.allowed_actions;
  const act = async (action: string) => {
    await budgetAction(id, action);
    queryClient.invalidateQueries({ queryKey: ["budget", id] });
  };

  return <div className="space-y-4">
    <PageHeader title={budget?.budget_number || "Budget"} description={`${budget?.name || ""} · ${budget?.date_from || ""} to ${budget?.date_to || ""}`} actions={<>
      <Button variant="outline" onClick={() => navigate("/budgets")}>Back</Button>
      <Button variant="outline" onClick={() => window.print()}><Printer size={15} /></Button>
      {actions?.can_submit && <Button onClick={() => act("submit")}>Submit</Button>}
      {actions?.can_approve && <Button onClick={() => act("approve")}>Approve</Button>}
      {actions?.can_reject && <Button variant="danger" onClick={() => act("reject")}>Reject</Button>}
      {actions?.can_lock && <Button onClick={() => act("lock")}>Lock</Button>}
      {actions?.can_cancel && <Button variant="outline" onClick={() => act("cancel")}>Cancel</Button>}
    </>} />
    <Card className="grid gap-3 p-4 md:grid-cols-4"><div>Status<br /><Badge>{budget?.status}</Badge></div><div>Fiscal Year<br /><b>{budget?.fiscal_year}</b></div><div>Total Budget<br /><b className="tabular-nums">{money(budget?.total_budget)}</b></div><div>Approved By<br /><b>{budget?.approved_by || "—"}</b></div></Card>
    <Table variant="grid" stickyHeader><THead><TR><TH>Month</TH><TH>Account</TH><TH>Business Unit</TH><TH>Location</TH><TH>Department</TH><TH className="text-right">Budget</TH><TH>Notes</TH></TR></THead><TBody>{budget?.lines?.map((line: any) => <TR key={line.id}><TD>{line.month}</TD><TD>{line.account_code} — {line.account_name}</TD><TD>{line.business_unit_name || "—"}</TD><TD>{line.location_name || "All"}</TD><TD>{line.department_name || "All"}</TD><TD className="text-right tabular-nums">{money(line.budget_amount)}</TD><TD>{line.notes}</TD></TR>)}</TBody></Table>
    <div className="grid gap-3 md:grid-cols-2"><Card className="p-4"><h2 className="font-semibold">Approval History</h2><p className="text-sm">Approved by {budget?.approved_by || "—"} at {budget?.approved_at || "—"}</p></Card><Card className="p-4"><h2 className="font-semibold">Activity & Attachments</h2><p className="text-sm text-slate-500">Budget actions are recorded in the audit trail. Document attachments use the shared document service.</p></Card></div>
  </div>;
}

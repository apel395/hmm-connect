import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Upload } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import ListToolbar from "@/components/common/ListToolbar";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import useAuthorization from "@/hooks/useAuthorization";
import { exportCsv } from "@/utils/exportCsv";
import PurchaseRequisitionTable from "../components/PurchaseRequisitionTable";
import PurchaseRequisitionForm from "../components/PurchaseRequisitionForm";
import { useCreatePurchaseRequisition, usePurchaseRequisitions } from "../hooks/usePurchaseRequisitions";

export default function PurchaseRequisitionListPage() {
  const navigate = useNavigate();
  const { canPerform } = useAuthorization();
  const canCreate = canPerform("create", ["REQUESTER"]);
  const [scope, setScope] = useState<"active"|"history">("active");
  const [open, setOpen] = useState(false), [keyword, setKeyword] = useState(""), [status, setStatus] = useState("ALL"), [advanced, setAdvanced] = useState(false);
  const query:any = usePurchaseRequisitions(scope);
  const create = useCreatePurchaseRequisition();
  const source:any[] = useMemo(() => Array.isArray(query.data) ? query.data : query.data?.items ?? query.data?.data ?? [], [query.data]);
  const rows = useMemo(() => source.filter((row) => (status === "ALL" || row.status === status) && (!keyword.trim() || [row.pr_number,row.requester_name].filter(Boolean).join(" ").toLowerCase().includes(keyword.toLowerCase()))), [source, keyword, status]);
  const count = (value:string) => source.filter((row) => row.status === value).length;
  const thisMonth = source.filter((row) => row.request_date?.slice(0,7) === new Date().toISOString().slice(0,7)).length;
  const statusSelect = <select className="h-9 rounded-md border border-slate-300 bg-white px-3 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}><option value="ALL">All statuses</option><option value="DRAFT">Draft</option><option value="PENDING_APPROVAL">Waiting Approval</option><option value="APPROVED">Approved</option><option value="CONVERTED">Converted</option><option value="REJECTED">Rejected</option><option value="CANCELLED">Cancelled</option></select>;
  return <div className="space-y-6">
    <PageHeader title="Purchase Requisitions" description="Manage purchasing requests before creating purchase orders." actions={<div className="flex flex-wrap gap-2">{canCreate && <Button onClick={() => setOpen(true)}><Plus size={16}/> Create</Button>}<Button variant="outline" disabled title="PR import is not available yet"><Upload size={16}/> Import</Button><Button variant="outline" onClick={() => exportCsv("purchase-requisitions.csv", ["PR Number","Date","Requester","Status","Total"], rows.map((row) => [row.pr_number,row.request_date,row.requester_name,row.status,row.total_amount]))}>Export</Button><div className="flex"><Button variant={scope === "active" ? "secondary" : "outline"} onClick={() => setScope("active")}>Active</Button><Button variant={scope === "history" ? "secondary" : "outline"} onClick={() => setScope("history")}>History</Button></div></div>}/>
    <ModuleSummary metrics={[{label:"Waiting Approval",value:count("PENDING_APPROVAL")},{label:"Approved",value:count("APPROVED")},{label:"Rejected",value:count("REJECTED")},{label:"This Month",value:thisMonth}]}/>
    <Card className="overflow-hidden p-0"><div className="p-5"><ListToolbar search={keyword} searchPlaceholder="Search PR number or requester..." onSearch={setKeyword} filters={statusSelect} advancedOpen={advanced} onAdvancedToggle={() => setAdvanced(!advanced)} advancedFilters={<div className="max-w-xs">{statusSelect}</div>} onExport={() => exportCsv("purchase-requisitions.csv", ["PR Number","Date","Requester","Status","Total"], rows.map((row) => [row.pr_number,row.request_date,row.requester_name,row.status,row.total_amount]))} onRefresh={() => query.refetch()} footer={<div className="text-xs text-slate-500">Showing {rows.length} requisition{rows.length === 1 ? "" : "s"}</div>}/></div>{query.isLoading ? <div className="py-16"><Loading/></div> : <PurchaseRequisitionTable rows={rows} onView={(row) => navigate(`/purchase-requisitions/${row.id}`)}/>}</Card>
    {open && <PurchaseRequisitionForm onClose={() => setOpen(false)} onSubmit={async (payload) => {await create.mutateAsync(payload); setOpen(false);}}/>}
  </div>;
}

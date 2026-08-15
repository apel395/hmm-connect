import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Upload } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import ListToolbar from "@/components/common/ListToolbar";
import Pagination from "@/components/datatable/Pagination";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import useAuthorization from "@/hooks/useAuthorization";
import { exportCsv } from "@/utils/exportCsv";
import PurchaseRequisitionTable from "../components/PurchaseRequisitionTable";
import PurchaseRequisitionForm from "../components/PurchaseRequisitionForm";
import { useCreatePurchaseRequisition, usePurchaseRequisitions } from "../hooks/usePurchaseRequisitions";

const PAGE_SIZE = 25;

export default function PurchaseRequisitionListPage() {
  const navigate = useNavigate();
  const { canPerform } = useAuthorization();
  const canCreate = canPerform("create", ["REQUESTER"]);
  const [scope, setScope] = useState<"active"|"history">("active");
  const [open, setOpen] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState("ALL");
  const [advanced, setAdvanced] = useState(false);
  const [page, setPage] = useState(1);
  const query: any = usePurchaseRequisitions({
    scope,
    page,
    page_size: PAGE_SIZE,
    search: keyword.trim() || undefined,
    status: status === "ALL" ? undefined : status,
  });
  const create = useCreatePurchaseRequisition();
  const data = query.data ?? {};
  const rows: any[] = data.items ?? [];
  const pages = Math.max(data.total_pages ?? 0, 1);
  const total = data.total_items ?? 0;
  const summary = data.summary ?? {};
  const counts = summary.status_counts ?? {};

  useEffect(() => setPage(1), [scope, keyword, status]);
  useEffect(() => { if (page > pages) setPage(pages); }, [page, pages]);

  const statusSelect = <select className="h-9 rounded-md border border-slate-300 bg-white px-3 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}><option value="ALL">All statuses</option><option value="DRAFT">Draft</option><option value="PENDING_APPROVAL">Waiting Approval</option><option value="APPROVED">Approved</option><option value="CONVERTED">Converted</option><option value="REJECTED">Rejected</option><option value="CANCELLED">Cancelled</option></select>;

  return <div className="space-y-6">
    <PageHeader title="Purchase Requisitions" description="Manage purchasing requests before creating purchase orders." actions={<div className="flex flex-wrap gap-2">{canCreate && <Button onClick={() => setOpen(true)}><Plus size={16}/> Create</Button>}<Button variant="outline" disabled title="PR import is not available yet"><Upload size={16}/> Import</Button><Button variant="outline" onClick={() => exportCsv("purchase-requisitions-page.csv", ["PR Number","Date","Requester","Status","Total"], rows.map((row) => [row.pr_number,row.request_date,row.requester_name,row.status,row.total_amount]))}>Export Page</Button><div className="flex"><Button variant={scope === "active" ? "secondary" : "outline"} onClick={() => setScope("active")}>Active</Button><Button variant={scope === "history" ? "secondary" : "outline"} onClick={() => setScope("history")}>History</Button></div></div>}/>
    <ModuleSummary metrics={[{label:"Waiting Approval",value:counts.PENDING_APPROVAL ?? 0},{label:"Approved",value:counts.APPROVED ?? 0},{label:"Rejected",value:counts.REJECTED ?? 0},{label:"This Month",value:summary.this_month ?? 0}]}/>
    <Card className="overflow-hidden p-0"><div className="p-5"><ListToolbar search={keyword} searchPlaceholder="Search PR number or requester..." onSearch={setKeyword} filters={statusSelect} advancedOpen={advanced} onAdvancedToggle={() => setAdvanced(!advanced)} advancedFilters={<div className="max-w-xs">{statusSelect}</div>} onExport={() => exportCsv("purchase-requisitions-page.csv", ["PR Number","Date","Requester","Status","Total"], rows.map((row) => [row.pr_number,row.request_date,row.requester_name,row.status,row.total_amount]))} onRefresh={() => query.refetch()} footer={<div className="text-xs text-slate-500">{total} requisition{total === 1 ? "" : "s"} match current filters</div>}/></div>{query.isLoading ? <div className="py-16"><Loading/></div> : <><PurchaseRequisitionTable rows={rows} onView={(row) => navigate(`/purchase-requisitions/${row.id}`)}/><div className="px-5 pb-5"><Pagination page={page} pages={pages} total={total} pageSize={PAGE_SIZE} noun="requisitions" onChange={setPage}/></div></>}</Card>
    {open && <PurchaseRequisitionForm onClose={() => setOpen(false)} onSubmit={async (payload) => {await create.mutateAsync(payload); setOpen(false);}}/>}
  </div>;
}

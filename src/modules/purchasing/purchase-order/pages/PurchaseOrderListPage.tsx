import { useEffect, useMemo, useState } from "react";
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
import PurchaseOrderTable from "../components/PurchaseOrderTable";
import PurchaseOrderForm from "../components/PurchaseOrderForm";
import { useCreatePurchaseOrder, usePurchaseOrders } from "../hooks/usePurchaseOrders";
import type { PurchaseOrder, PurchaseOrderPage as PurchaseOrderPageData } from "../types";

type Scope = "active" | "history" | "all";

function errorMessage(error: unknown) {
  const candidate = error as { response?: { data?: { detail?: string } }; message?: string };
  return candidate.response?.data?.detail ?? candidate.message ?? "Unable to load purchase orders.";
}

export default function PurchaseOrderListPage() {
  const navigate = useNavigate();
  const { canPerform } = useAuthorization();
  const canCreate = canPerform("create", ["PURCHASING"]);
  const [scope, setScope] = useState<Scope>("all");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("ALL");
  const [advanced, setAdvanced] = useState(false);
  const [open, setOpen] = useState(false);
  const query = usePurchaseOrders(scope, page, 20, status === "ALL" ? undefined : status);
  const result = query.data as PurchaseOrderPageData | undefined;
  const source = result?.items ?? [];
  const create = useCreatePurchaseOrder();

  useEffect(() => setPage(1), [scope, status]);
  const rows = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return source;
    return source.filter((order) => [order.po_number, order.source_pr_number, order.supplier_name, order.department_name, order.location_name, order.order_date, order.expected_date]
      .filter(Boolean).join(" ").toLowerCase().includes(term));
  }, [source, search]);
  const count = (value: string) => source.filter((row) => row.status === value).length;
  const csv = () => exportCsv("purchase-orders.csv", ["PO Number", "Supplier", "Order Date", "Expected Date", "Status", "Total"], rows.map((row: PurchaseOrder) => [row.po_number, row.supplier_name, row.order_date, row.expected_date, row.status, row.total_amount]));
  const statusSelect = <select className="h-9 rounded-md border border-slate-300 bg-white px-3 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}><option value="ALL">All statuses</option><option value="DRAFT">Draft</option><option value="PENDING_APPROVAL">Waiting Approval</option><option value="APPROVED">Approved</option><option value="PARTIALLY_RECEIVED">Partially Received</option><option value="RECEIVED">Fully Received</option><option value="REJECTED">Rejected</option></select>;

  return <><div className="space-y-6">
    <PageHeader title="Purchase Orders" description="Manage supplier orders and receiving progress." actions={<div className="flex flex-wrap gap-2">{canCreate && <Button onClick={() => setOpen(true)}><Plus size={16}/> Create</Button>}<Button variant="outline" disabled title="PO import is not available yet"><Upload size={16}/> Import</Button><Button variant="outline" onClick={csv}>Export</Button><div className="flex"><Button variant={scope === "all" ? "secondary" : "outline"} onClick={() => setScope("all")}>All</Button><Button variant={scope === "active" ? "secondary" : "outline"} onClick={() => setScope("active")}>Active</Button><Button variant={scope === "history" ? "secondary" : "outline"} onClick={() => setScope("history")}>History</Button></div></div>}/>
    <ModuleSummary metrics={[{label:"Waiting Approval",value:count("PENDING_APPROVAL")},{label:"Approved",value:count("APPROVED")},{label:"Partially Received",value:count("PARTIALLY_RECEIVED")},{label:"Fully Received",value:count("RECEIVED")}]}/>
    <Card className="overflow-hidden p-0"><div className="p-5"><ListToolbar search={search} searchPlaceholder="Search PO number, supplier, or date..." onSearch={setSearch} filters={statusSelect} advancedOpen={advanced} onAdvancedToggle={() => setAdvanced(!advanced)} advancedFilters={<div className="max-w-xs">{statusSelect}</div>} onExport={csv} onRefresh={() => query.refetch()} footer={<div className="text-xs text-slate-500">Showing {rows.length} of {result?.total_items ?? 0} purchase orders</div>}/></div>
      {query.isLoading ? <div className="py-12"><Loading/></div> : query.isError ? <div role="alert" className="m-5 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700"><div className="font-semibold">Purchase orders could not be loaded</div><div className="mt-1">{errorMessage(query.error)}</div><Button className="mt-3" size="sm" variant="outline" onClick={() => query.refetch()}>Try again</Button></div> : <PurchaseOrderTable rows={rows} onView={(row) => navigate(`/purchase-orders/${row.id}`)}/>}
      {!query.isLoading && !query.isError && (result?.total_pages ?? 0) > 1 && <div className="flex items-center justify-end gap-3 border-t p-4"><Button size="sm" variant="outline" disabled={!result?.has_previous} onClick={() => setPage((value) => value - 1)}>Previous</Button><span className="text-sm">Page {result?.page} of {result?.total_pages}</span><Button size="sm" variant="outline" disabled={!result?.has_next} onClick={() => setPage((value) => value + 1)}>Next</Button></div>}
    </Card>
  </div><PurchaseOrderForm open={open} loading={create.isPending} onClose={() => setOpen(false)} onSubmit={async (payload) => {await create.mutateAsync(payload); setOpen(false);}}/></>;
}

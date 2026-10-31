import PurchasingPagePrintButton from "@/components/print/PurchasingPagePrintButton";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {Plus} from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import ListToolbar from "@/components/common/ListToolbar";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import DateRangeFilter from "@/components/common/DateRangeFilter";
import useAuthorization from "@/hooks/useAuthorization";
import { exportCsv } from "@/utils/exportCsv";
import PurchasingExceptionPanel from "../../reports/PurchasingExceptionPanel";
import PurchaseOrderTable from "../components/PurchaseOrderTable";
import PurchaseOrderForm from "../components/PurchaseOrderForm";
import { useCreatePurchaseOrder, usePurchaseOrders } from "../hooks/usePurchaseOrders";
import type { PurchaseOrder, PurchaseOrderPage as PurchaseOrderPageData } from "../types";

type Scope = "active" | "history" | "all";
type PurchaseOrderResult = PurchaseOrderPageData & { summary?: Record<string, number> };

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
  const [pageSize, setPageSize] = useState(() => Number(window.localStorage.getItem("purchase-orders-page-size")) === 100 ? 100 : 50);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [status, setStatus] = useState("ALL");
  const [advanced, setAdvanced] = useState(false);
  const [open, setOpen] = useState(false);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [appliedDateFrom, setAppliedDateFrom] = useState("");
  const [appliedDateTo, setAppliedDateTo] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);
  useEffect(() => setPage(1), [scope, status, debouncedSearch, appliedDateFrom, appliedDateTo, pageSize]);
  useEffect(() => window.localStorage.setItem("purchase-orders-page-size", String(pageSize)), [pageSize]);

  const query = usePurchaseOrders(scope, page, pageSize, status === "ALL" ? undefined : status, debouncedSearch || undefined, appliedDateFrom || undefined, appliedDateTo || undefined);
  const result = query.data as PurchaseOrderResult | undefined;
  const rows = useMemo(() => result?.items ?? [], [result?.items]);
  const create = useCreatePurchaseOrder();
  const summary = result?.summary ?? {};
  const count = (value: string) => Number(summary[value] ?? 0);
  const csv = () => exportCsv("purchase-orders.csv", ["PO Number", "Supplier", "Order Date", "Expected Date", "Status", "Total"], rows.map((row: PurchaseOrder) => [row.po_number, row.supplier_name, row.order_date, row.expected_date, row.status, row.total_amount]));
  const statusSelect = <select className="h-9 rounded-md border border-slate-300 bg-white px-3 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}><option value="ALL">All statuses</option><option value="DRAFT">Draft</option><option value="PENDING_APPROVAL">Waiting Approval</option><option value="APPROVED">Approved</option><option value="PARTIALLY_RECEIVED">Partially Received</option><option value="RECEIVED">Fully Received</option><option value="REJECTED">Rejected</option></select>;
  const dateFilter = <DateRangeFilter from={dateFrom} to={dateTo} onFromChange={setDateFrom} onToChange={setDateTo} onApply={() => { setAppliedDateFrom(dateFrom); setAppliedDateTo(dateTo); }} onClear={() => { setDateFrom(""); setDateTo(""); setAppliedDateFrom(""); setAppliedDateTo(""); }} />;

  return <><div className="space-y-6">
    <PageHeader title="Purchase Orders" description="Manage supplier orders and receiving progress." actions={<div className="flex flex-wrap gap-2">{canCreate && <Button onClick={() => setOpen(true)}><Plus size={16}/> Create</Button>}<div className="flex"><Button variant={scope === "all" ? "secondary" : "outline"} onClick={() => setScope("all")}>All</Button><Button variant={scope === "active" ? "secondary" : "outline"} onClick={() => setScope("active")}>Active</Button><Button variant={scope === "history" ? "secondary" : "outline"} onClick={() => setScope("history")}>History</Button></div>  <PurchasingPagePrintButton kind="PURCHASE_ORDER_LIST"/>
</div>}/>
    <PurchasingExceptionPanel dateFrom="" dateTo="" />
    <ModuleSummary metrics={[{label:"Waiting Approval",value:count("PENDING_APPROVAL")},{label:"Approved",value:count("APPROVED")},{label:"Partially Received",value:count("PARTIALLY_RECEIVED")},{label:"Fully Received",value:count("RECEIVED")}]}/>
    <Card className="overflow-hidden p-0"><div className="p-3"><ListToolbar search={search} searchPlaceholder="Search PO number, supplier, or reference..." onSearch={setSearch} filters={statusSelect} advancedOpen={advanced} onAdvancedToggle={() => setAdvanced(!advanced)} advancedFilters={<div className="space-y-3"><div className="max-w-xs">{statusSelect}</div>{dateFilter}</div>} onExport={csv} onRefresh={() => query.refetch()} footer={<div className="text-xs text-slate-500">Showing {rows.length} of {result?.total_items ?? 0} purchase orders</div>}/></div>
      {query.isLoading ? <div className="py-12"><Loading/></div> : query.isError ? <div role="alert" className="m-5 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700"><div className="font-semibold">Purchase orders could not be loaded</div><div className="mt-1">{errorMessage(query.error)}</div><Button className="mt-3" size="sm" variant="outline" onClick={() => query.refetch()}>Try again</Button></div> : <PurchaseOrderTable rows={rows} onView={(row) => navigate(`/purchase-orders/${row.id}`)}/>}
      {!query.isLoading && !query.isError && <div className="flex flex-wrap items-center justify-between gap-2 border-t px-3 py-2 text-xs"><label>Rows per page <select className="ml-1 rounded border border-slate-300 bg-white px-2 py-1" value={pageSize} onChange={e => { setPageSize(Number(e.target.value)); setPage(1); }}><option value={50}>50</option><option value={100}>100</option></select></label><div className="flex items-center gap-2"><span>{result?.total_items ?? 0} orders · Page {result?.page ?? 1} of {Math.max(result?.total_pages ?? 0, 1)}</span><Button size="sm" variant="outline" disabled={!result?.has_previous} onClick={() => setPage((value) => value - 1)}>Previous</Button><Button size="sm" variant="outline" disabled={!result?.has_next} onClick={() => setPage((value) => value + 1)}>Next</Button></div></div>}
    </Card>
  </div><PurchaseOrderForm open={open} loading={create.isPending} onClose={() => setOpen(false)} onSubmit={async (payload) => {await create.mutateAsync(payload); setOpen(false);}}/></>;
}

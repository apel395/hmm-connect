import PurchasingPagePrintButton from "@/components/print/PurchasingPagePrintButton";
import ListToolbar from "@/components/common/ListToolbar";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import Pagination from "@/components/datatable/Pagination";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import useAuthorization from "@/hooks/useAuthorization";
import { exportCsv } from "@/utils/exportCsv";
import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { PurchasingStatusBadge } from "../components/PurchasingDocumentUI";
import MarketListForm from "./MarketListForm";
import { useCreateMarketList, useMarketLists } from "./useMarketLists";

const money = (value: unknown) =>
  Number(value ?? 0).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

export default function MarketListPage() {
  const nav = useNavigate();
  const { canPerform } = useAuthorization();
  const canCreate = canPerform("create", ["REQUESTER"], true, "market_list.create");
  const [scope, setScope] = useState<"active" | "history">("active");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [status, setStatus] = useState("ALL");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(() =>
    Number(window.localStorage.getItem("market-lists-page-size")) === 100 ? 100 : 50,
  );
  const [open, setOpen] = useState(false);

  const query = useMarketLists({
    scope,
    page,
    page_size: pageSize,
    search: debouncedSearch || undefined,
    status: status === "ALL" ? undefined : status,
  });
  const create = useCreateMarketList();
  const data: any = query.data ?? {};
  const rows: any[] = data.items ?? [];
  const pages = Math.max(data.total_pages ?? 0, 1);
  const total = data.total_items ?? 0;
  const counts = data.summary?.status_counts ?? {};

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);
  useEffect(() => setPage(1), [scope, debouncedSearch, status, pageSize]);
  useEffect(() => window.localStorage.setItem("market-lists-page-size", String(pageSize)), [pageSize]);
  useEffect(() => { if (page > pages) setPage(pages); }, [page, pages]);

  const statusSelect = (
    <select
      className="h-9 rounded-md border border-slate-300 bg-white px-3 text-sm"
      value={status}
      onChange={(event) => setStatus(event.target.value)}
    >
      <option value="ALL">All statuses</option>
      <option value="DRAFT">Draft</option>
      <option value="PENDING_APPROVAL">Waiting Approval</option>
      <option value="APPROVED">Approved</option>
      <option value="CONVERTED">Converted</option>
      <option value="REJECTED">Rejected</option>
    </select>
  );

  const exportPage = () => exportCsv("market-lists.csv", ["ML Number", "Date", "Requester", "Status", "Total"], rows.map((row) => [row.ml_number, row.request_date, row.requester_name, row.status, row.total_amount]));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Market List"
        description="Requests for food and beverage items purchased from the local market."
        actions={
          <div className="flex flex-wrap gap-2">
            {canCreate && <Button onClick={() => setOpen(true)}><Plus size={16} /> Create Market List</Button>}
            <div className="flex">
              <Button variant={scope === "active" ? "secondary" : "outline"} onClick={() => setScope("active")}>Active</Button>
              <Button variant={scope === "history" ? "secondary" : "outline"} onClick={() => setScope("history")}>History</Button>
            </div>
            <PurchasingPagePrintButton kind="MARKET_LIST_LIST" />
          </div>
        }
      />
      <ModuleSummary metrics={[
        { label: "Waiting Approval", value: counts.PENDING_APPROVAL ?? 0 },
        { label: "Approved", value: counts.APPROVED ?? 0 },
        { label: "Converted", value: counts.CONVERTED ?? 0 },
        { label: "This Month", value: data.summary?.this_month ?? 0 },
      ]} />
      <Card className="overflow-hidden p-0">
        <div className="p-3">
          <ListToolbar
            search={search}
            searchPlaceholder="Search ML number or requester..."
            onSearch={setSearch}
            filters={statusSelect}
            onExport={exportPage}
            exportLabel="Export current page CSV"
            onRefresh={() => query.refetch()}
            footer={<div className="text-xs text-slate-500">{total} Market List{total === 1 ? "" : "s"} match current filters</div>}
          />
        </div>
        {query.isLoading ? (
          <div className="py-16"><Loading /></div>
        ) : query.isError ? (
          <div role="alert" className="m-5 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            <div className="font-semibold">Market Lists could not be loaded</div>
            <Button className="mt-3" size="sm" variant="outline" onClick={() => query.refetch()}>Try again</Button>
          </div>
        ) : (
          <>
            <Table className="min-w-[900px]" containerClassName="rounded-none border-x-0 shadow-none">
              <THead>
                <TR className="whitespace-nowrap">
                  <TH>ML Number</TH>
                  <TH>Date</TH>
                  <TH>Requester</TH>
                  <TH>Business Unit</TH>
                  <TH>Location</TH>
                  <TH>Status</TH>
                  <TH numeric>Total</TH>
                  <TH numeric>Actions</TH>
                </TR>
              </THead>
              <TBody>
                {rows.map((row) => (
                  <TR key={row.id}>
                    <TD><TableCellStack primary={row.ml_number} secondary={row.expiry_date ? `Expires ${row.expiry_date}` : undefined} /></TD>
                    <TD>{row.request_date ?? "—"}</TD>
                    <TD>{row.requester_name ?? "—"}</TD>
                    <TD>{row.business_unit_name ?? "—"}</TD>
                    <TD>{row.location_name ?? "—"}</TD>
                    <TD><PurchasingStatusBadge value={row.status} /></TD>
                    <TD numeric className="font-semibold tabular-nums">{money(row.total_amount)}</TD>
                    <TD numeric><Button size="sm" variant="outline" onClick={() => nav(`/market-lists/${row.id}`)}>View</Button></TD>
                  </TR>
                ))}
                {!rows.length && <TR><TD colSpan={8} className="p-10 text-center text-slate-500">No Market Lists found.</TD></TR>}
              </TBody>
            </Table>
            <div className="flex flex-wrap items-center justify-between gap-2 border-t px-3 py-2">
              <label className="text-xs">
                Rows per page
                <select
                  className="ml-1 rounded border border-slate-300 bg-white px-2 py-1"
                  value={pageSize}
                  onChange={(event) => setPageSize(Number(event.target.value))}
                >
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </label>
              <Pagination page={page} pages={pages} total={total} pageSize={pageSize} noun="market lists" onChange={setPage} />
            </div>
          </>
        )}
      </Card>
      {open && (
        <MarketListForm
          onClose={() => setOpen(false)}
          onSubmit={async (payload) => {
            await create.mutateAsync(payload);
            setOpen(false);
          }}
        />
      )}
    </div>
  );
}

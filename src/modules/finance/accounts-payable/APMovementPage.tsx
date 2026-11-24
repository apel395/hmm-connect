import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import api from "@/api/client";
import ListToolbar from "@/components/common/ListToolbar";
import ModuleSummary from "@/components/common/ModuleSummary";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import SearchableSelect from "@/components/form/SearchableSelect";
import Card, { CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import { FORM_UI } from "@/config/formUi";
import { listLocations } from "@/modules/admin/organization/api";
import { supplierApi } from "@/modules/master/suppliers/api/supplierApi";
import { todayLocal } from "@/utils/dateConstraints";
import { exportCsv } from "@/utils/exportCsv";
import APWorkspaceHeader from "./APWorkspaceHeader";

type MovementRow = {
  id: string | number;
  movement_date: string;
  supplier_id?: number | null;
  supplier_name?: string | null;
  document_type: string;
  document_id?: number | null;
  document_number?: string | null;
  supplier_reference?: string | null;
  movement_type: "INVOICE" | "PAYMENT" | "ADJUSTMENT" | "OPENING" | string;
  increase: number | string;
  decrease: number | string;
  running_balance: number | string;
  status?: string | null;
  unallocated_amount?: number | string | null;
};

type MovementResponse = {
  items: MovementRow[];
  summary: {
    opening_balance: number | string;
    invoice_total: number | string;
    payment_total: number | string;
    adjustment_total: number | string;
    closing_balance: number | string;
    opening_unassigned?: boolean;
  };
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
};

const today = todayLocal();
const yearStart = `${today.slice(0, 4)}-01-01`;
const PAGE_SIZE = 50;
const money = (value: unknown) =>
  Number(value || 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const movementLink = (row: MovementRow) => {
  if (!row.document_id) return null;
  if (row.document_type === "SUPPLIER_INVOICE") return `/supplier-invoices/${row.document_id}`;
  if (row.document_type === "SUPPLIER_PAYMENT") return `/payments/${row.document_id}`;
  if (row.document_type === "SUPPLIER_ADJUSTMENT") return `/supplier-adjustments`;
  return null;
};

const movementLabel = (type: string) =>
  ({ OPENING: "Opening", INVOICE: "Supplier Invoice", PAYMENT: "Payment", ADJUSTMENT: "Credit / Debit Note" }[type] ?? type.replaceAll("_", " "));

export default function APMovementPage() {
  const [page, setPage] = useState(1);
  const [draft, setDraft] = useState({
    date_from: yearStart,
    date_to: today,
    supplier_id: undefined as number | undefined,
    location_id: undefined as number | undefined,
    movement_type: "",
    search: "",
  });
  const [filters, setFilters] = useState(draft);
  const invalidPeriod = draft.date_from > draft.date_to;

  const suppliers = useQuery({ queryKey: ["ap-movement-suppliers"], queryFn: () => supplierApi.lookup("", 100) });
  const locations = useQuery({
    queryKey: ["ap-movement-locations"],
    queryFn: () => listLocations({ is_active: true }),
  });
  const movement = useQuery({
    queryKey: ["ap-movement", filters, page],
    enabled: !invalidPeriod,
    queryFn: async () =>
      (
        await api.get<MovementResponse>("/ap-movement", {
          params: {
            ...filters,
            supplier_id: filters.supplier_id || undefined,
            location_id: filters.location_id || undefined,
            movement_type: filters.movement_type || undefined,
            search: filters.search || undefined,
            page,
            page_size: PAGE_SIZE,
          },
        })
      ).data,
  });

  const rows = useMemo(() => movement.data?.items ?? [], [movement.data?.items]);
  const pageTotals = useMemo(
    () =>
      rows.reduce(
        (sum, row) => ({
          increase: sum.increase + Number(row.increase || 0),
          decrease: sum.decrease + Number(row.decrease || 0),
        }),
        { increase: 0, decrease: 0 },
      ),
    [rows],
  );

  const supplierOptions = (suppliers.data ?? []).map((row: any) => ({
    id: row.id,
    label: `${row.code} — ${row.name}`,
    keywords: [row.code ?? "", row.name ?? ""],
  }));
  const locationOptions = (locations.data ?? []).map((row: any) => ({
    id: row.id,
    label: `${row.code} — ${row.name}`,
    keywords: [row.code ?? "", row.name ?? ""],
  }));

  const apply = () => {
    setPage(1);
    setFilters({ ...draft, search: draft.search.trim() });
  };

  const exportPage = () =>
    exportCsv(
      "ap-movement.csv",
      ["Date", "Supplier", "Document", "Movement", "Increase", "Decrease", "Running AP", "Status"],
      rows.map((row) => [
        row.movement_date,
        row.supplier_name,
        row.document_number,
        movementLabel(row.movement_type),
        row.increase,
        row.decrease,
        row.running_balance,
        row.status,
      ]),
    );

  const inputClass = `${FORM_UI.controlBase} ${FORM_UI.density.compact.control}`;

  return (
    <DataWorkspace area="Accounting" className="data-first">
      <div className="space-y-2">
        <PageHeader
          title="AP Movement"
          description="Follow posted invoices, payments, and adjustments through the AP balance. Open a document to review its details."
          actions={
            <Button size="sm" variant="outline" onClick={() => movement.refetch()}>
              Refresh
            </Button>
          }
        >
          <div className="mt-0.5 text-[11px] text-slate-500">Posted document activity · {filters.date_from} → {filters.date_to}</div>
        </PageHeader>
        <APWorkspaceHeader />

        {invalidPeriod && (
          <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            From date must be on or before To date.
          </div>
        )}

        <Card className="overflow-hidden p-0">
          <div className="p-3 print:hidden">
            <ListToolbar
              search={draft.search}
              searchPlaceholder="Document number, supplier reference, or supplier name..."
              onSearch={(value) => setDraft({ ...draft, search: value })}
              onExport={exportPage}
              onRefresh={() => movement.refetch()}
              filters={
                <>
                  <label className="inline-flex items-center gap-1 text-xs text-slate-600">
                    From
                    <input
                      aria-label="From date"
                      type="date"
                      className={`${inputClass} w-36`}
                      value={draft.date_from}
                      onChange={(event) => setDraft({ ...draft, date_from: event.target.value })}
                    />
                  </label>
                  <label className="inline-flex items-center gap-1 text-xs text-slate-600">
                    To
                    <input
                      aria-label="To date"
                      type="date"
                      className={`${inputClass} w-36`}
                      value={draft.date_to}
                      onChange={(event) => setDraft({ ...draft, date_to: event.target.value })}
                    />
                  </label>
                  <div className="w-48">
                    <SearchableSelect
                      label="Supplier"
                      value={draft.supplier_id}
                      placeholder="All suppliers"
                      options={supplierOptions}
                      onChange={(value) => setDraft({ ...draft, supplier_id: value })}
                    />
                  </div>
                  <div className="w-48">
                    <SearchableSelect
                      label="Location"
                      value={draft.location_id}
                      placeholder="All locations"
                      options={locationOptions}
                      onChange={(value) => setDraft({ ...draft, location_id: value })}
                    />
                  </div>
                  <label className="inline-flex items-center gap-1 text-xs text-slate-600">
                    Movement
                    <select
                      aria-label="Movement type"
                      className={`${inputClass} w-40`}
                      value={draft.movement_type}
                      onChange={(event) => setDraft({ ...draft, movement_type: event.target.value })}
                    >
                      <option value="">All movements</option>
                      <option value="OPENING">Opening</option>
                      <option value="INVOICE">Supplier Invoice</option>
                      <option value="PAYMENT">Payment</option>
                      <option value="ADJUSTMENT">Credit / Debit Note</option>
                    </select>
                  </label>
                  <Button size="sm" disabled={invalidPeriod} onClick={apply}>Apply</Button>
                </>
              }
            />
          </div>

          {movement.data?.summary?.opening_unassigned && (
            <div role="status" className="mx-3 mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              The manual opening AP is recorded by account and cannot be assigned to this supplier or AP user. These balances show document activity only.
            </div>
          )}

          {!!movement.data && (
            <div className="px-3 pb-2">
              <ModuleSummary
                metrics={[
                  {
                    label: movement.data.summary.opening_unassigned ? "Brought forward activity" : "Opening AP",
                    value: money(movement.data.summary.opening_balance),
                  },
                  { label: "Invoices +", value: money(movement.data.summary.invoice_total) },
                  { label: "Payments −", value: money(movement.data.summary.payment_total) },
                  { label: "Adjustments", value: money(movement.data.summary.adjustment_total) },
                  {
                    label: movement.data.summary.opening_unassigned ? "Closing activity" : "Closing AP",
                    value: money(movement.data.summary.closing_balance),
                    note: "Includes the complete filtered period",
                  },
                ]}
              />
            </div>
          )}

          {invalidPeriod ? (
            <div className="m-3 rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
              Set a valid date range to load AP movement.
            </div>
          ) : movement.isPending ? (
            <div className="p-10 text-center text-sm text-slate-500">Loading AP movement…</div>
          ) : movement.isError ? (
            <div role="alert" className="m-3 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <div className="font-semibold">AP Movement could not be loaded.</div>
              <Button className="mt-3" size="sm" variant="outline" onClick={() => movement.refetch()}>Try again</Button>
            </div>
          ) : (
            <>
              <CardHeader>
                <div>
                  <CardTitle className="text-sm">Document Activity</CardTitle>
                  <CardDescription>Page increase {money(pageTotals.increase)} · page decrease {money(pageTotals.decrease)}</CardDescription>
                </div>
              </CardHeader>
              <Table className="min-w-[1120px]" containerClassName="rounded-none border-x-0 border-b-0 shadow-none">
                <THead>
                  <TR>
                    <TH>Date</TH>
                    <TH>Supplier</TH>
                    <TH>Document</TH>
                    <TH>Movement</TH>
                    <TH numeric>Increase</TH>
                    <TH numeric>Decrease</TH>
                    <TH numeric>Running AP</TH>
                    <TH>Status</TH>
                  </TR>
                </THead>
                <TBody>
                  {rows.map((row) => {
                    const link = movementLink(row);
                    return (
                      <TR key={row.id}>
                        <TD className="whitespace-nowrap">{row.movement_date}</TD>
                        <TD>{row.supplier_name || "—"}</TD>
                        <TD>
                          <TableCellStack
                            primary={
                              link ? (
                                <Link className="font-medium text-emerald-700 hover:underline" to={link}>
                                  {row.document_number || "—"}
                                </Link>
                              ) : (
                                row.document_number || "—"
                              )
                            }
                            secondary={
                              row.unallocated_amount && Number(row.unallocated_amount) > 0
                                ? `Unallocated payment: Rp ${money(row.unallocated_amount)}`
                                : row.supplier_reference || undefined
                            }
                          />
                        </TD>
                        <TD>{movementLabel(row.movement_type)}</TD>
                        <TD numeric>{money(row.increase)}</TD>
                        <TD numeric>{money(row.decrease)}</TD>
                        <TD numeric className="font-semibold tabular-nums">{money(row.running_balance)}</TD>
                        <TD>{row.status || "—"}</TD>
                      </TR>
                    );
                  })}
                  {!rows.length && (
                    <TR><TD colSpan={8} className="p-10 text-center text-slate-500">No AP movements match these filters.</TD></TR>
                  )}
                </TBody>
              </Table>
              <div className="px-3 pb-2">
                <Pagination
                  page={page}
                  pages={movement.data?.total_pages ?? 1}
                  total={movement.data?.total_items ?? 0}
                  pageSize={PAGE_SIZE}
                  noun="movements"
                  onChange={setPage}
                />
              </div>
            </>
          )}
        </Card>
      </div>
    </DataWorkspace>
  );
}

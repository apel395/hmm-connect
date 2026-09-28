import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import api from "@/api/client";
import APWorkspaceHeader from "./APWorkspaceHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import SearchableSelect from "@/components/form/SearchableSelect";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import { supplierApi } from "@/modules/master/suppliers/api/supplierApi";
import { listLocations } from "@/modules/admin/organization/api";

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
};

type MovementResponse = {
  items: MovementRow[];
  summary: {
    opening_balance: number | string;
    invoice_total: number | string;
    payment_total: number | string;
    adjustment_total: number | string;
    closing_balance: number | string;
  };
  page: number;
  page_size: number;
  total_items: number;
  has_next: boolean;
  has_previous: boolean;
};

const today = new Date().toISOString().slice(0, 10);
const yearStart = `${today.slice(0, 4)}-01-01`;
const money = (value: unknown) =>
  Number(value || 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const movementLink = (row: MovementRow) => {
  if (!row.document_id) return null;
  if (row.document_type === "SUPPLIER_INVOICE") return `/supplier-invoices/${row.document_id}`;
  if (row.document_type === "SUPPLIER_PAYMENT") return `/payments/${row.document_id}`;
  if (row.document_type === "SUPPLIER_ADJUSTMENT") return `/supplier-adjustments`;
  return null;
};

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

  const suppliers = useQuery({
    queryKey: ["ap-movement-suppliers"],
    queryFn: () => supplierApi.lookup("", 100),
  });
  const locations = useQuery({
    queryKey: ["ap-movement-locations"],
    queryFn: () => listLocations({ is_active: true }),
  });
  const movement = useQuery({
    queryKey: ["ap-movement", filters, page],
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
            page_size: 50,
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

  return (
    <div className="space-y-5">
      <APWorkspaceHeader />

      <div>
        <h1 className="text-2xl font-semibold text-slate-900">AP Movement</h1>
        <p className="mt-1 text-sm text-slate-500">
          Trace supplier invoices, payments, and adjustments into the Accounts Payable balance.
        </p>
      </div>

      <Card>
        <form
          className="grid gap-3 md:grid-cols-3 xl:grid-cols-6"
          onSubmit={(event) => {
            event.preventDefault();
            setPage(1);
            setFilters({ ...draft });
          }}
        >
          <label className="text-sm">
            From
            <input className="mt-1 h-10 w-full rounded-md border px-3" type="date" value={draft.date_from} onChange={(e) => setDraft({ ...draft, date_from: e.target.value })} />
          </label>
          <label className="text-sm">
            To
            <input className="mt-1 h-10 w-full rounded-md border px-3" type="date" value={draft.date_to} onChange={(e) => setDraft({ ...draft, date_to: e.target.value })} />
          </label>
          <SearchableSelect label="Supplier" value={draft.supplier_id} placeholder="All suppliers" options={supplierOptions} onChange={(supplier_id) => setDraft({ ...draft, supplier_id })} />
          <SearchableSelect label="Location" value={draft.location_id} placeholder="All locations" options={locationOptions} onChange={(location_id) => setDraft({ ...draft, location_id })} />
          <label className="text-sm">
            Movement
            <select className="mt-1 h-10 w-full rounded-md border px-3" value={draft.movement_type} onChange={(e) => setDraft({ ...draft, movement_type: e.target.value })}>
              <option value="">All movements</option>
              <option value="OPENING">Opening</option>
              <option value="INVOICE">Supplier Invoice</option>
              <option value="PAYMENT">Payment</option>
              <option value="ADJUSTMENT">Credit / Debit Note</option>
            </select>
          </label>
          <div className="flex items-end">
            <Button type="submit" className="w-full">Apply</Button>
          </div>
          <label className="text-sm md:col-span-3 xl:col-span-6">
            Search
            <input className="mt-1 h-10 w-full rounded-md border px-3" placeholder="Document number, supplier reference, or supplier name..." value={draft.search} onChange={(e) => setDraft({ ...draft, search: e.target.value })} />
          </label>
        </form>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Metric label="Opening AP" value={money(movement.data?.summary?.opening_balance)} />
        <Metric label="Invoices +" value={money(movement.data?.summary?.invoice_total)} />
        <Metric label="Payments −" value={money(movement.data?.summary?.payment_total)} />
        <Metric label="Adjustments" value={money(movement.data?.summary?.adjustment_total)} />
        <Metric label="Closing AP" value={money(movement.data?.summary?.closing_balance)} strong />
      </div>

      <Card className="p-0">
        {movement.isLoading ? (
          <div className="p-10 text-center text-sm text-slate-500">Loading AP movement…</div>
        ) : movement.isError ? (
          <div className="p-10 text-center text-sm text-amber-700">
            AP Movement data endpoint is not available yet.
          </div>
        ) : (
          <>
            <Table variant="grid" className="min-w-[1120px]">
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
                          primary={link ? <Link className="font-medium text-emerald-700 hover:underline" to={link}>{row.document_number || "—"}</Link> : row.document_number || "—"}
                          secondary={row.supplier_reference || undefined}
                        />
                      </TD>
                      <TD>{row.movement_type.replaceAll("_", " ")}</TD>
                      <TD numeric>{money(row.increase)}</TD>
                      <TD numeric>{money(row.decrease)}</TD>
                      <TD numeric className="font-semibold">{money(row.running_balance)}</TD>
                      <TD>{row.status || "—"}</TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3 text-sm">
              <div>
                Page increase <b>{money(pageTotals.increase)}</b> · Page decrease <b>{money(pageTotals.decrease)}</b>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" disabled={!movement.data?.has_previous} onClick={() => setPage(Math.max(1, page - 1))}>Previous</Button>
                <Button variant="outline" disabled={!movement.data?.has_next} onClick={() => setPage(page + 1)}>Next</Button>
              </div>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}

function Metric({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <Card className="p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-xl tabular-nums ${strong ? "font-bold text-slate-950" : "font-semibold"}`}>{value}</div>
    </Card>
  );
}

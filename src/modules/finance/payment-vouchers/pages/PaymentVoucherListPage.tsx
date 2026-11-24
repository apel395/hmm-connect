import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Printer } from "lucide-react";
import APWorkspaceHeader from "@/modules/finance/accounts-payable/APWorkspaceHeader";
import DateRangeFilter from "@/components/common/DateRangeFilter";
import ListToolbar from "@/components/common/ListToolbar";
import ModuleSummary, { type SummaryMetric } from "@/components/common/ModuleSummary";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import SearchableSelect from "@/components/form/SearchableSelect";
import Badge, { type BadgeVariant } from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card, { CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import { FORM_UI } from "@/config/formUi";
import { listLocations } from "@/modules/admin/organization/api";
import { todayLocal } from "@/utils/dateConstraints";
import { createVoucher, listEligibleInvoices, listVouchers } from "../api";

const money = (value: unknown) =>
  Number(value || 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const statusVariant = (status: string): BadgeVariant => {
  if (status === "APPROVED" || status === "PAID") return "success";
  if (status === "PENDING_APPROVAL") return "warning";
  if (status === "REJECTED" || status === "VOID") return "danger";
  return "default";
};

const locationLabel = (location: any) => `${location.code} — ${location.name}`;

export default function PaymentVoucherListPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [locationId, setLocationId] = useState<number | undefined>(undefined);
  const [voucherDate, setVoucherDate] = useState(todayLocal());
  const [selected, setSelected] = useState<Record<number, boolean>>({});
  const [page, setPage] = useState(1);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [appliedFromDate, setAppliedFromDate] = useState("");
  const [appliedToDate, setAppliedToDate] = useState("");
  const [filterLocationId, setFilterLocationId] = useState<number | undefined>(undefined);
  const [status, setStatus] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const invalidPeriod = !!appliedFromDate && !!appliedToDate && appliedFromDate > appliedToDate;

  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(searchInput.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => setPage(1), [appliedFromDate, appliedToDate, filterLocationId, status, search]);

  const vouchers = useQuery({
    queryKey: ["payment-vouchers", page, appliedFromDate, appliedToDate, filterLocationId, status, search],
    enabled: !invalidPeriod,
    queryFn: async () =>
      (await listVouchers({
        page,
        page_size: 20,
        date_from: appliedFromDate || undefined,
        date_to: appliedToDate || undefined,
        location_id: filterLocationId || undefined,
        status: status || undefined,
        search: search || undefined,
      })).data,
  });
  const locations = useQuery({ queryKey: ["pv-locations"], queryFn: () => listLocations({ is_active: true }) });
  const eligible = useQuery({
    queryKey: ["pv-eligible", locationId],
    queryFn: async () => (await listEligibleInvoices(locationId!)).data,
    enabled: !!locationId,
  });

  const applyDates = () => {
    if (fromDate && toDate && fromDate > toDate) {
      toast.error("Voucher date From must be on or before To");
      return;
    }
    setPage(1);
    setAppliedFromDate(fromDate);
    setAppliedToDate(toDate);
  };

  const clearDates = () => {
    setPage(1);
    setFromDate("");
    setToDate("");
    setAppliedFromDate("");
    setAppliedToDate("");
  };

  const create = useMutation({
    mutationFn: async () => {
      const ids = Object.entries(selected).filter(([, value]) => value).map(([key]) => Number(key));
      if (!locationId) throw new Error("Select a location");
      if (!ids.length) throw new Error("Select at least one invoice");
      if (!voucherDate) throw new Error("Voucher Date is required");
      const rows = (eligible.data ?? []).filter((row: any) => ids.includes(row.id));
      const allocations = rows.map((row: any) => ({
        supplier_invoice_id: row.id,
        allocated_amount: Number(row.available_balance),
      }));
      return (await createVoucher({ location_id: locationId, voucher_date: voucherDate, allocations })).data;
    },
    onSuccess: (data: any) => {
      toast.success(`Voucher ${data.voucher_number} created`);
      setSelected({});
      qc.invalidateQueries({ queryKey: ["payment-vouchers"] });
      navigate(`/finance/payment-vouchers/${data.id}`);
    },
    onError: (error: any) => toast.error(error.response?.data?.detail || String(error)),
  });

  const items: any[] = vouchers.data?.items ?? [];
  const eligibleRows: any[] = eligible.data ?? [];
  const selectedRows = eligibleRows.filter((row: any) => selected[row.id]);
  const selectedTotal = selectedRows.reduce((sum, row: any) => sum + Number(row.available_balance || 0), 0);
  const pendingCount = items.filter((row: any) => row.status === "PENDING_APPROVAL").length;

  const metrics: SummaryMetric[] = [
    { label: "Vouchers", value: vouchers.data?.total_items ?? 0 },
    { label: "Pending approval", value: pendingCount, note: "On the current page" },
    { label: "Invoices selected", value: selectedRows.length },
    { label: "Selected amount", value: money(selectedTotal) },
  ];

  const locationOptions = (locations.data ?? []).map((location: any) => ({
    id: location.id,
    label: locationLabel(location),
    keywords: [location.code, location.name],
  }));

  const statusSelect = (
    <select
      aria-label="Voucher status"
      className="h-9 rounded-md border border-slate-300 bg-white px-3 text-sm"
      value={status}
      onChange={(event) => setStatus(event.target.value)}
    >
      <option value="">All statuses</option>
      {["DRAFT", "PENDING_APPROVAL", "APPROVED", "REJECTED", "VOID", "PAID"].map((value) => (
        <option key={value} value={value}>{value.replaceAll("_", " ")}</option>
      ))}
    </select>
  );

  return (
    <DataWorkspace area="Accounting" className="data-first">
      <div className="space-y-2">
        <APWorkspaceHeader />
        <PageHeader
          title="Payment Vouchers"
          description="Per-location payment request — select invoices, get approval, then create and post a payment from the Payments screen."
          actions={
            <Button variant="outline" onClick={() => window.print()}>
              <Printer size={15} /> Print
            </Button>
          }
        >
          <div className="mt-0.5 text-[11px] text-slate-500">Vouchers are approval documents only; they do not post to the GL.</div>
        </PageHeader>
        <ModuleSummary metrics={metrics} />

        <Card className="overflow-hidden p-0">
          <CardHeader>
            <div>
              <CardTitle className="text-sm">Create Voucher</CardTitle>
              <CardDescription>Choose the location, voucher date, and payable invoices. Full available balances are allocated.</CardDescription>
            </div>
          </CardHeader>
          <div className="p-3">
            <div className="grid gap-3 md:grid-cols-3">
              <SearchableSelect
                label="Location (locked per voucher)"
                value={locationId}
                placeholder="Type location code or name..."
                options={locationOptions}
                onChange={(value) => {
                  setLocationId(value);
                  setSelected({});
                }}
              />
              <label className="text-xs font-medium text-slate-700">
                Voucher date
                <input
                  type="date"
                  data-accounting-date="true"
                  className={`${FORM_UI.controlBase} ${FORM_UI.density.compact.control} mt-1`}
                  value={voucherDate}
                  onChange={(event) => setVoucherDate(event.target.value)}
                />
              </label>
              <div className="flex items-end">
                <Button
                  className="w-full"
                  loading={create.isPending}
                  disabled={!locationId || !voucherDate || !Object.values(selected).some(Boolean)}
                  onClick={() => create.mutate()}
                >
                  Create Voucher
                </Button>
              </div>
            </div>

            {locationId && (
              <div className="mt-4 overflow-x-auto rounded border">
                <Table className="min-w-[900px]" containerClassName="rounded-none border-0 shadow-none">
                  <THead>
                    <TR>
                      <TH aria-label="Select invoice" />
                      <TH>Invoice</TH>
                      <TH>Supplier</TH>
                      <TH>Due</TH>
                      <TH numeric>Available</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {eligible.isPending && (
                      <TR><TD colSpan={5} className="p-6 text-center text-slate-500">Loading invoices...</TD></TR>
                    )}
                    {eligible.isError && (
                      <TR><TD colSpan={5} className="p-6 text-center text-red-700">Payable invoices could not be loaded.</TD></TR>
                    )}
                    {!eligible.isPending && !eligible.isError && eligibleRows.length === 0 && (
                      <TR><TD colSpan={5} className="p-6 text-center text-slate-500">No payable invoices for this location.</TD></TR>
                    )}
                    {eligibleRows.map((row: any) => (
                      <TR key={row.id}>
                        <TD>
                          <input
                            type="checkbox"
                            aria-label={`Select ${row.invoice_number}`}
                            checked={!!selected[row.id]}
                            onChange={(event) => setSelected({ ...selected, [row.id]: event.target.checked })}
                          />
                        </TD>
                        <TD>
                          <TableCellStack primary={row.invoice_number} secondary={row.supplier_invoice_number} />
                        </TD>
                        <TD>{row.supplier_name}</TD>
                        <TD>{row.due_date || "—"}</TD>
                        <TD numeric className="tabular-nums">{money(row.available_balance)}</TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              </div>
            )}
          </div>
        </Card>

        <Card className="overflow-hidden p-0">
          <div className="p-3 print:hidden">
            <ListToolbar
              search={searchInput}
              searchPlaceholder="Search voucher number..."
              onSearch={setSearchInput}
              filters={
                <>
                  <div className="w-52">
                    <SearchableSelect
                      label="Filter location"
                      value={filterLocationId}
                      placeholder="All locations"
                      options={locationOptions}
                      onChange={setFilterLocationId}
                    />
                  </div>
                  {statusSelect}
                </>
              }
              advancedOpen={advancedOpen}
              onAdvancedToggle={() => setAdvancedOpen((value) => !value)}
              advancedFilters={
                <DateRangeFilter
                  from={fromDate}
                  to={toDate}
                  onFromChange={setFromDate}
                  onToChange={setToDate}
                  onApply={applyDates}
                  onClear={clearDates}
                  fromLabel="Voucher Date From"
                  toLabel="Voucher Date To"
                />
              }
              onRefresh={() => vouchers.refetch()}
              footer={
                <div className="text-xs text-slate-500">
                  {vouchers.data?.total_items ?? 0} vouchers match current filters
                </div>
              }
            />
          </div>

          {invalidPeriod ? (
            <div className="m-3 rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
              Set a valid voucher date range to load vouchers.
            </div>
          ) : vouchers.isPending ? (
            <div className="p-10 text-center text-sm text-slate-500">Loading payment vouchers…</div>
          ) : vouchers.isError ? (
            <div role="alert" className="m-3 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <div className="font-semibold">Payment vouchers could not be loaded.</div>
              <Button className="mt-3" size="sm" variant="outline" onClick={() => vouchers.refetch()}>Try again</Button>
            </div>
          ) : (
            <>
              <CardHeader>
                <div>
                  <CardTitle className="text-sm">Voucher Register</CardTitle>
                  <CardDescription>Draft → pending approval → approved; create the payment separately.</CardDescription>
                </div>
              </CardHeader>
              <Table className="min-w-[900px]" containerClassName="rounded-none border-x-0 border-b-0 shadow-none">
                <THead>
                  <TR><TH>Voucher</TH><TH>Location</TH><TH>Period</TH><TH numeric>Total</TH><TH>Status</TH><TH numeric>Actions</TH></TR>
                </THead>
                <TBody>
                  {items.map((voucher: any) => (
                    <TR key={voucher.id}>
                      <TD>
                        <TableCellStack
                          primary={
                            <Link className="font-medium text-emerald-700 hover:underline" to={`/finance/payment-vouchers/${voucher.id}`}>
                              {voucher.voucher_number}
                            </Link>
                          }
                          secondary={voucher.voucher_date}
                        />
                      </TD>
                      <TD>{voucher.location_name}</TD>
                      <TD>{voucher.period_from || "—"} → {voucher.period_to || "—"}</TD>
                      <TD numeric className="font-semibold tabular-nums">{money(voucher.total_amount)}</TD>
                      <TD><Badge variant={statusVariant(voucher.status)}>{voucher.status.replaceAll("_", " ")}</Badge></TD>
                      <TD>
                        <div className="flex justify-end">
                          <Link
                            className="inline-flex h-7 items-center rounded border border-slate-200 px-2 text-xs text-slate-700 hover:bg-slate-50"
                            to={`/finance/payment-vouchers/${voucher.id}`}
                          >
                            Open
                          </Link>
                        </div>
                      </TD>
                    </TR>
                  ))}
                  {!items.length && (
                    <TR><TD colSpan={6} className="p-10 text-center text-slate-500">No vouchers match these filters.</TD></TR>
                  )}
                </TBody>
              </Table>
              <div className="px-3 pb-2">
                <Pagination
                  page={page}
                  pages={vouchers.data?.total_pages ?? 1}
                  total={vouchers.data?.total_items ?? 0}
                  pageSize={20}
                  noun="vouchers"
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

import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Ban, Eye, Pencil, Printer, PlayCircle } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import DataWorkspace, { WorkspaceFilters } from "@/components/workspace/DataWorkspace";
import Card from "@/components/ui/Card";
import Empty from "@/components/ui/Empty";
import Loading from "@/components/ui/Loading";
import Badge, { type BadgeVariant } from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Pagination from "@/components/datatable/Pagination";
import Dialog, { DialogContent, DialogHeader, DialogTitle, DialogBody, DialogFooter } from "@/components/ui/Dialog";
import SearchableSelect from "@/components/form/SearchableSelect";
import { FORM_UI } from "@/config/formUi";
import PosCustomerField from "../components/PosCustomerField";
import useAuthStore from "@/store/auth";
import { canAccess } from "@/lib/access";
import { posErrorMessage } from "../errors";
import {
  usePosBillingOptions,
  usePosOptions,
  usePosRevenueAccounts,
  usePosSaleDetail,
  usePosSales,
} from "../hooks/usePosData";
import {
  posApi,
  type PosPaymentMethod,
  type PosStatusFilter,
  type PosVoidPayload,
} from "../api";
import type { PosDraftLine, PosSaleItem, PosStatus } from "../types";

const POS_ROLES = ["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"];
const money = (value: unknown) => "Rp " + Number(value ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (value: unknown) => Number(value ?? 0).toLocaleString("id-ID");
const input = `${FORM_UI.controlBase} ${FORM_UI.density.standard.control}`;

const statusVariant: Record<PosStatus, BadgeVariant> = {
  DRAFT: "warning",
  POSTED: "success",
  VOID: "outline",
};
const statusChoices: { id: PosStatusFilter; name: string }[] = [
  { id: "ALL", name: "All statuses" },
  { id: "DRAFT", name: "Draft" },
  { id: "POSTED", name: "Posted" },
  { id: "VOID", name: "Void" },
];
const paymentChoices: { id: PosPaymentMethod; name: string }[] = [
  { id: "CASH", name: "Cash" },
  { id: "CARD", name: "Card" },
  { id: "BANK_TRANSFER", name: "Bank Transfer" },
];
const paymentLabel: Record<PosPaymentMethod, string> = { CASH: "Cash", CARD: "Card", BANK_TRANSFER: "Bank Transfer" };

function fmtDate(value: unknown): string {
  if (!value) return "-";
  const date = new Date(String(value));
  if (isNaN(date.getTime())) return String(value);
  if (String(value).length === 10) return date.toLocaleDateString("id-ID");
  return date.toLocaleDateString("id-ID") + ", " + date.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
}

function draftLinesFrom(items: PosSaleItem[] = []): PosDraftLine[] {
  return items.map((item) => ({
    product_id: item.product_id,
    quantity: Number(item.quantity),
    unit_price: Number(item.unit_price),
    description: item.description ?? undefined,
    uom: item.uom ?? undefined,
    registration_number: item.registration_number ?? undefined,
    service_period_from: item.service_period_from ?? undefined,
    service_period_to: item.service_period_to ?? undefined,
  }));
}

export default function PosSalesPage() {
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const canManage = useAuthStore((state) => state.hasPermission("finance.manage"));
  const canSell = canAccess(user, POS_ROLES, "pos.sell");

  const [status, setStatus] = useState<PosStatusFilter>("ALL");
  const [locationFilter, setLocationFilter] = useState("");
  const [outletFilter, setOutletFilter] = useState("");
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const listQuery = usePosSales({
    status: status === "ALL" ? undefined : status,
    location_id: locationFilter ? Number(locationFilter) : undefined,
    department_id: outletFilter ? Number(outletFilter) : undefined,
    search: search.trim() || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });
  const rows = listQuery.items;
  const summary = listQuery.data?.summary;
  const statusCounts = summary?.status_counts ?? {};

  const optionsQuery = usePosOptions(user?.id);
  const locations = optionsQuery.data?.locations ?? [];
  const outletChoices = (optionsQuery.data?.departments ?? [])
    .filter((department) => (!locationFilter || String(department.location_id) === locationFilter)
      && (department.is_outlet || !locations.find((location) => location.id === department.location_id)?.has_outlets))
    .filter((department, index, all) => all.findIndex((row) => row.id === department.id) === index);

  const [detailId, setDetailId] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [draftLines, setDraftLines] = useState<PosDraftLine[]>([]);
  const [formError, setFormError] = useState("");

  const detailQuery = usePosSaleDetail(detailId);
  const detail = detailQuery.data;
  useEffect(() => setDraftLines(draftLinesFrom(detail?.items)), [detail]);

  const [postRevenue, setPostRevenue] = useState<number | undefined>();
  const [postMethod, setPostMethod] = useState<PosPaymentMethod>("CASH");
  const [cashReceived, setCashReceived] = useState("");
  useEffect(() => { setPostRevenue(undefined); setCashReceived(""); setPostMethod("CASH"); setFormError(""); }, [detailId]);

  const revenueQuery = usePosRevenueAccounts(
    user?.id,
    detail?.location_id ?? undefined,
    Boolean(detail && detail.status === "DRAFT" && canSell),
  );
  const [invoiceCustomer, setInvoiceCustomer] = useState<number | undefined>();
  const [invoiceDue, setInvoiceDue] = useState("");
  const [invoiceAccount, setInvoiceAccount] = useState<number | undefined>();
  const [correctionDate, setCorrectionDate] = useState(new Date().toLocaleDateString("en-CA"));
  const [confirmUnpaid, setConfirmUnpaid] = useState(false);
  useEffect(() => { setInvoiceCustomer(undefined); setInvoiceDue(""); setInvoiceAccount(undefined); setConfirmUnpaid(false); }, [detailId]);

  const billingQuery = usePosBillingOptions(user?.id, detail?.transaction_type === "INVOICE");
  const chosenCustomer = invoiceCustomer ?? detail?.customer_id ?? undefined;
  const chosenDue = invoiceDue || detail?.invoice_due_date || "";
  const chosenAR = invoiceAccount ?? detail?.receivable_account_id ?? billingQuery.data?.default_receivable_account_id ?? undefined;
  const isInvoice = detail?.transaction_type === "INVOICE";
  const legacyInvoice = Boolean(isInvoice && detail?.status === "POSTED" && !detail?.account_receivable_id);
  const chosenRevenue = postRevenue ?? detail?.revenue_account_id ?? undefined;

  const invalidateSale = () => {
    void queryClient.invalidateQueries({ queryKey: ["pos-sales"] });
    void queryClient.invalidateQueries({ queryKey: ["pos-sale-detail", detailId] });
  };
  const postMutation = useMutation({
    mutationFn: async (id: number) => (await posApi.post(id, {
      revenue_account_id: chosenRevenue,
      customer_id: chosenCustomer,
      invoice_due_date: chosenDue || undefined,
      receivable_account_id: chosenAR,
      payment_method: postMethod,
      payment_received: postMethod === "CASH" ? Number(cashReceived) : undefined,
    })).data,
    onSuccess: invalidateSale,
    onError: (error: unknown) => setFormError(posErrorMessage(error, "Post failed")),
  });

  const voidMutation = useMutation({
    mutationFn: async ({ id, reason }: { id: number; reason?: string }) => (await posApi.void(id, { reason } satisfies PosVoidPayload)).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["pos-sales"] }),
    onError: (error: unknown) => setFormError(posErrorMessage(error, "Void failed")),
  });

  const correction = useMutation({
    mutationFn: async () => {
      if (!detail) throw new Error("Select a sale first");
      return (await posApi.correctToAR(detail.id, {
        customer_id: chosenCustomer!,
        invoice_due_date: chosenDue,
        receivable_account_id: chosenAR,
        correction_date: correctionDate,
        confirm_unpaid: true,
      })).data;
    },
    onSuccess: () => {
      setFormError("");
      invalidateSale();
      void queryClient.invalidateQueries({ queryKey: ["ar-reporting"] });
    },
    onError: (error: unknown) => setFormError(posErrorMessage(error, "AR correction failed")),
  });

  const saveEdit = useMutation({
    mutationFn: async () => {
      if (!detail) throw new Error("Select a sale first");
      return (await posApi.update(detail.id, {
        revenue_account_id: chosenRevenue,
        customer_id: isInvoice ? chosenCustomer : undefined,
        invoice_due_date: isInvoice ? chosenDue : undefined,
        receivable_account_id: isInvoice ? chosenAR : undefined,
        items: draftLines,
      })).data;
    },
    onSuccess: () => {
      setEditing(false);
      setFormError("");
      invalidateSale();
    },
    onError: (error: unknown) => setFormError(posErrorMessage(error, "Could not update draft")),
  });

  const confirmVoid = (id: number) => {
    const reason = window.prompt("Void reason (optional)");
    if (reason === null) return;
    setFormError("");
    voidMutation.mutate({ id, reason: reason.trim() || undefined });
  };

  return (
    <DataWorkspace area="Reports">
      <div className="space-y-6">
        <PageHeader
          title="Point of Sales"
          description="History of register sales. SELL sales are reflected in the general ledger; draft sales can still be edited."
          actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>}
        />

        <ModuleSummary metrics={[
          { label: "Sales", value: num(listQuery.data?.total_items ?? 0) },
          { label: "Draft", value: num(statusCounts.DRAFT ?? 0) },
          { label: "Posted", value: num(statusCounts.POSTED ?? 0) },
          { label: "Posted Value (BP)", value: money(summary?.posted_value) },
        ]} />

        <WorkspaceFilters label="Sales filters" context={`${rows.length} of ${listQuery.data?.total_items ?? 0} sales`}>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[1fr_160px_180px_180px_150px_150px_120px]">
            <input
              aria-label="Search sales"
              className={input}
              placeholder="Search number, item or cashier"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <SearchableSelect<PosStatusFilter> label="Status" value={status} options={statusChoices} onChange={(value) => setStatus(value ?? "ALL")} />
            <SearchableSelect<number>
              label="Sales location"
              value={locationFilter ? Number(locationFilter) : undefined}
              options={locations.map((location) => ({ id: location.id, name: location.name }))}
              onChange={(value) => { setLocationFilter(value ? String(value) : ""); setOutletFilter(""); }}
            />
            <SearchableSelect<number>
              label="Outlet"
              value={outletFilter ? Number(outletFilter) : undefined}
              options={outletChoices.map((department) => ({ id: department.id, name: department.display_name ?? department.name }))}
              onChange={(value) => setOutletFilter(value ? String(value) : "")}
            />
            <input aria-label="From date" type="date" className={input} value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
            <input aria-label="To date" type="date" className={input} value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
            <Link className="inline-flex h-10 items-center justify-center rounded-md border border-emerald-700 bg-emerald-700 px-3 text-sm font-medium text-white" to="/pos">
              <span className="mr-1 text-lg leading-none">+</span>New Sale
            </Link>
          </div>
        </WorkspaceFilters>

        <Card className="p-0">
          {listQuery.isLoading ? (
            <Loading message="Loading sales…" />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[980px] text-left text-sm">
                  <thead>
                    <tr className="whitespace-nowrap border-b text-xs uppercase tracking-wide text-slate-500">
                      <th className="px-4 py-3">Number</th><th className="px-4 py-3">Date</th><th className="px-4 py-3">Sales location</th><th className="px-4 py-3">Outlet</th><th className="px-4 py-3">Cashier</th>
                      <th className="px-4 py-3">Payment</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Total</th><th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.length === 0 && (
                      <tr><td colSpan={9} className="px-4 py-10">
                        <Empty title="No sales match the current filters" description="Adjust the filters or create a new sale." />
                      </td></tr>
                    )}
                    {rows.map((row) => (
                      <tr key={row.id} className="border-t">
                        <td className="px-4 py-3 font-medium text-emerald-700">{row.transaction_number}</td>
                        <td className="whitespace-nowrap px-4 py-3">{fmtDate(row.sale_date)}</td>
                        <td className="px-4 py-3">{row.location_name || row.warehouse_name || "—"}</td>
                        <td className="px-4 py-3">{optionsQuery.data?.departments.find((department) => department.id === row.department_id)?.display_name ?? "—"}</td>
                        <td className="px-4 py-3">{row.created_by_name || "-"}</td>
                        <td className="px-4 py-3">{row.account_receivable_id ? `AR · ${row.payment_status}` : (row.payment_method ? paymentLabel[row.payment_method as PosPaymentMethod] ?? "-" : "-")}</td>
                        <td className="px-4 py-3"><Badge variant={statusVariant[row.status]}>{row.status}</Badge></td>
                        <td className="px-4 py-3 text-right font-semibold">{money(row.total_amount)}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-1">
                            <Button variant="ghost" size="xs" onClick={() => { setEditing(false); setDetailId(row.id); }}><Eye className="h-4 w-4" /></Button>
                            {canSell && row.status === "DRAFT" && (row.cashier_session_id || row.transaction_type === "INVOICE") && <Link className="text-sm text-emerald-700 underline" to={`/pos?order=${row.id}`}>{row.transaction_type === "INVOICE" ? "Continue invoice" : "Continue / settle"}</Link>}
                            {canSell && row.status === "DRAFT" && !row.cashier_session_id && <Button variant="outline" size="xs" onClick={() => { setEditing(true); setDetailId(row.id); }}><Pencil className="h-4 w-4" />Edit</Button>}
                            {canManage && row.status === "POSTED" && row.transaction_type === "INVOICE" && !row.account_receivable_id && <Button variant="outline" size="xs" onClick={() => { setEditing(false); setDetailId(row.id); }}>Repair AR</Button>}
                            {row.status === "POSTED" && <Button variant="ghost" size="xs" onClick={() => window.open(`/pos/sales/${row.id}/print`, "_blank")}><Printer className="h-4 w-4" /></Button>}
                            {canSell && row.status === "DRAFT" && (
                              <>
                                <Button variant="success" size="xs" disabled={postMutation.isPending} onClick={() => setDetailId(row.id)}><PlayCircle className="h-4 w-4" />Post</Button>
                                <Button variant="ghost" size="xs" disabled={voidMutation.isPending} onClick={() => confirmVoid(row.id)}><Ban className="h-4 w-4" />Void</Button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="p-4">
                <Pagination page={listQuery.page} pages={listQuery.pages} total={listQuery.data?.total_items ?? 0} noun="sales" onChange={listQuery.setPage} />
              </div>
            </>
          )}
        </Card>

        <Dialog open={detailId !== null} onOpenChange={(open: boolean) => { if (!open) { setDetailId(null); setEditing(false); } }}>
          <DialogContent>
            <DialogHeader><DialogTitle className="flex items-center gap-2"><Eye className="h-5 w-5 text-[#0F6758]" />{detail?.transaction_number ?? "POS Sale"}</DialogTitle></DialogHeader>
            <DialogBody className={FORM_UI.dialog.body}>
              {detailQuery.isLoading || !detail ? (
                <Loading message="Loading sale…" />
              ) : (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div><div className="text-xs uppercase tracking-wide text-slate-500">Status</div><Badge variant={statusVariant[detail.status]}>{detail.status}</Badge></div>
                    <div><div className="text-xs uppercase tracking-wide text-slate-500">Date</div>{fmtDate(detail.sale_date)}</div>
                    <div><div className="text-xs uppercase tracking-wide text-slate-500">Sales location</div>{detail.location_name || detail.warehouse_name || "—"}</div>
                    {detail.department_name && <div><div className="text-xs uppercase tracking-wide text-slate-500">Department / outlet</div>{detail.department_name}</div>}
                    {detail.guest_count != null && <div><div className="text-xs uppercase tracking-wide text-slate-500">Guests</div>{detail.guest_count}</div>}
                    {detail.cashier_session_id && <div><div className="text-xs uppercase tracking-wide text-slate-500">Table / event · Shift #{detail.cashier_session_id}</div>{detail.table_number || detail.event_name || "Counter"}</div>}
                    <div><div className="text-xs uppercase tracking-wide text-slate-500">Payment</div>{detail.account_receivable_id ? `AR · ${detail.payment_status}` : (detail.payment_method ? paymentLabel[detail.payment_method as PosPaymentMethod] ?? "-" : "-")}{detail.payment_method === "CASH" && Number(detail.change_amount) > 0 ? ` (change ${money(detail.change_amount)})` : ""}</div>
                    <div><div className="text-xs uppercase tracking-wide text-slate-500">Cashier</div>{detail.created_by_name || "-"}</div>
                    <div><div className="text-xs uppercase tracking-wide text-slate-500">Journal</div>{detail.journal_number || "-"}</div>
                    {detail.customer_name && <div className="col-span-2"><div className="text-xs uppercase tracking-wide text-slate-500">Customer</div>{detail.customer_code} - {detail.customer_name}</div>}
                    {detail.notes && <div className="col-span-2"><div className="text-xs uppercase tracking-wide text-slate-500">Notes</div>{detail.notes}</div>}
                    {detail.status === "VOID" && detail.void_reason && <div className="col-span-2"><div className="text-xs uppercase tracking-wide text-slate-500">Void Reason</div>{detail.void_reason}</div>}
                    {detail.posted_by_name && <div className="col-span-2"><div className="text-xs uppercase tracking-wide text-slate-500">Posted By</div>{detail.posted_by_name} · {fmtDate(detail.posted_at)}</div>}
                  </div>
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b text-xs uppercase tracking-wide text-slate-500">
                        <th className="px-2 py-2">Product</th><th className="px-2 py-2 text-right">Qty</th><th className="px-2 py-2 text-right">Price</th><th className="px-2 py-2 text-right">Tax</th><th className="px-2 py-2 text-right">Amount</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.items.map((item: PosSaleItem, index: number) => (
                        <tr key={item.id ?? `${item.product_id}:${index}`} className="border-t">
                          <td className="px-2 py-2"><span className="font-medium">{item.product_name}</span> <span className="text-slate-400">({item.product_code})</span></td>
                          <td className="px-2 py-2 text-right tabular-nums">
                            {editing ? <input aria-label={`Quantity for ${item.product_name}`} type="number" min="0.0001" step="0.0001" className="w-20 rounded border px-2 py-1 text-right" value={draftLines[index]?.quantity ?? Number(item.quantity)} onChange={(event) => setDraftLines((lines) => lines.map((line, i) => i === index ? { ...line, quantity: Number(event.target.value) } : line))} /> : num(item.quantity)} {item.uom}
                          </td>
                          <td className="px-2 py-2 text-right tabular-nums">
                            {editing ? <input aria-label={`Unit price for ${item.product_name}`} type="number" min="0.01" step="0.01" className="w-28 rounded border px-2 py-1 text-right" value={draftLines[index]?.unit_price ?? Number(item.unit_price)} onChange={(event) => setDraftLines((lines) => lines.map((line, i) => i === index ? { ...line, unit_price: Number(event.target.value) } : line))} /> : money(item.unit_price)}
                          </td>
                          <td className="px-2 py-2 text-right tabular-nums">{item.tax_type === "PBJT" ? "PBJT " : ""}{money(item.tax_amount)}</td>
                          <td className="px-2 py-2 text-right tabular-nums">{money(item.line_amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="border-t text-slate-600"><td className="px-2 py-2" colSpan={4}>Subtotal</td><td className="px-2 py-2 text-right tabular-nums">{money(detail.subtotal)}</td></tr>
                      {Number(detail.discount_amount) > 0 && <tr className="text-slate-600"><td className="px-2 py-2" colSpan={4}>Discount</td><td className="px-2 py-2 text-right tabular-nums">-{money(detail.discount_amount)}</td></tr>}
                      <tr className="text-slate-600"><td className="px-2 py-2" colSpan={4}>Service charge</td><td className="px-2 py-2 text-right tabular-nums">{money(detail.service_charge_amount)}</td></tr>
                      <tr className="text-slate-600"><td className="px-2 py-2" colSpan={4}>Tax</td><td className="px-2 py-2 text-right tabular-nums">{money(detail.tax_amount)}</td></tr>
                      <tr className="font-bold"><td className="px-2 py-2" colSpan={4}>Total</td><td className="px-2 py-2 text-right tabular-nums">{money(detail.total_amount)}</td></tr>
                      {Number(detail.payment_received) > 0 && <tr className="text-slate-600"><td className="px-2 py-2" colSpan={4}>Received</td><td className="px-2 py-2 text-right tabular-nums">{money(detail.payment_received)}</td></tr>}
                    </tfoot>
                  </table>
                  {canSell && detail.status === "DRAFT" && (
                    <div className="grid gap-3 sm:grid-cols-2">
                      <SearchableSelect<number> label="Revenue account" required value={chosenRevenue} options={revenueQuery.data ?? []} placeholder="Choose revenue account" onChange={setPostRevenue} inlineDropdown />
                      {!isInvoice && (
                        <>
                          <SearchableSelect<PosPaymentMethod> label="Payment method" value={postMethod} options={paymentChoices} onChange={(value) => setPostMethod(value ?? "CASH")} inlineDropdown />
                          <div>
                            <span className={FORM_UI.label}>Cash received</span>
                            <input className={`${input} mt-1`} type="number" min={0} value={cashReceived} onChange={(event) => setCashReceived(event.target.value)} />
                          </div>
                        </>
                      )}
                    </div>
                  )}
                  {isInvoice && ((detail.status === "DRAFT" && canSell) || (legacyInvoice && canManage)) && (
                    <div className="grid gap-3 sm:grid-cols-2">
                      <PosCustomerField value={chosenCustomer} onChange={setInvoiceCustomer} customers={billingQuery.data?.customers ?? []} canCreate={canSell} />
                      <div>
                        <span className={FORM_UI.label}>Invoice due date</span>
                        <input className={`${input} mt-1`} type="date" value={chosenDue} onChange={(event) => setInvoiceDue(event.target.value)} />
                      </div>
                      <SearchableSelect<number> label="Receivable account" value={chosenAR} options={billingQuery.data?.receivable_accounts ?? []} onChange={setInvoiceAccount} inlineDropdown />
                      {legacyInvoice && (
                        <>
                          <div>
                            <span className={FORM_UI.label}>Correction posting date</span>
                            <input className={`${input} mt-1`} type="date" value={correctionDate} onChange={(event) => setCorrectionDate(event.target.value)} />
                          </div>
                          <label className="col-span-full text-sm"><input type="checkbox" checked={confirmUnpaid} onChange={(event) => setConfirmUnpaid(event.target.checked)} /> This invoice has not been paid. Correct its bank posting to receivables.</label>
                        </>
                      )}
                    </div>
                  )}
                  {(postMutation.isError || voidMutation.isError || correction.isError || saveEdit.isError) && formError && (
                    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{formError}</div>
                  )}
                </div>
              )}
            </DialogBody>
            <DialogFooter className={FORM_UI.dialog.footer}>
              {canSell && detail?.status === "DRAFT" && detail.cashier_session_id && <Link className="rounded border px-3 py-2 text-sm text-emerald-700" to={`/pos?order=${detail.id}`}>Continue / settle</Link>}
              {canSell && detail?.status === "DRAFT" && !detail.cashier_session_id && (editing ? (
                <>
                  <Button variant="outline" onClick={() => { setEditing(false); setDraftLines(draftLinesFrom(detail?.items)); }}>Cancel edit</Button>
                  <Button loading={saveEdit.isPending} disabled={!draftLines.length || draftLines.some((line) => line.quantity <= 0 || line.unit_price <= 0) || (isInvoice && (!chosenCustomer || !chosenDue))} onClick={() => saveEdit.mutate()}>Save Changes</Button>
                </>
              ) : <Button variant="outline" onClick={() => setEditing(true)}><Pencil className="h-4 w-4" />Edit Draft</Button>)}
              {canSell && detail ? (
                <>
                  {detail.status === "DRAFT" && !detail.cashier_session_id && !editing && <Button variant="success" onClick={() => postMutation.mutate(detail.id)} disabled={postMutation.isPending || !chosenRevenue || (isInvoice ? (!chosenCustomer || !chosenDue) : (postMethod === "CASH" && Number(cashReceived) < Number(detail.total_amount)))}><PlayCircle className="h-4 w-4" />Post</Button>}
                  {detail.status === "DRAFT" && !editing && <Button variant="outline" onClick={() => confirmVoid(detail.id)} disabled={voidMutation.isPending}><Ban className="h-4 w-4" />Void</Button>}
                </>
              ) : null}
              {legacyInvoice && canManage && <Button variant="primary" disabled={!confirmUnpaid || !chosenCustomer || !chosenDue || !correctionDate || correction.isPending} onClick={() => correction.mutate()}>Correct unpaid invoice to AR</Button>}
              {detail?.account_receivable_id && <Link className="rounded border px-3 py-2 text-sm text-emerald-700" to={`/accounts-receivable/invoices/${detail.account_receivable_id}`}>Open AR Invoice</Link>}
              {detail?.status === "POSTED" && <Button variant="outline" onClick={() => window.open(`/pos/sales/${detail.id}/print`, "_blank")}><Printer className="h-4 w-4" />Print</Button>}
              <Button variant="outline" onClick={() => setDetailId(null)}>Close</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </DataWorkspace>
  );
}

import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, Eye, Pencil, Printer, PlayCircle } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Pagination from "@/components/datatable/Pagination";
import Dialog from "@/components/ui/Dialog";
import { DialogContent, DialogHeader, DialogTitle, DialogBody, DialogFooter } from "@/components/ui/Dialog";
import SearchableSelect from "@/components/form/SearchableSelect";
import PosCustomerField from "../components/PosCustomerField";
import useAuthStore from "@/store/auth";
import { canAccess } from "@/lib/access";
import { posApi, type PosPaymentMethod, type PosVoidPayload } from "../api";

const POS_ROLES = ["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"];
const money = (v: unknown) => "Rp " + Number(v ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (v: unknown) => Number(v ?? 0).toLocaleString("id-ID");
const input = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";
const PAGE_SIZE = 25;

const statusVariant: Record<string, "default" | "warning" | "success" | "outline"> = {
  DRAFT: "warning",
  POSTED: "success",
  VOID: "outline",
};

const paymentLabel: Record<string, string> = { CASH: "Cash", CARD: "Card", BANK_TRANSFER: "Bank Transfer" };

function fmtDate(value: unknown): string {
  if (!value) return "-";
  const d = new Date(String(value));
  if (isNaN(d.getTime())) return String(value);
  if (String(value).length === 10) return d.toLocaleDateString("id-ID");
  return d.toLocaleDateString("id-ID") + ", " + d.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
}

export default function PosSalesPage() {
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const canManage = useAuthStore(state => state.hasPermission("finance.manage"));
  const canSell = canAccess(user, POS_ROLES, "pos.sell");

  const [status, setStatus] = useState("ALL");
  const [locationFilter, setLocationFilter] = useState("");
  const [outletFilter, setOutletFilter] = useState("");
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);

  const listQuery = useQuery({
    queryKey: ["pos-sales", { status, locationFilter, outletFilter, search, dateFrom, dateTo, page }],
    queryFn: async () => (await posApi.list({
      page,
      page_size: PAGE_SIZE,
      status: status === "ALL" ? undefined : status,
      location_id: locationFilter ? Number(locationFilter) : undefined,
      department_id: outletFilter ? Number(outletFilter) : undefined,
      search: search.trim() || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    })).data,
  });
  const data: any = listQuery.data ?? {};
  const rows: any[] = data.items ?? [];
  const summary = data.summary ?? {};
  const statusCounts: Record<string, number> = summary.status_counts ?? {};
  const pages = Math.max(data.total_pages ?? 0, 1);

  useEffect(() => setPage(1), [status, locationFilter, outletFilter, search, dateFrom, dateTo]);

  const locationsQuery = useQuery({
    queryKey: ["pos-options"],
    queryFn: async () => (await posApi.options()).data,
  });
  const locations: any[] = locationsQuery.data?.locations ?? [];
  const outletChoices: any[] = (locationsQuery.data?.departments ?? []).filter((d: any) => (!locationFilter || String(d.location_id) === locationFilter) && (d.is_outlet || !locations.find((l: any) => l.id === d.location_id)?.has_outlets)).filter((d: any, i: number, all: any[]) => all.findIndex(x => x.id === d.id) === i);

  const [detailId, setDetailId] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [draftLines, setDraftLines] = useState<Array<{ product_id: number; quantity: number; unit_price: number }>>([]);
  const [formError, setFormError] = useState("");

  const detailQuery = useQuery({
    queryKey: ["pos-sale-detail", detailId],
    queryFn: async () => detailId ? (await posApi.detail(detailId)).data : null,
    enabled: detailId !== null,
  });
  const detail: any = detailQuery.data;
  useEffect(() => {
    setDraftLines((detail?.items ?? []).map((item: any) => ({ product_id: item.product_id, quantity: Number(item.quantity), unit_price: Number(item.unit_price) })));
  }, [detail]);

  const [postRevenue, setPostRevenue] = useState<number | undefined>();
  const [postMethod, setPostMethod] = useState<PosPaymentMethod>("CASH");
  const [cashReceived, setCashReceived] = useState("");
  useEffect(() => { setPostRevenue(undefined); setCashReceived(""); setPostMethod("CASH"); setFormError(""); }, [detailId]);
  const revenueQuery = useQuery({ queryKey: ["pos-revenue-accounts", user?.id, detail?.location_id], queryFn: async () => (await posApi.revenueAccounts(detail?.location_id)).data, enabled: Boolean(detail && detail.status === "DRAFT" && canSell) });
  const [invoiceCustomer, setInvoiceCustomer] = useState<number | undefined>();
  const [invoiceDue, setInvoiceDue] = useState("");
  const [invoiceAccount, setInvoiceAccount] = useState<number | undefined>();
  const [correctionDate, setCorrectionDate] = useState(new Date().toLocaleDateString("en-CA"));
  const [confirmUnpaid, setConfirmUnpaid] = useState(false);
  useEffect(() => { setInvoiceCustomer(undefined); setInvoiceDue(""); setInvoiceAccount(undefined); setConfirmUnpaid(false); }, [detailId]);
  const billingQuery = useQuery({ queryKey: ["pos-billing-options", user?.id], queryFn: async () => (await posApi.billingOptions()).data, enabled: detail?.transaction_type === "INVOICE" });
  const chosenCustomer = invoiceCustomer ?? detail?.customer_id;
  const chosenDue = invoiceDue || detail?.invoice_due_date || "";
  const chosenAR = invoiceAccount ?? detail?.receivable_account_id ?? billingQuery.data?.default_receivable_account_id;
  const isInvoice = detail?.transaction_type === "INVOICE";
  const legacyInvoice = isInvoice && detail?.status === "POSTED" && !detail?.account_receivable_id;
  const chosenRevenue = postRevenue ?? detail?.revenue_account_id;
  const postMutation = useMutation({
    mutationFn: async (id: number) => (await posApi.post(id, { revenue_account_id: chosenRevenue, customer_id: chosenCustomer, invoice_due_date: chosenDue || undefined, receivable_account_id: chosenAR, payment_method: postMethod, payment_received: postMethod === "CASH" ? Number(cashReceived) : undefined })).data,
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["pos-sales"] }); void queryClient.invalidateQueries({ queryKey: ["pos-sale-detail", detailId] }); },
    onError: (error: any) => setFormError(typeof error?.response?.data?.detail === "string" ? error.response.data.detail : error?.message || "Post failed"),
  });

  const voidMutation = useMutation({
    mutationFn: async ({ id, reason }: { id: number; reason?: string }) => (await posApi.void(id, { reason } satisfies PosVoidPayload)).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["pos-sales"] }),
    onError: (error: any) => setFormError(typeof error?.response?.data?.detail === "string" ? error.response.data.detail : error?.message || "Void failed"),
  });

  const correction = useMutation({
    mutationFn: async () => posApi.correctToAR(detail.id, { customer_id: chosenCustomer, invoice_due_date: chosenDue, receivable_account_id: chosenAR, correction_date: correctionDate, confirm_unpaid: true }),
    onSuccess: () => { setFormError(""); void queryClient.invalidateQueries({ queryKey: ["pos-sales"] }); void queryClient.invalidateQueries({ queryKey: ["pos-sale-detail", detailId] }); void queryClient.invalidateQueries({ queryKey: ["ar-reporting"] }); },
    onError: (error: any) => setFormError(error?.response?.data?.detail || error?.message || "AR correction failed"),
  });
  const saveEdit = useMutation({
    mutationFn: async () => posApi.update(detail.id, {
      revenue_account_id: chosenRevenue,
      customer_id: isInvoice ? chosenCustomer : undefined,
      invoice_due_date: isInvoice ? chosenDue : undefined,
      receivable_account_id: isInvoice ? chosenAR : undefined,
      items: draftLines,
    }),
    onSuccess: () => {
      setEditing(false); setFormError("");
      void queryClient.invalidateQueries({ queryKey: ["pos-sales"] });
      void queryClient.invalidateQueries({ queryKey: ["pos-sale-detail", detailId] });
    },
    onError: (error: any) => setFormError(error?.response?.data?.detail || "Could not update draft"),
  });
  const confirmVoid = (id: number) => {
    const reason = window.prompt("Void reason (optional)");
    if (reason === null) return;
    setFormError("");
    voidMutation.mutate({ id, reason: reason.trim() || undefined });
  };

  return (
    <div className="space-y-6">
      <PageHeader  actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>} title="Point of Sales" description="History of register sales. SELL sales are reflected in the general ledger; draft sales can still be edited." />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Sales</div><div className="mt-2 text-2xl font-bold">{num(data.total_items ?? 0)}</div></Card>
        <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Draft</div><div className="mt-2 text-2xl font-bold">{num(statusCounts.DRAFT ?? 0)}</div></Card>
        <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Posted</div><div className="mt-2 text-2xl font-bold text-emerald-700">{num(statusCounts.POSTED ?? 0)}</div></Card>
        <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Posted Value (BP)</div><div className="mt-2 text-2xl font-bold text-emerald-700">{money(summary.posted_value)}</div></Card>
      </div>

      <Card className="p-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[1fr_140px_160px_170px_150px_150px_110px]">
          <input className={input} placeholder="Search number, item or cashier" value={search} onChange={(e) => setSearch(e.target.value)} />
          <select className={input} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="ALL">All statuses</option>
            <option value="DRAFT">Draft</option>
            <option value="POSTED">Posted</option>
            <option value="VOID">Void</option>
          </select>
          <select className={input} value={locationFilter} onChange={(e) => {setLocationFilter(e.target.value);setOutletFilter("");}}>
            <option value="">All sales locations</option>
            {locations.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </select>
          <select aria-label="Filter outlet" className={input} value={outletFilter} onChange={(e) => setOutletFilter(e.target.value)}>
            <option value="">All outlets</option>
            {outletChoices.map((d) => <option key={d.id} value={d.id}>{d.display_name ?? d.name}</option>)}
          </select>
          <input type="date" className={input} value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          <input type="date" className={input} value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          <Button variant="primary" onClick={() => window.location.href = "/pos"}><span className="text-lg leading-none mr-1">+</span>New Sale</Button>
        </div>
      </Card>

      <Card className="p-0">
        {listQuery.isLoading ? <Loading /> : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[980px] text-left text-sm">
                <thead><tr className="whitespace-nowrap border-b text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-3">Number</th><th className="px-4 py-3">Date</th><th className="px-4 py-3">Sales location</th><th className="px-4 py-3">Outlet</th><th className="px-4 py-3">Cashier</th>
                  <th className="px-4 py-3">Payment</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Total</th><th className="px-4 py-3 text-right">Actions</th>
                </tr></thead>
                <tbody>
                  {rows.length === 0 && <tr><td colSpan={9} className="px-4 py-10 text-center text-slate-500">No sales match the current filters.</td></tr>}
                  {rows.map((row) => (
                    <tr key={row.id} className="border-t">
                      <td className="px-4 py-3 font-medium text-emerald-700">{row.transaction_number}</td>
                      <td className="px-4 py-3 whitespace-nowrap">{fmtDate(row.sale_date)}</td>
                      <td className="px-4 py-3">{row.location_name || row.warehouse_name || "—"}</td>
                      <td className="px-4 py-3">{(locationsQuery.data?.departments ?? []).find((d: any) => d.id === row.department_id)?.display_name ?? "—"}</td>
                      <td className="px-4 py-3">{row.created_by_name || "-"}</td>
                      <td className="px-4 py-3">{row.account_receivable_id ? `AR · ${row.payment_status}` : paymentLabel[row.payment_method] ?? "-"}</td>
                      <td className="px-4 py-3"><Badge variant={statusVariant[row.status] ?? "default"}>{row.status}</Badge></td>
                      <td className="px-4 py-3 text-right font-semibold">{money(row.total_amount)}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="xs" onClick={() => { setEditing(false); setDetailId(row.id); }}><Eye className="h-4 w-4" /></Button>
                          {canSell && row.status === "DRAFT" && row.cashier_session_id && <Link className="text-sm text-emerald-700 underline" to={`/pos?order=${row.id}`}>Continue / settle</Link>}
                          {canSell && row.status === "DRAFT" && <Button variant="outline" size="xs" onClick={() => { setEditing(true); setDetailId(row.id); }}><Pencil className="h-4 w-4" />Edit</Button>}
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
            <div className="p-4"><Pagination page={page} pages={pages} total={data.total_items ?? 0} pageSize={PAGE_SIZE} noun="sales" onChange={setPage} /></div>
          </>
        )}
      </Card>

      <Dialog open={detailId !== null} onOpenChange={(open: boolean) => { if (!open) { setDetailId(null); setEditing(false); } }}>
        <DialogContent>
          <DialogHeader><DialogTitle className="flex items-center gap-2"><Eye className="h-5 w-5 text-[#0F6758]" />{detail?.transaction_number ?? "POS Sale"}</DialogTitle></DialogHeader>
          <DialogBody>
            {detailQuery.isLoading || !detail ? <Loading /> : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div><div className="text-xs uppercase tracking-wide text-slate-500">Status</div><Badge variant={statusVariant[detail.status] ?? "default"}>{detail.status}</Badge></div>
                  <div><div className="text-xs uppercase tracking-wide text-slate-500">Date</div>{fmtDate(detail.sale_date)}</div>
                  <div><div className="text-xs uppercase tracking-wide text-slate-500">Sales location</div>{detail.location_name || detail.warehouse_name || "—"}</div>
                  {detail.department_name&&<div><div className="text-xs uppercase tracking-wide text-slate-500">Department / outlet</div>{detail.department_name}</div>}
                  {detail.cashier_session_id&&<div><div className="text-xs uppercase tracking-wide text-slate-500">Table / event · Shift #{detail.cashier_session_id}</div>{detail.table_number||detail.event_name||"Counter"}</div>}
                  <div><div className="text-xs uppercase tracking-wide text-slate-500">Payment</div>{detail.account_receivable_id ? `AR · ${detail.payment_status}` : paymentLabel[detail.payment_method] ?? "-"}{detail.payment_method === "CASH" && detail.change_amount > 0 ? ` (change ${money(detail.change_amount)})` : ""}</div>
                  <div><div className="text-xs uppercase tracking-wide text-slate-500">Cashier</div>{detail.created_by_name || "-"}</div>
                  <div><div className="text-xs uppercase tracking-wide text-slate-500">Journal</div>{detail.journal_number || "-"}</div>
                  {detail.customer_name && <div className="col-span-2"><div className="text-xs uppercase tracking-wide text-slate-500">Customer</div>{detail.customer_code} - {detail.customer_name}</div>}
                  {detail.notes && <div className="col-span-2"><div className="text-xs uppercase tracking-wide text-slate-500">Notes</div>{detail.notes}</div>}
                  {detail.status === "VOID" && detail.void_reason && <div className="col-span-2"><div className="text-xs uppercase tracking-wide text-slate-500">Void Reason</div>{detail.void_reason}</div>}
                  {detail.posted_by_name && <div className="col-span-2"><div className="text-xs uppercase tracking-wide text-slate-500">Posted By</div>{detail.posted_by_name ?? detail.void_reason ? `${detail.posted_by_name || "-"} · ${fmtDate(detail.posted_at)}` : detail.posted_by_name}</div>}
                </div>
                <table className="w-full text-left text-sm">
                  <thead><tr className="border-b text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-2 py-2">Product</th><th className="px-2 py-2 text-right">Qty</th><th className="px-2 py-2 text-right">Price</th><th className="px-2 py-2 text-right">Tax</th><th className="px-2 py-2 text-right">Amount</th>
                  </tr></thead>
                  <tbody>
                    {(detail.items ?? []).map((item: any, index: number) => (
                      <tr key={item.id} className="border-t">
                        <td className="px-2 py-2"><span className="font-medium">{item.product_name}</span> <span className="text-slate-400">({item.product_code})</span></td>
                        <td className="px-2 py-2 text-right tabular-nums">{editing ? <input aria-label={`Quantity for ${item.product_name}`} type="number" min="0.0001" step="0.0001" className="w-20 rounded border px-2 py-1 text-right" value={draftLines[index]?.quantity ?? item.quantity} onChange={event => setDraftLines(rows => rows.map((row, i) => i === index ? { ...row, quantity: Number(event.target.value) } : row))}/> : num(item.quantity)} {item.uom}</td>
                        <td className="px-2 py-2 text-right tabular-nums">{editing ? <input aria-label={`Unit price for ${item.product_name}`} type="number" min="0.01" step="0.01" className="w-28 rounded border px-2 py-1 text-right" value={draftLines[index]?.unit_price ?? item.unit_price} onChange={event => setDraftLines(rows => rows.map((row, i) => i === index ? { ...row, unit_price: Number(event.target.value) } : row))}/> : money(item.unit_price)}</td>
                        <td className="px-2 py-2 text-right tabular-nums">{item.tax_type === "PBJT" ? "PBJT " : ""}{money(item.tax_amount)}</td>
                        <td className="px-2 py-2 text-right tabular-nums">{money(item.line_amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t text-slate-600"><td className="px-2 py-2" colSpan={4}>Subtotal</td><td className="px-2 py-2 text-right tabular-nums">{money(detail.subtotal)}</td></tr>
                    {detail.discount_amount > 0 && <tr className="text-slate-600"><td className="px-2 py-2" colSpan={4}>Discount</td><td className="px-2 py-2 text-right tabular-nums">-{money(detail.discount_amount)}</td></tr>}
                    <tr className="text-slate-600"><td className="px-2 py-2" colSpan={4}>Service charge</td><td className="px-2 py-2 text-right tabular-nums">{money(detail.service_charge_amount)}</td></tr><tr className="text-slate-600"><td className="px-2 py-2" colSpan={4}>Tax</td><td className="px-2 py-2 text-right tabular-nums">{money(detail.tax_amount)}</td></tr>
                    <tr className="font-bold"><td className="px-2 py-2" colSpan={4}>Total</td><td className="px-2 py-2 text-right tabular-nums">{money(detail.total_amount)}</td></tr>
                    {detail.payment_received > 0 && <tr className="text-slate-600"><td className="px-2 py-2" colSpan={4}>Received</td><td className="px-2 py-2 text-right tabular-nums">{money(detail.payment_received)}</td></tr>}
                  </tfoot>
                </table>
                {canSell && detail.status === "DRAFT" && <div className="grid gap-3 sm:grid-cols-2">
                  <SearchableSelect label="Revenue account" required value={chosenRevenue} options={revenueQuery.data ?? []} placeholder="Choose revenue account" onChange={setPostRevenue} />
                  {!isInvoice && <div><label className="mb-1 block text-xs">Payment method</label><select className={input} value={postMethod} onChange={event => setPostMethod(event.target.value as PosPaymentMethod)}><option value="CASH">Cash</option><option value="CARD">Card</option><option value="BANK_TRANSFER">Bank Transfer</option></select></div>}
                  {!isInvoice && postMethod === "CASH" && <div><label className="mb-1 block text-xs">Cash received</label><input className={input} type="number" min={0} value={cashReceived} onChange={event => setCashReceived(event.target.value)} /></div>}
                </div>}
                {isInvoice && ((detail.status === "DRAFT" && canSell) || (legacyInvoice && canManage)) && <div className="grid gap-3 sm:grid-cols-2">
                  <PosCustomerField value={chosenCustomer} onChange={setInvoiceCustomer} customers={billingQuery.data?.customers ?? []} canCreate={canSell} />
                  <div><label className="mb-1 block text-xs">Invoice due date</label><input className={input} type="date" value={chosenDue} onChange={event => setInvoiceDue(event.target.value)} /></div>
                  <SearchableSelect label="Receivable account" value={chosenAR} options={billingQuery.data?.receivable_accounts ?? []} onChange={setInvoiceAccount} />
                  {legacyInvoice && <><div><label className="mb-1 block text-xs">Correction posting date</label><input className={input} type="date" value={correctionDate} onChange={event => setCorrectionDate(event.target.value)} /></div><label className="col-span-full text-sm"><input type="checkbox" checked={confirmUnpaid} onChange={event => setConfirmUnpaid(event.target.checked)} /> This invoice has not been paid. Correct its bank posting to receivables.</label></>}
                </div>}
                {(postMutation.isError || voidMutation.isError || correction.isError || saveEdit.isError) && formError && <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{formError}</div>}
              </div>
            )}
          </DialogBody>
          <DialogFooter>
            {canSell && detail?.status === "DRAFT" && (editing ? <><Button variant="outline" onClick={() => { setEditing(false); setDraftLines((detail.items ?? []).map((item: any) => ({ product_id: item.product_id, quantity: Number(item.quantity), unit_price: Number(item.unit_price) }))); }}>Cancel edit</Button><Button loading={saveEdit.isPending} disabled={!draftLines.length || draftLines.some(line => line.quantity <= 0 || line.unit_price <= 0) || (isInvoice && (!chosenCustomer || !chosenDue))} onClick={() => saveEdit.mutate()}>Save Changes</Button></> : <Button variant="outline" onClick={() => setEditing(true)}><Pencil className="h-4 w-4"/>Edit Draft</Button>)}
            {canSell && detail ? (
              <>
                {detail.status === "DRAFT" && !editing && <Button variant="success" onClick={() => postMutation.mutate(detail.id)} disabled={postMutation.isPending || !chosenRevenue || (isInvoice ? (!chosenCustomer || !chosenDue) : (postMethod === "CASH" && Number(cashReceived) < Number(detail.total_amount)))}><PlayCircle className="h-4 w-4" />Post</Button>}
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
  );
}


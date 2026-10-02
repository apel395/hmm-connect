import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import DateRangeFilter from "@/components/common/DateRangeFilter";
import { Printer } from "lucide-react";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import SearchableSelect from "@/components/form/SearchableSelect";
import { listLocations } from "@/modules/admin/organization/api";
import { createVoucher, listEligibleInvoices, listVouchers } from "../api";
import { todayLocal } from "@/utils/dateConstraints";

const money = (v: unknown) => Number(v || 0).toLocaleString("id-ID", { minimumFractionDigits: 2 });

export default function PaymentVoucherListPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [locationId, setLocationId] = useState<number | undefined>(undefined);
  const [voucherDate, setVoucherDate] = useState(todayLocal);
  const [selected, setSelected] = useState<Record<number, boolean>>({});
  const [page, setPage] = useState(1);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [appliedFromDate, setAppliedFromDate] = useState("");
  const [appliedToDate, setAppliedToDate] = useState("");

  const vouchers = useQuery({
    queryKey: ["payment-vouchers", page, appliedFromDate, appliedToDate],
    queryFn: async () => (await listVouchers({
      page,
      page_size: 20,
      date_from: appliedFromDate || undefined,
      date_to: appliedToDate || undefined,
    })).data,
  });
  const locations = useQuery({ queryKey: ["pv-locations"], queryFn: () => listLocations({ is_active: true }) });
  const eligible = useQuery({
    queryKey: ["pv-eligible", locationId],
    queryFn: async () => (await listEligibleInvoices(locationId!)).data,
    enabled: !!locationId,
  });

  const applyDates = () => {
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
      const ids = Object.entries(selected).filter(([, v]) => v).map(([k]) => Number(k));
      if (!locationId) throw new Error("Select a location");
      if (!ids.length) throw new Error("Select at least one invoice");
      if (!voucherDate) throw new Error("Voucher Date is required");
      const rows = (eligible.data ?? []).filter((r: any) => ids.includes(r.id));
      // group by invoice, use available_balance as allocated_amount
      const allocations = rows.map((r: any) => ({ supplier_invoice_id: r.id, allocated_amount: Number(r.available_balance) }));
      const payload = {
        location_id: locationId,
        voucher_date: voucherDate,
        allocations,
      };
      return (await createVoucher(payload)).data;
    },
    onSuccess: (data: any) => {
      toast.success(`Voucher ${data.voucher_number} created`);
      setSelected({});
      qc.invalidateQueries({ queryKey: ["payment-vouchers"] });
      navigate(`/finance/payment-vouchers/${data.id}`);
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || String(e)),
  });

  const items: any[] = vouchers.data?.items ?? [];
  const eligibleRows: any[] = eligible.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>} title="Payment Vouchers" description="Per-location payment request — select invoices, get approval, then create and post a payment from the Payments screen." />
      <Card className="p-4">
        <div className="mb-3 font-semibold">Create Voucher — Select Location + Invoices</div>
        <div className="grid gap-3 md:grid-cols-3">
          <SearchableSelect label="Location (locked per voucher)" value={locationId} placeholder="Type location code or name..." options={(locations.data ?? []).map((l: any) => ({ id: l.id, label: `${l.code} — ${l.name}`, keywords: [l.code, l.name] }))} onChange={(id) => { setLocationId(id as number); setSelected({}); }} />
          <label className="text-sm">Voucher Date<input type="date" data-accounting-date="true" className="mt-1 h-10 w-full rounded border border-slate-300 px-3" value={voucherDate} onChange={(event) => setVoucherDate(event.target.value)} /></label>
          <div className="flex items-end"><Button loading={create.isPending} disabled={!locationId || !voucherDate || !Object.values(selected).some(Boolean)} onClick={() => create.mutate()}>Create Voucher</Button></div>
        </div>
        {locationId && (
          <div className="mt-4 overflow-x-auto rounded border">
            <table className="w-full min-w-[900px] text-sm">
              <thead><tr className="border-b bg-slate-50"><th className="p-2"><input type="checkbox" checked={eligibleRows.length > 0 && eligibleRows.every((r: any) => selected[r.id])} onChange={(e) => { const next: Record<number, boolean> = {}; eligibleRows.forEach((r: any) => (next[r.id] = e.target.checked)); setSelected(next); }} /></th><th className="p-2 text-left">Invoice</th><th className="p-2 text-left">Supplier</th><th className="p-2">Due</th><th className="p-2 text-right">Outstanding</th></tr></thead>
              <tbody>
                {eligible.isLoading ? <tr><td colSpan={5} className="p-6 text-center text-slate-500">Loading invoices...</td></tr> : eligibleRows.length === 0 ? <tr><td colSpan={5} className="p-6 text-center text-slate-500">No payable invoices for this location.</td></tr> : eligibleRows.map((r: any) => (
                  <tr key={r.id} className="border-b hover:bg-slate-50">
                    <td className="p-2"><input type="checkbox" checked={!!selected[r.id]} onChange={(e) => setSelected({ ...selected, [r.id]: e.target.checked })} /></td>
                    <td className="p-2"><span className="font-mono">{r.invoice_number}</span> <span className="text-slate-500">{r.supplier_invoice_number}</span></td>
                    <td className="p-2">{r.supplier_name}</td>
                    <td className="p-2">{r.due_date || "—"}</td>
                    <td className="p-2 text-right tabular-nums">{money(r.available_balance)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card className="p-4">
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
      </Card>

      <Card className="p-0">
        <Table variant="grid"><THead><TR><TH>Voucher</TH><TH>Location</TH><TH>Period</TH><TH className="text-right">Total</TH><TH>Status</TH><TH /></TR></THead>
          <TBody>
            {items.length === 0 ? <TR><TD colSpan={6} className="py-8 text-center text-slate-500">No vouchers yet.</TD></TR> : items.map((v: any) => (
              <TR key={v.id}>
                <TD><Link to={`/finance/payment-vouchers/${v.id}`} className="font-mono text-blue-600 hover:underline">{v.voucher_number}</Link> <span className="text-xs text-slate-500">{v.voucher_date}</span></TD>
                <TD>{v.location_name}</TD>
                <TD>{v.period_from || "—"} → {v.period_to || "—"}</TD>
                <TD className="text-right tabular-nums">{money(v.total_amount)}</TD>
                <TD><Badge variant={v.status === "APPROVED" ? "success" : v.status === "PENDING_APPROVAL" ? "warning" : v.status === "REJECTED" ? "danger" : "secondary"}>{v.status}</Badge></TD>
                <TD><Link to={`/finance/payment-vouchers/${v.id}`}><Button size="xs" variant="outline">Open</Button></Link></TD>
              </TR>
            ))}
          </TBody>
        </Table>
        <div className="flex items-center justify-between p-3 text-sm"><span>{vouchers.data?.total_items ?? 0} vouchers</span><div className="flex gap-2"><Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button><span>Page {page} of {Math.max(vouchers.data?.total_pages ?? 1, 1)}</span><Button size="sm" variant="outline" disabled={page >= (vouchers.data?.total_pages ?? 1)} onClick={() => setPage(page + 1)}>Next</Button></div></div>
      </Card>
    </div>
  );
}

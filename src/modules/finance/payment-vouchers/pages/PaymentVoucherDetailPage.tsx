import { Printer } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import { approveVoucher, getVoucher, rejectVoucher, submitVoucher, voidVoucher } from "../api";

const money = (v: unknown) => Number(v || 0).toLocaleString("id-ID", { minimumFractionDigits: 2 });

export default function PaymentVoucherDetailPage() {
  const { id } = useParams();
  const voucherId = Number(id);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const q = useQuery({ queryKey: ["payment-voucher", voucherId], queryFn: async () => (await getVoucher(voucherId)).data });

  const submit = useMutation({ mutationFn: () => submitVoucher(voucherId), onSuccess: () => { toast.success("Submitted for approval"); qc.invalidateQueries({ queryKey: ["payment-voucher", voucherId] }); }, onError: (e: any) => toast.error(e.response?.data?.detail || String(e)) });
  const approve = useMutation({ mutationFn: () => approveVoucher(voucherId), onSuccess: () => { toast.success("Approved — create a payment from the Payments screen or below"); qc.invalidateQueries({ queryKey: ["payment-voucher", voucherId] }); qc.invalidateQueries({ queryKey: ["payments"] }); }, onError: (e: any) => toast.error(e.response?.data?.detail || String(e)) });
  const reject = useMutation({ mutationFn: () => rejectVoucher(voucherId, "Rejected from detail"), onSuccess: () => { toast.success("Rejected"); qc.invalidateQueries({ queryKey: ["payment-voucher", voucherId] }); }, onError: (e: any) => toast.error(e.response?.data?.detail || String(e)) });
  const voidIt = useMutation({ mutationFn: () => voidVoucher(voucherId), onSuccess: () => { toast.success("Voided"); navigate("/finance/payment-vouchers"); }, onError: (e: any) => toast.error(e.response?.data?.detail || String(e)) });

  if (q.isLoading) return <div className="py-16 text-center text-slate-500">Loading...</div>;
  if (q.isError) return <div className="py-16 text-center text-red-600">Voucher not found.</div>;
  const v: any = q.data;
  const firstSupplierId = v.groups?.[0]?.supplier_id as number | undefined;

  return (
    <div className="space-y-6">
      <PageHeader title={v.voucher_number} description={`${v.location_name} • ${v.voucher_date} • ${v.status}`} actions={
        <div className="flex gap-2">
          <Link to="/finance/payment-vouchers"><Button variant="outline">Back</Button></Link>
          <Link to={`/finance/payment-vouchers/${v.id}/print`}><Button variant="outline">Print</Button></Link>
          {v.status === "DRAFT" && <Button onClick={() => submit.mutate()} loading={submit.isPending}>Submit</Button>}
          {v.status === "PENDING_APPROVAL" && <><Button onClick={() => approve.mutate()} loading={approve.isPending}>Approve</Button><Button variant="outline" onClick={() => reject.mutate()} loading={reject.isPending}>Reject</Button></>}
          {(v.status === "DRAFT" || v.status === "PENDING_APPROVAL") && <Button variant="outline" onClick={() => voidIt.mutate()} loading={voidIt.isPending}>Void</Button>}
          <Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
</div>
      } />
      <div className="grid gap-3 sm:grid-cols-4">
        <Card className="p-4"><div className="text-xs uppercase text-slate-500">Total</div><div className="mt-1 text-xl font-bold">{money(v.total_amount)}</div></Card>
        <Card className="p-4"><div className="text-xs uppercase text-slate-500">Status</div><div className="mt-1"><Badge variant={v.status === "APPROVED" ? "success" : v.status === "PENDING_APPROVAL" ? "warning" : "secondary"}>{v.status}</Badge></div></Card>
        <Card className="p-4"><div className="text-xs uppercase text-slate-500">Period</div><div className="mt-1">{v.period_from || "—"} → {v.period_to || "—"}</div></Card>
        <Card className="p-4"><div className="text-xs uppercase text-slate-500">Payment</div><div className="mt-1">{v.payment_id ? <Link to={`/payments/${v.payment_id}`} className="text-blue-600 hover:underline">Open Payment #{v.payment_id}</Link> : v.status === "APPROVED" ? <Button size="sm" onClick={() => navigate("/payments", { state: { editPayment: null, voucherId: v.id, voucherSupplierId: firstSupplierId } })}>Create Payment</Button> : "—"}</div></Card>
      </div>
      {v.groups?.map((g: any) => (
        <Card key={g.supplier_id} className="p-0">
          <div className="border-b bg-slate-50 px-4 py-3 flex items-center justify-between"><div><div className="font-semibold">{g.supplier_name} <span className="font-mono text-xs text-slate-500">{g.supplier_code}</span></div><div className="text-xs text-slate-500">{g.bank ? `${g.bank.bank_name} — ${g.bank.account_number} (${g.bank.account_name})` : "Bank not set"}</div></div><div className="text-right"><div className="text-xs uppercase text-slate-500">Supplier Total</div><div className="font-bold">{money(g.total)}</div></div></div>
          <Table variant="grid"><THead><TR><TH>Invoice</TH><TH>Date</TH><TH>Due</TH><TH className="text-right">Total</TH><TH className="text-right">Allocated</TH></TR></THead>
            <TBody>{g.invoices.map((inv: any) => <TR key={inv.id}><TD><span className="font-mono">{inv.invoice_number}</span> <span className="text-xs text-slate-500">{inv.supplier_invoice_number}</span></TD><TD>{inv.invoice_date}</TD><TD>{inv.due_date || "—"}</TD><TD className="text-right">{money(inv.total_amount)}</TD><TD className="text-right font-semibold">{money(inv.allocated_amount)}</TD></TR>)}</TBody>
          </Table>
        </Card>
      ))}
    </div>
  );
}

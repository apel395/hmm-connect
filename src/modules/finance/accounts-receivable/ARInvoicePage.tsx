import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { Settings2 } from "lucide-react";
import { toast } from "sonner";
import api from "@/api/client";
import Button from "@/components/ui/Button";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import useAuthStore from "@/store/auth";

type Layout = { title: string; billing_name: string; billing_address: string; description: string; payment_instructions: string; footer: string; show_settlement: boolean };
type Invoice = { id: number; invoice_number: string; invoice_date: string; due_date: string; amount: string; received_amount: string; outstanding_amount: string; customer_id: number; customer_name: string; customer_address: string | null; layout: Layout };
const fields = [["title", "Invoice title"], ["billing_name", "Client billing name"], ["billing_address", "Client billing address"], ["description", "Description label"], ["payment_instructions", "Payment instructions"], ["footer", "Client footer / terms"]] as const;
const money = (value: unknown) => Number(value || 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function ARInvoicePage() {
  const { id } = useParams();
  const client = useQueryClient();
  const canManage = useAuthStore(s => s.hasPermission("finance.manage"));
  const [open, setOpen] = useState(false);
  const [layout, setLayout] = useState<Layout | null>(null);
  const invoice = useQuery({ queryKey: ["ar-invoice-print", id], queryFn: async () => (await api.get<Invoice>(`/ar-invoice-print/${id}`)).data });
  useEffect(() => { if (invoice.data) setLayout(invoice.data.layout); }, [invoice.data]);
  const save = useMutation({ mutationFn: () => api.put(`/ar-invoice-print/clients/${invoice.data?.customer_id}`, layout), onSuccess: () => { client.invalidateQueries({ queryKey: ["ar-invoice-print"] }); setOpen(false); toast.success("Client invoice layout saved"); }, onError: () => toast.error("Client layout could not be saved") });
  const data = invoice.data;
  if (invoice.isPending) return <p data-print-ready="false">Loading invoice…</p>;
  if (invoice.isError || !data) return <p data-print-ready="false" role="alert">Invoice could not load.</p>;
  return <div className="space-y-2">
    <div className="flex justify-end gap-1 print:hidden">{canManage && <Button size="sm" variant="outline" aria-label="Client invoice layout" title="Client invoice layout" onClick={() => setOpen(true)}><Settings2 size={15} /></Button>}<PrintPreviewButton title="AR Invoice" ariaLabel="Print client invoice" src={`/accounts-receivable/invoices/${id}/print`} /></div>
    <article className="print-document mx-auto max-w-4xl bg-white p-6 font-sans text-sm" data-print-ready="true">
      <style>{`@page { size:A4 portrait; margin:15mm; } @media print { article { font:10pt Arial; } .print-document { padding:0!important; } }`}</style>
      <header className="mb-5 flex justify-between border-b-2 border-slate-800 pb-3"><div><h1 className="text-xl font-bold">PT. MUTIARA MERDEKA HOTEL</h1><p className="text-xs">MMH-Connect</p></div><div className="text-right"><h2 className="text-xl font-bold">{data.layout.title}</h2><p>{data.invoice_number}</p></div></header>
      <div className="mb-6 grid grid-cols-2 gap-4"><div><b>Bill to</b><p>{data.layout.billing_name || data.customer_name}</p><p className="whitespace-pre-line">{data.layout.billing_address || data.customer_address || ""}</p></div><div className="text-right"><p>Invoice date: {data.invoice_date}</p><p>Due date: {data.due_date || "—"}</p></div></div>
      <table className="w-full border-collapse"><thead><tr className="border-y bg-slate-50"><th className="p-2 text-left">Description</th><th className="p-2 text-right">Amount</th></tr></thead><tbody><tr className="border-b"><td className="p-2">{data.layout.description}</td><td className="p-2 text-right tabular-nums">{money(data.amount)}</td></tr></tbody><tfoot><tr className="font-bold"><td className="p-2">Invoice total</td><td className="p-2 text-right">{money(data.amount)}</td></tr>{data.layout.show_settlement && <><tr><td className="p-2">Received</td><td className="p-2 text-right">{money(data.received_amount)}</td></tr><tr className="font-bold"><td className="p-2">Outstanding</td><td className="p-2 text-right">{money(data.outstanding_amount)}</td></tr></>}</tfoot></table>
      {data.layout.payment_instructions && <section className="mt-8 whitespace-pre-line"><b>Payment instructions</b><p>{data.layout.payment_instructions}</p></section>}
      {data.layout.footer && <footer className="mt-8 whitespace-pre-line border-t pt-3">{data.layout.footer}</footer>}
    </article>
    <Dialog open={open} onOpenChange={setOpen}><DialogContent><DialogHeader><DialogTitle>Invoice layout — {data.customer_name}</DialogTitle></DialogHeader><DialogBody>{layout && <div className="grid gap-2">{fields.map(([key, label]) => <label key={key} className="text-xs">{label}<textarea className="mt-1 w-full rounded border p-2" rows={key === "billing_address" || key === "payment_instructions" ? 3 : 2} value={layout[key]} onChange={e => setLayout({ ...layout, [key]: e.target.value })} /></label>)}<label className="flex gap-2 text-xs"><input type="checkbox" checked={layout.show_settlement} onChange={e => setLayout({ ...layout, show_settlement: e.target.checked })} />Show settlement and outstanding</label></div>}</DialogBody><DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Close</Button><Button loading={save.isPending} onClick={() => save.mutate()}>Save client layout</Button></DialogFooter></DialogContent></Dialog>
  </div>;
}

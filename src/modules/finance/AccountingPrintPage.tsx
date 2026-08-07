import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import api from "@/api/client";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";

const money = (value: unknown) => Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function AccountingPrintPage({ kind }: { kind: "supplier-invoices" | "journal-entries" | "payments" }) {
  const { id } = useParams();
  const query = useQuery({ queryKey: [kind, id, "print"], queryFn: async () => (await api.get(`/${kind}/${id}/print`)).data, enabled: !!id });
  if (query.isLoading) return <Loading/>;
  if (!query.data) return <p>Document could not be loaded.</p>;
  const data = query.data;
  const isJournal = kind === "journal-entries";
  const isPayment = kind === "payments";
  const rows = isPayment ? data.allocations : data.lines;
  const documentTitle = isPayment ? "Payment Voucher" : data.document_type;

  return <article className="print-document mx-auto max-w-[210mm] bg-white p-8 text-black">
    <div className="print-actions mb-6 flex justify-end"><Button onClick={() => window.print()}>Print</Button></div>
    <header className="mb-8 flex justify-between border-b-2 border-black pb-5"><div><h1 className="text-2xl font-bold">HMM-Connect</h1><div>Hotel Mutiara Merdeka</div></div><div className="text-right"><h2 className="text-2xl font-bold">{documentTitle}</h2><div>{data.payment_number || data.journal_number || data.internal_invoice_number}</div></div></header>
    <div className="mb-6 grid grid-cols-2 gap-3"><div>Date: {data.payment_date || data.journal_date || data.invoice_date}</div><div>Status: {data.status}</div><div>Reference: {data.reference_number || data.supplier_invoice_number || "—"}</div><div>Description: {data.description || data.notes || "—"}</div>{isPayment && <><div>Supplier: {data.supplier_name}</div><div>Payment Method: {String(data.payment_method || "—").replaceAll("_", " ")}</div></>}</div>
    <table className="w-full border-collapse text-sm"><thead><tr><th className="border p-2 text-left">{isPayment ? "Invoice" : "Account / Item"}</th><th className="border p-2 text-left">Description</th>{isJournal ? <><th className="border p-2 text-right">Debit</th><th className="border p-2 text-right">Credit</th></> : isPayment ? <><th className="border p-2 text-right">Invoice Total</th><th className="border p-2 text-right">Allocated</th></> : <><th className="border p-2 text-right">Quantity</th><th className="border p-2 text-right">Amount</th></>}</tr></thead><tbody>{rows.map((line: any) => <tr key={line.id}><td className="border p-2">{isPayment ? line.invoice_number : isJournal ? `${line.account_code} — ${line.account_name}` : line.product_name || "Manual line"}</td><td className="border p-2">{isPayment ? (line.due_date ? `Due ${line.due_date}` : "—") : line.description}</td>{isJournal ? <><td className="border p-2 text-right">{money(line.debit)}</td><td className="border p-2 text-right">{money(line.credit)}</td></> : isPayment ? <><td className="border p-2 text-right">{money(line.invoice_total)}</td><td className="border p-2 text-right">{money(line.allocated_amount)}</td></> : <><td className="border p-2 text-right">{line.quantity}</td><td className="border p-2 text-right">{money(line.line_amount)}</td></>}</tr>)}</tbody></table>
    {isPayment && <section className="mt-6"><h3 className="mb-2 font-bold">Funding Accounts</h3><table className="w-full border-collapse text-sm"><thead><tr><th className="border p-2 text-left">Bank</th><th className="border p-2 text-left">Account</th><th className="border p-2 text-left">Account Number</th><th className="border p-2 text-right">Amount</th></tr></thead><tbody>{data.funding_lines?.map((line: any) => <tr key={line.id}><td className="border p-2">{line.bank_name}</td><td className="border p-2">{line.account_name}</td><td className="border p-2">{line.account_number}</td><td className="border p-2 text-right">{money(line.amount)}</td></tr>)}</tbody></table></section>}
    {isJournal && <div className="mt-5 text-right font-bold">Total Debit: {money(data.total_debit)} · Total Credit: {money(data.total_credit)}</div>}
    {isPayment && <><div className="mt-5 space-y-1 text-right"><div className="font-bold">Payment Total: {money(data.total_amount)}</div><div>Related Journal: {data.journal_number || "—"}</div></div><div className="mt-14 grid grid-cols-3 gap-10 text-center text-sm"><div><div className="h-16"/><div className="border-t border-black pt-2">Prepared By</div><div className="text-xs text-slate-600">{data.created_by_name || "Finance"}</div></div><div><div className="h-16"/><div className="border-t border-black pt-2">Approved By</div><div className="text-xs text-slate-600">{data.approved_by_name || "—"}</div></div><div><div className="h-16"/><div className="border-t border-black pt-2">Receiver / Bank Reference</div><div className="text-xs text-slate-600">{data.reference_number || "—"}</div></div></div></>}
    <footer className="mt-10 border-t pt-3 text-xs">Created by {data.created_by_name || "—"} · Posted by {data.posted_by_name || "—"} · Printed at {new Date(data.generated_at).toLocaleString()}</footer>
  </article>;
}

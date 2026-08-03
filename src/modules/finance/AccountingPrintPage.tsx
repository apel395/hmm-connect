import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import api from "@/api/client";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";
export default function AccountingPrintPage({
  kind,
}: {
  kind: "supplier-invoices" | "journal-entries" | "payments";
}) {
  const { id } = useParams(),
    q = useQuery({
      queryKey: [kind, id, "print"],
      queryFn: async () => (await api.get(`/${kind}/${id}/print`)).data,
      enabled: !!id,
    });
  if (q.isLoading) return <Loading />;
  if (!q.data) return <p>Document could not be loaded.</p>;
  const x = q.data,
    isJournal = kind === "journal-entries",
    isPayment = kind === "payments",
    rows = isPayment ? x.allocations : x.lines;
  return (
    <article className="print-document mx-auto max-w-[210mm] bg-white p-8 text-black">
      <div className="print-actions mb-6 flex justify-end">
        <Button onClick={() => window.print()}>Print</Button>
      </div>
      <header className="mb-8 flex justify-between border-b-2 border-black pb-5">
        <div>
          <h1 className="text-2xl font-bold">HMM-Connect</h1>
          <div>Hotel Mutiara Merdeka</div>
        </div>
        <div className="text-right">
          <h2 className="text-2xl font-bold">{x.document_type}</h2>
          <div>
            {x.payment_number || x.journal_number || x.internal_invoice_number}
          </div>
        </div>
      </header>
      <div className="mb-6 grid grid-cols-2 gap-3">
        <div>Date: {x.payment_date || x.journal_date || x.invoice_date}</div>
        <div>Status: {x.status}</div>
        <div>
          Reference: {x.reference_number || x.supplier_invoice_number || "—"}
        </div>
        <div>Description: {x.description || x.notes || "—"}</div>
        {isPayment && (
          <>
            <div>Supplier: {x.supplier_name}</div>
            <div>
              Payment Account: {x.payment_account_code} —{" "}
              {x.payment_account_name}
            </div>
          </>
        )}
      </div>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            <th className="border p-2 text-left">
              {isPayment ? "Invoice" : "Account / Item"}
            </th>
            <th className="border p-2 text-left">Description</th>
            {isJournal ? (
              <>
                <th className="border p-2 text-right">Debit</th>
                <th className="border p-2 text-right">Credit</th>
              </>
            ) : isPayment ? (
              <>
                <th className="border p-2 text-right">Invoice Total</th>
                <th className="border p-2 text-right">Allocated</th>
              </>
            ) : (
              <>
                <th className="border p-2 text-right">Quantity</th>
                <th className="border p-2 text-right">Amount</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((l: any) => (
            <tr key={l.id}>
              <td className="border p-2">
                {isPayment
                  ? l.invoice_number
                  : isJournal
                    ? `${l.account_code} — ${l.account_name}`
                    : l.product_name || "Manual line"}
              </td>
              <td className="border p-2">
                {isPayment
                  ? l.due_date
                    ? `Due ${l.due_date}`
                    : "—"
                  : l.description}
              </td>
              {isJournal ? (
                <>
                  <td className="border p-2 text-right">
                    {Number(l.debit).toLocaleString()}
                  </td>
                  <td className="border p-2 text-right">
                    {Number(l.credit).toLocaleString()}
                  </td>
                </>
              ) : isPayment ? (
                <>
                  <td className="border p-2 text-right">
                    {Number(l.invoice_total).toLocaleString()}
                  </td>
                  <td className="border p-2 text-right">
                    {Number(l.allocated_amount).toLocaleString()}
                  </td>
                </>
              ) : (
                <>
                  <td className="border p-2 text-right">{l.quantity}</td>
                  <td className="border p-2 text-right">
                    {Number(l.line_amount).toLocaleString()}
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {isJournal && (
        <div className="mt-5 text-right font-bold">
          Total Debit: {Number(x.total_debit).toLocaleString()} · Total Credit:{" "}
          {Number(x.total_credit).toLocaleString()}
        </div>
      )}
      {isPayment && (
        <div className="mt-5 space-y-1 text-right">
          <div className="font-bold">Payment Total: {Number(x.total_amount).toLocaleString()}</div>
          <div>Approved by: {x.approved_by_name || "—"}</div>
          <div>Related Journal: {x.journal_number || "—"}</div>
        </div>
      )}
      <footer className="mt-10 border-t pt-3 text-xs">
        Created by {x.created_by_name || "—"} · Posted by{" "}
        {x.posted_by_name || "—"} · Printed at{" "}
        {new Date(x.generated_at).toLocaleString()}
      </footer>
    </article>
  );
}

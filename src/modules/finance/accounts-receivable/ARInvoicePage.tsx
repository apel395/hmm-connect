import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { FilePenLine, Settings2 } from "lucide-react";
import { toast } from "sonner";
import api from "@/api/client";
import Button from "@/components/ui/Button";
import Dialog, {
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import useAuthStore from "@/store/auth";
import useFormRecovery from "@/hooks/useFormRecovery";

import ARReceiptForm from "./ARReceiptForm";
import PHRInvoice from "./PHRInvoice";
import {
  type Invoice,
  type InvoiceDocument,
  type Layout,
  money,
} from "./arInvoiceTypes";
const validInvoiceDraft = (value: unknown): value is InvoiceDocument | null => {
  if (value === null) return true;
  if (!value || typeof value !== "object") return false;
  const doc = value as Record<string, unknown>;
  return typeof doc.description === "string"
    && Array.isArray(doc.lines)
    && typeof doc.tax_amount === "string"
    && doc.lines.every((line: unknown) => !!line && typeof line === "object"
      && typeof (line as Record<string, unknown>).registration_number === "string"
      && typeof (line as Record<string, unknown>).description === "string");
};
const cents = (value: string | number) => Math.round(Number(value || 0) * 100);
const fields = [
  ["title", "Invoice title"],
  ["billing_name", "Client billing name"],
  ["billing_address", "Client billing address"],
  ["description", "Description label"],
  ["payment_instructions", "Payment instructions"],
  ["footer", "Client footer / terms"],
  ["company_address", "Company letterhead address"],
  ["attention", "Attention"],
  ["contract_number", "Default contract number"],
  ["signer_name", "Authorized signatory"],
  ["signer_position", "Signatory position"],
] as const;

export default function ARInvoicePage() {
  const { id } = useParams();
  const client = useQueryClient();
  const canManage = useAuthStore((s) => s.hasPermission("finance.manage"));
  const [documentOpen, setDocumentOpen] = useState(false);
  const [document, setDocument] = useState<InvoiceDocument | null>(null);
  const [open, setOpen] = useState(false);
  const [layout, setLayout] = useState<Layout | null>(null);
  const documentRecovery = useFormRecovery(`catering:invoice-document:${id}`, document, documentOpen, validInvoiceDraft);
  const invoice = useQuery({
    queryKey: ["ar-invoice-print", id],
    queryFn: async () =>
      (await api.get<Invoice>(`/ar-invoice-print/${id}`)).data,
  });
  useEffect(() => {
    if (invoice.data) {
      setLayout(invoice.data.layout);
      if (!documentOpen) setDocument(invoice.data.document);
    }
  }, [invoice.data, documentOpen]);
  const save = useMutation({
    mutationFn: () =>
      api.put(`/ar-invoice-print/clients/${invoice.data?.customer_id}`, layout),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["ar-invoice-print"] });
      setOpen(false);
      toast.success("Client invoice layout saved");
    },
    onError: () => toast.error("Client layout could not be saved"),
  });
  const saveDocument = useMutation({
    mutationFn: () => api.put(`/ar-invoice-print/${id}/document`, document),
    onSuccess: () => {
      documentRecovery.clear();
      void client.invalidateQueries({ queryKey: ["ar-invoice-print"] });
      setDocumentOpen(false);
      toast.success("Invoice print details saved");
    },
    onError: (error: any) =>
      toast.error(typeof error?.response?.data?.detail === "string"
        ? error.response.data.detail : "Invoice print details could not be saved"),
  });
  const data = invoice.data;
  const subtotalCents = document?.lines.reduce((total, line) => total + cents(line.amount), 0) ?? 0;
  const taxCents = cents(document?.tax_amount ?? "0");
  const grandCents = subtotalCents + taxCents;
  const expectedCents = cents(data?.amount ?? "0");
  const documentInvalid = !document || !document.lines.length || grandCents !== expectedCents
    || !Number.isFinite(grandCents) || !Number.isFinite(taxCents) || taxCents < 0
    || document.lines.some(line => !line.description.trim() || !Number.isFinite(Number(line.amount))
      || Number(line.amount) < 0
      || Boolean(line.service_period_from && line.service_period_to
        && line.service_period_to < line.service_period_from));
  if (invoice.isPending)
    return <p data-print-ready="false">Loading invoice…</p>;
  if (invoice.isError || !data)
    return (
      <p data-print-ready="false" role="alert">
        Invoice could not load.
      </p>
    );
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-4 rounded border bg-white px-3 py-2 text-sm print:hidden"><span>Invoice: <strong>{money(data.amount)}</strong></span><span>Received: <strong>{money(data.received_amount)}</strong></span><span>Outstanding: <strong>{money(data.outstanding_amount)}</strong></span></div>
      {!!data.receipts?.length && <div className="rounded border bg-white px-3 py-2 text-xs print:hidden">{data.receipts.map(receipt => <div key={receipt.id} className="flex gap-4 py-1"><span>{receipt.payment_number}</span><span>{receipt.payment_date}</span><span>{money(receipt.amount)}</span><span>{receipt.reference_number}</span></div>)}</div>}
      <div className="flex justify-end gap-1 print:hidden">
        {canManage && data.account_id && Number(data.outstanding_amount) > 0 && <ARReceiptForm key={data.id} invoiceId={data.id} outstanding={data.outstanding_amount} />}
        {canManage && (
          <Button
            size="sm"
            variant="outline"
            aria-label="Client invoice layout"
            title="Client invoice layout"
            onClick={() => setOpen(true)}
          >
            <Settings2 size={15} />
          </Button>
        )}
        {canManage && data.layout.template === "phr" && (
          <Button
            size="sm"
            variant="outline"
            title="Invoice service details"
            aria-label="Invoice service details"
            onClick={() => {
              setDocument(documentRecovery.load() ?? data.document);
              setDocumentOpen(true);
            }}
          >
            <FilePenLine size={15} />
          </Button>
        )}
        {(data.layout.template !== "phr" || data.print_ready) && (
          <PrintPreviewButton
            title="AR Invoice"
            ariaLabel="Print client invoice"
            src={`/accounts-receivable/invoices/${id}/print`}
          />
        )}
      </div>
      {data.layout.template === "phr" ? (
        <PHRInvoice data={data} />
      ) : (
        <article
          className="print-document mx-auto max-w-4xl bg-white p-6 font-sans text-sm"
          data-print-ready="true"
        >
          <style>{`@page { size:A4 portrait; margin:15mm; } @media print { article { font:10pt Roboto, Arial, sans-serif; } .print-document { padding:0!important; } }`}</style>
          <header className="mb-5 flex justify-between border-b-2 border-slate-800 pb-3">
            <div>
              <h1 className="text-xl font-bold">PT. MUTIARA MERDEKA HOTEL</h1>
              <p className="text-xs">MMH-Connect</p>
            </div>
            <div className="text-right">
              <h2 className="text-xl font-bold">{data.layout.title}</h2>
              <p>{data.invoice_number}</p>
            </div>
          </header>
          <div className="mb-6 grid grid-cols-2 gap-4">
            <div>
              <b>Bill to</b>
              <p>{data.layout.billing_name || data.customer_name}</p>
              <p className="whitespace-pre-line">
                {data.layout.billing_address || data.customer_address || ""}
              </p>
            </div>
            <div className="text-right">
              <p>Invoice date: {data.invoice_date}</p>
              <p>Due date: {data.due_date || "—"}</p>
            </div>
          </div>
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-y bg-slate-50">
                <th className="p-2 text-left">Description</th>
                <th className="p-2 text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b">
                <td className="p-2">{data.layout.description}</td>
                <td className="p-2 text-right tabular-nums">
                  {money(data.amount)}
                </td>
              </tr>
            </tbody>
            <tfoot>
              <tr className="font-bold">
                <td className="p-2">Invoice total</td>
                <td className="p-2 text-right">{money(data.amount)}</td>
              </tr>
              {data.layout.show_settlement && (
                <>
                  <tr>
                    <td className="p-2">Received</td>
                    <td className="p-2 text-right">
                      {money(data.received_amount)}
                    </td>
                  </tr>
                  <tr className="font-bold">
                    <td className="p-2">Outstanding</td>
                    <td className="p-2 text-right">
                      {money(data.outstanding_amount)}
                    </td>
                  </tr>
                </>
              )}
            </tfoot>
          </table>
          {data.layout.payment_instructions && (
            <section className="mt-8 whitespace-pre-line">
              <b>Payment instructions</b>
              <p>{data.layout.payment_instructions}</p>
            </section>
          )}
          {data.layout.footer && (
            <footer className="mt-8 whitespace-pre-line border-t pt-3">
              {data.layout.footer}
            </footer>
          )}
        </article>
      )}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invoice layout — {data.customer_name}</DialogTitle>
          </DialogHeader>
          <DialogBody>
            {layout && (
              <div className="grid gap-2">
                <label className="text-xs">
                  Client template
                  <select
                    className="mt-1 w-full rounded border p-2"
                    value={layout.template}
                    onChange={(e) =>
                      setLayout({
                        ...layout,
                        template: e.target.value as Layout["template"],
                        ...(e.target.value === "phr"
                          ? {
                              billing_name:
                                layout.billing_name ||
                                "PT. Pertamina Hulu Rokan",
                              billing_address:
                                layout.billing_address ||
                                "16th Floor, RDTX Place Building\nJl. Prof. Dr. Satrio Kav. E-IV Kuningan\nJakarta Selatan 12930",
                              company_address:
                                layout.company_address ||
                                "Jln. Yos Sudarso 12 A, Pekanbaru - Riau - Indonesia",
                            }
                          : {}),
                      })
                    }
                  >
                    <option value="standard">Standard</option>
                    <option value="phr">PHR catering invoice</option>
                  </select>
                </label>
                <label className="text-xs">
                  Default contract date
                  <input
                    type="date"
                    className="mt-1 w-full rounded border p-2"
                    value={layout.contract_date || ""}
                    onChange={(e) =>
                      setLayout({
                        ...layout,
                        contract_date: e.target.value || null,
                      })
                    }
                  />
                </label>
                {fields.map(([key, label]) => (
                  <label key={key} className="text-xs">
                    {label}
                    <textarea
                      className="mt-1 w-full rounded border p-2"
                      rows={
                        key === "billing_address" ||
                        key === "payment_instructions"
                          ? 3
                          : 2
                      }
                      value={layout[key]}
                      onChange={(e) =>
                        setLayout({ ...layout, [key]: e.target.value })
                      }
                    />
                  </label>
                ))}
                <label className="flex gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={layout.show_settlement}
                    onChange={(e) =>
                      setLayout({
                        ...layout,
                        show_settlement: e.target.checked,
                      })
                    }
                  />
                  Show settlement and outstanding
                </label>
              </div>
            )}
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Close
            </Button>
            <Button loading={save.isPending} onClick={() => save.mutate()}>
              Save client layout
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={documentOpen} onOpenChange={setDocumentOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Invoice service details — {data.invoice_number}
            </DialogTitle>
          </DialogHeader>
          <DialogBody>
            {document && (
              <div className="grid gap-3">
                <p className="text-xs text-slate-600">
                  Accounting invoice <strong>{data.invoice_number}</strong> · Posted AR amount <strong>Rp {money(data.amount)}</strong>.
                  Printed service details never change journal, tax liability, or payment balances.
                </p>
                {documentRecovery.failed && <p className="text-xs text-amber-700">Browser storage unavailable; keep this dialog open until saved.</p>}
                <label className="text-xs">
                  Customer-facing invoice number
                  <input
                    aria-label="Printed invoice number"
                    className="mt-1 w-full rounded border p-2"
                    maxLength={100}
                    placeholder="MMH-MNS/186/VI/2026 (optional)"
                    value={document.billing_invoice_number ?? ""}
                    onChange={(e) => setDocument({ ...document, billing_invoice_number: e.target.value })}
                  />
                  <span className="mt-1 block text-slate-500">Optional printed reference; internal POS/AR invoice ID remains {data.invoice_number}.</span>
                </label>
                {(
                  [
                    ["description", "Service period / description"],
                    ["contract_number", "Contract number (override)"],
                    ["tax_label", "Tax label"],
                    ["amount_in_words", "Amount in words"],
                  ] as const
                ).map(([key, label]) => (
                  <label className="text-xs" key={key}>
                    {label}
                    <textarea
                      className="mt-1 w-full rounded border p-2"
                      value={document[key]}
                      onChange={(e) =>
                        setDocument({ ...document, [key]: e.target.value })
                      }
                    />
                  </label>
                ))}
                <label className="text-xs">
                  Contract date (override)
                  <input
                    type="date"
                    className="mt-1 w-full rounded border p-2"
                    value={document.contract_date || ""}
                    onChange={(e) =>
                      setDocument({
                        ...document,
                        contract_date: e.target.value || null,
                      })
                    }
                  />
                </label>
                <div className="flex items-center justify-between">
                  <strong className="text-sm">Service registrations ({document.lines.length})</strong>
                  <span className="text-xs text-slate-500">Each registration or billing period is a separate line.</span>
                </div>
                {document.lines.map((line, index) => (
                  <div key={line.source_line_id ?? `new-${index}`} className="grid gap-2 rounded border p-3 sm:grid-cols-2">
                    <div className="flex items-center justify-between sm:col-span-2">
                      <span className="text-xs font-semibold">Line {index + 1}</span>
                      <div className="flex gap-2">
                        <Button variant="outline" onClick={() => setDocument({
                          ...document,
                          lines: [...document.lines.slice(0, index + 1), {
                            source_line_id: null,
                            registration_number: "",
                            description: line.description,
                            service_period_from: null,
                            service_period_to: null,
                            amount: line.amount,
                          }, ...document.lines.slice(index + 1)],
                        })}>Duplicate</Button>
                        <Button variant="outline" onClick={() => setDocument({
                          ...document,
                          lines: document.lines.filter((_, i) => i !== index),
                        })}>Remove</Button>
                      </div>
                    </div>
                    <label className="text-xs">
                      Registration number
                      <input
                        aria-label={`Registration number line ${index + 1}`}
                        className="mt-1 w-full rounded border p-2"
                        maxLength={150}
                        value={line.registration_number}
                        onChange={(e) => setDocument({ ...document, lines: document.lines.map((l, i) =>
                          i === index ? { ...l, registration_number: e.target.value } : l) })}
                      />
                    </label>
                    <label className="text-xs">
                      Amount (IDR)
                      <input
                        aria-label={`Amount line ${index + 1}`}
                        type="number"
                        min="0"
                        step="0.01"
                        className="mt-1 w-full rounded border p-2"
                        value={line.amount}
                        onChange={(e) => setDocument({ ...document, lines: document.lines.map((l, i) =>
                          i === index ? { ...l, amount: e.target.value } : l) })}
                      />
                    </label>
                    <label className="text-xs sm:col-span-2">
                      Service
                      <textarea
                        aria-label={`Service line ${index + 1}`}
                        className="mt-1 w-full rounded border p-2"
                        maxLength={1000}
                        rows={2}
                        value={line.description}
                        onChange={(e) => setDocument({ ...document, lines: document.lines.map((l, i) =>
                          i === index ? { ...l, description: e.target.value } : l) })}
                      />
                    </label>
                    <label className="text-xs">
                      Period from
                      <input
                        type="date"
                        aria-label={`Period from line ${index + 1}`}
                        className="mt-1 w-full rounded border p-2"
                        value={line.service_period_from ?? ""}
                        onChange={(e) => setDocument({ ...document, lines: document.lines.map((l, i) =>
                          i === index ? { ...l, service_period_from: e.target.value || null } : l) })}
                      />
                    </label>
                    <label className="text-xs">
                      Period to
                      <input
                        type="date"
                        aria-label={`Period to line ${index + 1}`}
                        className="mt-1 w-full rounded border p-2"
                        value={line.service_period_to ?? ""}
                        onChange={(e) => setDocument({ ...document, lines: document.lines.map((l, i) =>
                          i === index ? { ...l, service_period_to: e.target.value || null } : l) })}
                      />
                    </label>
                  </div>
                ))}
                <Button
                  variant="outline"
                  disabled={document.lines.length >= 200}
                  onClick={() => setDocument({ ...document, lines: [
                    ...document.lines, {
                      source_line_id: null,
                      registration_number: "",
                      description: "",
                      service_period_from: null,
                      service_period_to: null,
                      amount: "0",
                    },
                  ] })}
                >Add registration line</Button>
                <label className="text-xs">
                  Tax amount
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    className="w-full border p-2"
                    value={document.tax_amount}
                    onChange={(e) =>
                      setDocument({ ...document, tax_amount: e.target.value })
                    }
                  />
                </label>
              </div>
            )}
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDocumentOpen(false)}>
              Close
            </Button>
            <Button
              loading={saveDocument.isPending}
              onClick={() => saveDocument.mutate()}
            >
              Save invoice details
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

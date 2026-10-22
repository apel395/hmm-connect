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

import ARReceiptForm from "./ARReceiptForm";
import PHRInvoice from "./PHRInvoice";
import {
  type Invoice,
  type InvoiceDocument,
  type Layout,
  money,
} from "./arInvoiceTypes";
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
  const invoice = useQuery({
    queryKey: ["ar-invoice-print", id],
    queryFn: async () =>
      (await api.get<Invoice>(`/ar-invoice-print/${id}`)).data,
  });
  useEffect(() => {
    if (invoice.data) {
      setLayout(invoice.data.layout);
      setDocument(invoice.data.document);
    }
  }, [invoice.data]);
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
      client.invalidateQueries({ queryKey: ["ar-invoice-print"] });
      setDocumentOpen(false);
      toast.success("Invoice print details saved");
    },
    onError: () =>
      toast.error("Service amounts plus tax must equal the AR invoice amount"),
  });
  const data = invoice.data;
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
            onClick={() => setDocumentOpen(true)}
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
          <style>{`@page { size:A4 portrait; margin:15mm; } @media print { article { font:10pt Arial; } .print-document { padding:0!important; } }`}</style>
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
                <p className="text-xs">
                  AR invoice amount: Rp {money(data.amount)}
                </p>
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
                {document.lines.map((line, index) => (
                  <div key={index} className="grid gap-1 rounded border p-2">
                    <label className="text-xs">
                      Registration number
                      <input
                        className="w-full border p-2"
                        value={line.registration_number}
                        onChange={(e) =>
                          setDocument({
                            ...document,
                            lines: document.lines.map((l, i) =>
                              i === index
                                ? { ...l, registration_number: e.target.value }
                                : l,
                            ),
                          })
                        }
                      />
                    </label>
                    <label className="text-xs">
                      Service
                      <textarea
                        className="w-full border p-2"
                        value={line.description}
                        onChange={(e) =>
                          setDocument({
                            ...document,
                            lines: document.lines.map((l, i) =>
                              i === index
                                ? { ...l, description: e.target.value }
                                : l,
                            ),
                          })
                        }
                      />
                    </label>
                    <label className="text-xs">
                      Amount
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        className="w-full border p-2"
                        value={line.amount}
                        onChange={(e) =>
                          setDocument({
                            ...document,
                            lines: document.lines.map((l, i) =>
                              i === index
                                ? { ...l, amount: e.target.value }
                                : l,
                            ),
                          })
                        }
                      />
                    </label>
                    <Button
                      variant="outline"
                      onClick={() =>
                        setDocument({
                          ...document,
                          lines: document.lines.filter((_, i) => i !== index),
                        })
                      }
                    >
                      Remove service
                    </Button>
                  </div>
                ))}
                <Button
                  variant="outline"
                  onClick={() =>
                    setDocument({
                      ...document,
                      lines: [
                        ...document.lines,
                        {
                          registration_number: "",
                          description: "",
                          amount: "0",
                        },
                      ],
                    })
                  }
                >
                  Add service
                </Button>
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

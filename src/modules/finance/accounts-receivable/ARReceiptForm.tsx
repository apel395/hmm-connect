import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "@/api/client";
import Button from "@/components/ui/Button";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import SearchableSelect from "@/components/form/SearchableSelect";
import useFormRecovery from "@/hooks/useFormRecovery";

type Input = { amount: string; paymentDate: string; cashAccountId?: number; method: string; reference: string; requestKey: string };
const valid = (v: unknown): v is Input => !!v && typeof v === "object" && ["amount", "paymentDate", "method", "reference", "requestKey"].every(key => typeof (v as Record<string, unknown>)[key] === "string");
const field = "h-9 w-full rounded border px-2 text-sm";
export default function ARReceiptForm({ invoiceId, outstanding }: { invoiceId: number; outstanding: string }) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState<Input>({ amount: "", paymentDate: "", method: "BANK_TRANSFER", reference: "", requestKey: "" });
  const [error, setError] = useState("");
  const recovery = useFormRecovery(`ar:receipt:${invoiceId}`, input, open, valid);
  const options = useQuery({ queryKey: ["customer-receipt-options", invoiceId], queryFn: async () => (await api.get("/customer-payments/options")).data, enabled: open });
  const change = <K extends keyof Input>(key: K, value: Input[K]) => setInput(previous => ({ ...previous, [key]: value }));
  const save = useMutation({
    mutationFn: () => api.post("/customer-payments", { account_receivable_id: invoiceId, amount: input.amount, payment_date: input.paymentDate, cash_account_id: input.cashAccountId, payment_method: input.method, reference_number: input.reference.trim() || null, idempotency_key: input.requestKey }),
    onSuccess: () => { recovery.clear(); setOpen(false); void client.invalidateQueries({ queryKey: ["ar-invoice-print"] }); void client.invalidateQueries({ queryKey: ["ar-reporting"] }); void client.invalidateQueries({ queryKey: ["pos-sales"] }); toast.success("Customer receipt posted"); },
    onError: (e: any) => setError(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : e?.message || "Receipt failed"),
  });
  return <><Button size="sm" onClick={() => { setError(""); setInput(recovery.load() ?? { amount: outstanding, paymentDate: new Date().toLocaleDateString("en-CA"), method: "BANK_TRANSFER", reference: "", requestKey: crypto.randomUUID() }); setOpen(true); }}>Receive Payment</Button>
    <Dialog open={open} onOpenChange={value => { if (!save.isPending) setOpen(value); }}><DialogContent><DialogHeader><DialogTitle>Receive customer payment</DialogTitle></DialogHeader><DialogBody>
      <div className="grid gap-3 sm:grid-cols-2">
        <div><label className="text-xs">Receipt date</label><input aria-label="Receipt date" className={field} type="date" value={input.paymentDate} onChange={e => change("paymentDate", e.target.value)} /></div>
        <div><label className="text-xs">Amount received</label><input aria-label="Amount received" className={field} type="number" min="0.01" step="0.01" value={input.amount} onChange={e => change("amount", e.target.value)} /></div>
        <SearchableSelect label="Cash / bank account" required value={input.cashAccountId} options={options.data?.cash_accounts ?? []} onChange={value => change("cashAccountId", value)} />
        <div><label className="text-xs">Payment method</label><select className={field} value={input.method} onChange={e => change("method", e.target.value)}><option value="BANK_TRANSFER">Bank Transfer</option><option value="CASH">Cash</option><option value="CARD">Card</option></select></div>
        <div className="sm:col-span-2"><label className="text-xs">Receipt / bank reference</label><input aria-label="Receipt reference" className={field} value={input.reference} onChange={e => change("reference", e.target.value)} /></div>
      </div>{error && <p className="mt-2 text-sm text-red-700" role="alert">{error}</p>}
    </DialogBody><DialogFooter><Button variant="outline" disabled={save.isPending} onClick={() => setOpen(false)}>Close</Button><Button disabled={save.isPending || !input.cashAccountId || !input.paymentDate || Number(input.amount) <= 0 || Number(input.amount) > Number(outstanding)} onClick={() => save.mutate()}>Post Receipt</Button></DialogFooter></DialogContent></Dialog>
  </>;
}

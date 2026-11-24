import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "@/api/client";
import Button from "@/components/ui/Button";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import SearchableSelect from "@/components/form/SearchableSelect";
import { FORM_UI } from "@/config/formUi";
import useFormRecovery from "@/hooks/useFormRecovery";
import { todayLocal } from "@/utils/dateConstraints";

type Input = {
  amount: string;
  paymentDate: string;
  cashAccountId?: number;
  method: string;
  reference: string;
  requestKey: string;
};
type ReceiptErrors = Partial<Record<"amount" | "paymentDate" | "cashAccountId" | "requestKey", string>>;

const valid = (value: unknown): value is Input =>
  !!value &&
  typeof value === "object" &&
  ["amount", "paymentDate", "method", "reference", "requestKey"].every(
    (key) => typeof (value as Record<string, unknown>)[key] === "string",
  );

const inputClass = `${FORM_UI.controlBase} ${FORM_UI.density.compact.control}`;

const newRequestKey = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

export default function ARReceiptForm({ invoiceId, outstanding }: { invoiceId: number; outstanding: string }) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState<Input>({
    amount: "",
    paymentDate: "",
    method: "BANK_TRANSFER",
    reference: "",
    requestKey: "",
  });
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<ReceiptErrors>({});
  const recovery = useFormRecovery(`ar:receipt:${invoiceId}`, input, open, valid);
  const options = useQuery({
    queryKey: ["customer-receipt-options", invoiceId],
    queryFn: async () => (await api.get("/customer-payments/options")).data,
    enabled: open,
  });

  const change = <K extends keyof Input>(key: K, value: Input[K]) => {
    setInput((previous) => ({ ...previous, [key]: value }));
    setFieldErrors((previous) => ({ ...previous, [key]: undefined }));
    setError("");
  };

  const openForm = () => {
    setError("");
    setFieldErrors({});
    const saved = recovery.load();
    if (saved) {
      setInput(saved);
      recovery.notifyRestored();
    } else {
      setInput({
        amount: outstanding,
        paymentDate: todayLocal(),
        method: "BANK_TRANSFER",
        reference: "",
        requestKey: newRequestKey(),
      });
    }
    setOpen(true);
  };

  const save = useMutation({
    mutationFn: () =>
      api.post("/customer-payments", {
        account_receivable_id: invoiceId,
        amount: input.amount,
        payment_date: input.paymentDate,
        cash_account_id: input.cashAccountId,
        payment_method: input.method,
        reference_number: input.reference.trim() || null,
        idempotency_key: input.requestKey,
      }),
    onSuccess: () => {
      recovery.clear();
      setOpen(false);
      void client.invalidateQueries({ queryKey: ["ar-invoice-print"] });
      void client.invalidateQueries({ queryKey: ["ar-reporting"] });
      void client.invalidateQueries({ queryKey: ["pos-sales"] });
      toast.success("Customer receipt posted");
    },
    onError: (cause: any) => {
      const detail = cause?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : cause?.message || "Receipt failed");
    },
  });

  const submit = () => {
    const next: ReceiptErrors = {};
    if (!input.paymentDate) next.paymentDate = "Choose the receipt date.";
    if (!(Number(input.amount) > 0)) next.amount = "Enter an amount greater than zero.";
    else if (Number(input.amount) > Number(outstanding))
      next.amount = "Receipt cannot exceed the outstanding balance.";
    if (!input.cashAccountId) next.cashAccountId = "Choose the cash or bank account.";
    if (!input.requestKey) next.requestKey = "Restart the form to generate a new receipt key.";
    setFieldErrors(next);
    setError("");
    if (Object.values(next).some(Boolean)) return;
    save.mutate();
  };

  return (
    <>
      <Button size="sm" onClick={openForm}>Receive Payment</Button>
      <Dialog
        open={open}
        onOpenChange={(value) => {
          if (!save.isPending) setOpen(value);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Receive customer payment</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <div className="mb-3 rounded-md border border-blue-100 bg-blue-50 px-3 py-2 text-xs leading-5 text-blue-900">
              Posting records a customer receipt and updates the invoice balance. Keep the bank reference and
              idempotency key together when retrying after a connection problem.
            </div>
            {recovery.failed && (
              <p className="mb-2 text-xs text-amber-700">
                Browser storage unavailable; keep this dialog open until the receipt is posted.
              </p>
            )}
            <div className={FORM_UI.grid}>
              <label className="text-xs font-medium text-slate-700">
                Receipt date
                <input
                  aria-label="Receipt date"
                  className={`${inputClass} mt-1 ${fieldErrors.paymentDate ? FORM_UI.error : ""}`}
                  type="date"
                  value={input.paymentDate}
                  onChange={(event) => change("paymentDate", event.target.value)}
                />
                {fieldErrors.paymentDate && <span className={FORM_UI.errorText}>{fieldErrors.paymentDate}</span>}
              </label>
              <label className="text-xs font-medium text-slate-700">
                Amount received
                <input
                  aria-label="Amount received"
                  className={`${inputClass} mt-1 ${fieldErrors.amount ? FORM_UI.error : ""}`}
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={input.amount}
                  onChange={(event) => change("amount", event.target.value)}
                />
                {fieldErrors.amount && <span className={FORM_UI.errorText}>{fieldErrors.amount}</span>}
                <span className={FORM_UI.helpText}>Outstanding: {outstanding}</span>
              </label>
              <div>
                <SearchableSelect
                  label="Cash / bank account"
                  required
                  invalid={!!fieldErrors.cashAccountId}
                  value={input.cashAccountId}
                  options={options.data?.cash_accounts ?? []}
                  onChange={(value) => change("cashAccountId", value)}
                />
                {fieldErrors.cashAccountId && <span className={FORM_UI.errorText}>{fieldErrors.cashAccountId}</span>}
                {options.isPending && <span className={FORM_UI.helpText}>Loading accounts...</span>}
              </div>
              <label className="text-xs font-medium text-slate-700">
                Payment method
                <select
                  aria-label="Payment method"
                  className={`${inputClass} mt-1`}
                  value={input.method}
                  onChange={(event) => change("method", event.target.value)}
                >
                  <option value="BANK_TRANSFER">Bank Transfer</option>
                  <option value="CASH">Cash</option>
                  <option value="CARD">Card</option>
                </select>
              </label>
              <label className="text-xs font-medium text-slate-700 md:col-span-2">
                Receipt / bank reference
                <input
                  aria-label="Receipt reference"
                  className={`${inputClass} mt-1`}
                  value={input.reference}
                  onChange={(event) => change("reference", event.target.value)}
                />
                <span className={FORM_UI.helpText}>Optional, but recommended for reconciliation.</span>
              </label>
            </div>
            {fieldErrors.requestKey && <p className={FORM_UI.errorText}>{fieldErrors.requestKey}</p>}
            {error && <p className="mt-2 text-sm text-red-700" role="alert">{error}</p>}
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" disabled={save.isPending} onClick={() => setOpen(false)}>Close</Button>
            <Button disabled={save.isPending} loading={save.isPending} onClick={submit}>Post Receipt</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
